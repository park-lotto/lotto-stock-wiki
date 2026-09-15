"""Idempotently register the dashboard Stop hook in the global Claude Code settings."""
import json
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
HOOK_COMMAND = f'py "{Path(__file__).resolve().parent / "stop_hook.py"}"'


def main():
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8")) if SETTINGS_PATH.exists() else {}
    hooks = settings.setdefault("hooks", {})
    stop_entries = hooks.setdefault("Stop", [])
    for entry in stop_entries:
        for h in entry.get("hooks", []):
            if h.get("command") == HOOK_COMMAND:
                print("already installed")
                return
    stop_entries.append({
        "matcher": "",
        "hooks": [{"type": "command", "command": HOOK_COMMAND}],
    })
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    print("installed")


if __name__ == "__main__":
    main()
