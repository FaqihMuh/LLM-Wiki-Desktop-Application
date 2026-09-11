"""
Persistent application configuration.

Stores user-level application settings — currently only the selected
workspace path — in the Windows per-user local application data
directory, never inside the workspace itself. This is intentionally
separate from WorkspaceConfig (gui/config.py), which describes a
workspace's directory layout, not application preferences.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

_APP_DIR_NAME = "LLM Wiki"
_FILENAME = "config.json"


def _config_dir() -> Path:
    """Return the per-user local application data directory for LLM Wiki.

    Uses %LOCALAPPDATA% (machine-specific settings) rather than
    %APPDATA% (roaming) — a workspace path is a local filesystem
    location and should not roam to a different machine.
    """
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / _APP_DIR_NAME


def _config_path() -> Path:
    return _config_dir() / _FILENAME


@dataclass
class AppConfig:
    """Persistent application settings. Currently just the workspace path."""

    workspace_path: str | None = None


def load_app_config() -> AppConfig:
    """Load AppConfig from disk, or return defaults if none is saved yet."""
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return AppConfig()
    return AppConfig(workspace_path=data.get("workspace_path"))


def save_app_config(config: AppConfig) -> None:
    """Write AppConfig to disk. Silently ignores write errors."""
    try:
        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"workspace_path": config.workspace_path}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
