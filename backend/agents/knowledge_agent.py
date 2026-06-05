import json
from pathlib import Path


def process(topic: str):

    data_path = Path(__file__).resolve().parent.parent / "data" / "knowledge.json"
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "agent": "Knowledge Agent",
            "task": "Knowledge base not found"
        }

    info = data.get(topic.lower())
    if not info:
        return {
            "agent": "Knowledge Agent",
            "task": f"No policy found for: {topic}"
        }

    return {
        "agent": "Knowledge Agent",
        "task": info
    }
