"""
Application configuration layer.

Exposes the workspace directory layout as read-only properties. This
module is not wired into the running application yet — it exists so a
later milestone can adopt it without touching existing runtime,
worker, or GUI code.
"""

from pathlib import Path

# Mirrors the resolution already used in gui/main.py: this file lives at
# <project_root>/gui/config.py, so its grandparent is the project root.
_HERE = Path(__file__).resolve()
_DEFAULT_ROOT = _HERE.parent.parent

# Source document formats accepted by Ingest: PDF (native or scanned) plus
# raster images containing text (PNG/JPG/JPEG), all routed through the same
# PyMuPDF4LLM hybrid-OCR preprocessing in gui/runtime/worker.py. Single
# source of truth — the file picker (gui/pages/ingest.py) and the Raw
# Documents listing/counts (gui/data/wiki_loader.py) both import this
# instead of each hard-coding their own extension list.
SOURCE_DOCUMENT_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")


class WorkspaceConfig:
    """Read-only view of the workspace directory layout.

    The root is accepted as a constructor argument (defaulting to the
    current project root) rather than hard-coded, so a future milestone
    can point the application at a relocated or alternate workspace by
    passing a different root — no other part of this module changes.
    """

    def __init__(self, root: Path | None = None):
        self._root = (root or _DEFAULT_ROOT).resolve()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def raw(self) -> Path:
        return self._root / "raw"

    @property
    def wiki(self) -> Path:
        return self._root / "wiki"

    @property
    def summaries(self) -> Path:
        return self.wiki / "summaries"

    @property
    def entities(self) -> Path:
        return self.wiki / "entities"

    @property
    def docs(self) -> Path:
        return self._root / "docs"

    @property
    def claude_md(self) -> Path:
        return self._root / "CLAUDE.md"


def default_workspace() -> WorkspaceConfig:
    """Return a WorkspaceConfig rooted at the current project root."""
    return WorkspaceConfig()
