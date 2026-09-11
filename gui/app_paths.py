"""
Application bundle path resolution.

Resolves the directory containing the application's own bundled,
read-only assets (currently: assets/workspace_template/) — correctly
under both `python -m gui.main` development execution and a frozen
PyInstaller onedir (or onefile) build. This is the one canonical
implementation of that resolution; nothing else should recompute it
independently.

This is deliberately separate from workspace location (WorkspaceConfig
/ WorkspaceManager's default root): that's where a *user's* workspace
lives, which is an unrelated concern this module does not touch.
"""

import sys
from pathlib import Path


def bundled_assets_root() -> Path:
    """Return the directory containing the application's bundled assets/.

    - Frozen (PyInstaller): `sys._MEIPASS`, the directory PyInstaller's
      bootloader points at bundled `datas` for both onedir and onefile
      builds — the officially supported way to locate bundled data.
    - Development: two levels up from this file (gui/<file>.py ->
      gui/ -> project root), matching the project's existing layout
      where assets/ is a project-root sibling of gui/.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        # Defensive fallback only; real PyInstaller builds always set
        # _MEIPASS when frozen is True.
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
