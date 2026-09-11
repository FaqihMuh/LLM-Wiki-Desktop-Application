"""Persist and restore the Maintenance Inspector state across sessions.

Stored next to AppConfig (%LOCALAPPDATA%\\LLM Wiki\\), not inside the
workspace: this is application UI state, not workspace content, and a
workspace created from the template has no "gui/" folder of its own —
storing it there previously only worked by coincidence when the
workspace happened to be the app's own source tree during development.
"""

import json
import os
from pathlib import Path

_APP_DIR_NAME = "LLM Wiki"
_FILENAME = "maintenance_inspector.json"


def _state_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / _APP_DIR_NAME / _FILENAME


def load_maintenance_state() -> dict:
    """Return {"overall_status", "last_scan", "duration"} or {} if nothing saved."""
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_maintenance_state(state: dict) -> None:
    """Write the Inspector state dict to disk. Silently ignores write errors."""
    try:
        path = _state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass
