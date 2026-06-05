import base64
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pypdf import PdfReader


POLICY_DIR = Path(__file__).resolve().parent.parent / "data" / "policies"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
POLICY_ALIASES = {
    "HousingPolicy": {"accommodation", "house", "housing", "hra", "lease", "rent"},
    "Mobile-BroadbandExpensesPolicy": {
        "bill",
        "broadband",
        "cell",
        "data",
        "expense",
        "internet",
        "mobile",
        "phone",
        "reimbursement",
    },
}
STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "can",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "me",
    "my",
    "of",
    "on",
    "policy",
    "show",
    "tell",
    "the",
    "to",
    "what",
}


def _load_env_file():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _tokens(text):
    normalized = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    normalized = normalized.replace("-", " ").replace("_", " ")
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", normalized.lower())
    return {word for word in words if word not in STOP_WORDS}


def _clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def _split_sentences(text):
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [_clean_text(chunk) for chunk in chunks if _clean_text(chunk)]


@lru_cache(maxsize=1)
def _load_policies():
    policies = []

    if not POLICY_DIR.exists():
        return policies

    for pdf_path in sorted(POLICY_DIR.glob("*.pdf")):
        pages = []
        try:
            reader = PdfReader(str(pdf_path))
        except Exception as exc:
            policies.append({
                "name": pdf_path.stem,
                "path": pdf_path,
                "error": str(exc),
                "pages": [],
            })
            continue

        for index, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            pages.append({
                "number": index,
                "text": _clean_text(text),
                "sentences": _split_sentences(text),
            })

        policies.append({
            "name": pdf_path.stem,
            "path": pdf_path,
            "error": None,
            "pages": pages,
        })

    return policies


def _score_text(query_tokens, text):
    text_tokens = _tokens(text)
    if not text_tokens:
        return 0

    return len(query_tokens & text_tokens)


def _policy_name_score(query_tokens, policy_name):
    alias_tokens = POLICY_ALIASES.get(policy_name, set())
    return len(query_tokens & (_tokens(policy_name) | alias_tokens))


def _best_snippets(policy, query_tokens):
    matches = []

    for page in policy["pages"]:
        for sentence in page["sentences"]:
            score = _score_text(query_tokens, sentence)
            if score:
                matches.append({
                    "page": page["number"],
                    "score": score,
                    "text": sentence,
                })

    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[:3]


def _extract_gemini_text(response_body):
    parts = []

    for candidate in response_body.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text)

    return "\n".join(parts).strip() or "Gemini could not read this policy PDF."


def _ask_gemini_about_policy(user_request, policy):
    _load_env_file()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "This PDF appears to be scanned, and GEMINI_API_KEY is required to search scanned policy PDFs."

    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip() or "gemini-flash-latest"
    model = model.removeprefix("models/")
    if model == "gemini-1.5-flash":
        model = "gemini-flash-latest"

    encoded_pdf = base64.b64encode(policy["path"].read_bytes()).decode("ascii")
    prompt = (
        f"Search this policy PDF named {policy['name']} for the user's question. "
        "Answer only from the PDF. Include the policy name, the most relevant answer, "
        "and page number if visible. If the answer is not present, say that it was not found.\n\n"
        f"User question: {user_request}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": encoded_pdf,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1
        }
    }

    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=75) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        return f"Gemini policy search failed with status {exc.code}. {details[:300]}"
    except URLError as exc:
        return f"Gemini policy search is unreachable: {exc.reason}"
    except TimeoutError:
        return "Gemini policy search timed out. Please try again."

    return _extract_gemini_text(body)


def process(user_request):
    policies = _load_policies()

    if not policies:
        return {
            "agent": "Policy Search Agent",
            "task": "No policy PDFs were found in backend/data/policies."
        }

    query_tokens = _tokens(user_request)
    if not query_tokens:
        return {
            "agent": "Policy Search Agent",
            "task": "Please ask a policy question with a keyword, for example: mobile reimbursement policy or housing policy."
        }

    ranked = []
    for policy in policies:
        if policy["error"]:
            continue

        policy_text = " ".join(page["text"] for page in policy["pages"])
        filename_score = _policy_name_score(query_tokens, policy["name"]) * 3
        content_score = _score_text(query_tokens, policy_text)
        snippets = _best_snippets(policy, query_tokens)
        snippet_score = sum(item["score"] for item in snippets)
        total_score = filename_score + content_score + snippet_score

        if total_score:
            ranked.append({
                "policy": policy,
                "score": total_score,
                "snippets": snippets,
            })

    ranked.sort(key=lambda item: item["score"], reverse=True)

    if not ranked:
        available = ", ".join(policy["name"] for policy in policies)
        return {
            "agent": "Policy Search Agent",
            "task": f"No matching policy content found. Available policies: {available}."
        }

    best = ranked[0]
    policy = best["policy"]
    snippet_lines = [
        f"Page {item['page']}: {item['text'][:350]}"
        for item in best["snippets"]
    ]

    if not snippet_lines:
        return {
            "agent": "Policy Search Agent",
            "task": f"Best match: {policy['name']}. {_ask_gemini_about_policy(user_request, policy)}"
        }

    return {
        "agent": "Policy Search Agent",
        "task": f"Best match: {policy['name']}. " + " ".join(snippet_lines)
    }
