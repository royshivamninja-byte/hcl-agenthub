import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def _load_env_file():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


SYSTEM_INSTRUCTIONS = (
    "You are HCL AgentHub's general AI assistant. Answer any user question "
    "clearly, accurately, and helpfully. If a question needs current private "
    "company data that was not provided, say what information is needed instead "
    "of inventing it."
)


def _extract_openai_text(response_body):
    if response_body.get("output_text"):
        return response_body["output_text"].strip()

    for item in response_body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"].strip()

    return "I could not read the AI response. Please try again."


def _extract_gemini_text(response_body):
    parts = []

    for candidate in response_body.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text)

    return "\n".join(parts).strip() or "I could not read the Gemini response. Please try again."


def _call_openai(user_request: str, api_key: str):
    model = os.getenv("MODEL_NAME", "gpt-4o-mini").strip() or "gpt-4o-mini"
    payload = {
        "model": model,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": user_request,
        "temperature": 0.3,
    }

    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        return {
            "agent": "AI Agent",
            "task": f"AI request failed with status {exc.code}. {details[:300]}"
        }
    except URLError as exc:
        return {
            "agent": "AI Agent",
            "task": f"AI service is unreachable: {exc.reason}"
        }
    except TimeoutError:
        return {
            "agent": "AI Agent",
            "task": "AI request timed out. Please try again."
        }

    return {
        "agent": "AI Agent",
        "task": _extract_openai_text(body)
    }


def _call_gemini(user_request: str, api_key: str):
    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip() or "gemini-flash-latest"
    model = model.removeprefix("models/")
    if model == "gemini-1.5-flash":
        model = "gemini-flash-latest"

    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_INSTRUCTIONS}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_request}]
            }
        ],
        "generationConfig": {
            "temperature": 0.3
        }
    }

    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        return {
            "agent": "Gemini AI Agent",
            "task": f"Gemini request failed with status {exc.code}. {details[:300]}"
        }
    except URLError as exc:
        return {
            "agent": "Gemini AI Agent",
            "task": f"Gemini service is unreachable: {exc.reason}"
        }
    except TimeoutError:
        return {
            "agent": "Gemini AI Agent",
            "task": "Gemini request timed out. Please try again."
        }

    return {
        "agent": "Gemini AI Agent",
        "task": _extract_gemini_text(body)
    }


def process(user_request: str):
    _load_env_file()

    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if gemini_api_key:
        return _call_gemini(user_request, gemini_api_key)

    if openai_api_key:
        return _call_openai(user_request, openai_api_key)

    return {
        "agent": "AI Agent",
        "task": "GEMINI_API_KEY or OPENAI_API_KEY is missing in backend/.env. Add one key, restart the backend, and I can answer general questions."
    }
