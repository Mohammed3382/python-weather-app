import json
from pathlib import Path


PREFERENCES_FILE = Path("user_preferences.json")


def load_user_preferences():
    if not PREFERENCES_FILE.exists():
        return {}

    try:
        payload = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    return payload if isinstance(payload, dict) else {}


def save_user_preferences(updates):
    payload = load_user_preferences()
    payload.update(updates or {})
    PREFERENCES_FILE.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return payload
