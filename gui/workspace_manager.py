"""
Workspace management service.

Owns workspace-level operations (existence checks, validation, creation,
repair) on top of the Application Configuration layer introduced in
Milestone 1. This module is not wired into the running application yet
— it exists so a later milestone can adopt it as the single entry point
for workspace operations without touching existing runtime, worker, or
GUI code.
"""

import shutil
from dataclasses import dataclass, field

from .app_paths import bundled_assets_root
from .config import WorkspaceConfig, default_workspace

# Paths (relative to WorkspaceConfig) required for a workspace to be
# considered structurally valid.
_REQUIRED_PATHS = ("raw", "wiki", "summaries", "entities", "docs", "claude_md")

# The application's own workspace template — a static asset, not a
# workspace itself. bundled_assets_root() is the one canonical place
# that resolves this correctly in both dev and frozen execution.
_TEMPLATE_DIR = bundled_assets_root() / "assets" / "workspace_template"


@dataclass
class WorkspaceValidation:
    """Result of validating a workspace's directory structure."""

    valid: bool
    missing: list = field(default_factory=list)   # labels from _REQUIRED_PATHS


class WorkspaceManager:
    """Single entry point for workspace-related operations.

    Holds a WorkspaceConfig and operates entirely through it, never
    constructing paths itself. A future milestone can hand this class a
    WorkspaceConfig pointed at a user-selected workspace instead of the
    current project root — every method below already operates purely
    off `self._config`, so no method body would need to change.
    """

    def __init__(self, config: WorkspaceConfig | None = None):
        self._config = config or default_workspace()

    # ── Current workspace ────────────────────────────────────────────

    def current_workspace(self) -> WorkspaceConfig:
        """Return the WorkspaceConfig this manager currently operates on."""
        return self._config

    def set_workspace(self, config: WorkspaceConfig) -> None:
        """Point this manager at a different workspace.

        Minimal seam for a future workspace-selection UI: swaps the
        WorkspaceConfig this manager operates on. Persisting the new
        path (see gui/app_config.py) is the caller's responsibility —
        this method only updates in-memory state.
        """
        self._config = config

    # ── Existence ─────────────────────────────────────────────────────

    def exists(self) -> bool:
        """Return whether the workspace root is present on disk."""
        return self._config.root.is_dir()

    # ── Validation ────────────────────────────────────────────────────

    def validate(self) -> WorkspaceValidation:
        """Check that every required workspace path is present.

        Returns a WorkspaceValidation listing which required paths (by
        label, e.g. "wiki", "claude_md") are missing.
        """
        missing = [
            label for label in _REQUIRED_PATHS
            if not getattr(self._config, label).exists()
        ]
        return WorkspaceValidation(valid=not missing, missing=missing)

    # ── Creation ──────────────────────────────────────────────────────

    def create(self) -> None:
        """Create the workspace by copying the application's workspace template.

        Copies every top-level item in assets/workspace_template/
        (CLAUDE.md, docs/, wiki/, raw/) into the workspace root, so a
        freshly created workspace is immediately valid according to
        StartupChecker. Items that already exist at the destination are
        left untouched — this does not overwrite an existing workspace.

        The template's intentionally-empty directories (raw/,
        wiki/entities/, wiki/summaries/, wiki/concepts/,
        wiki/query_synthesis/) each carry a .gitkeep placeholder so
        PyInstaller's file-based bundling doesn't drop them from a
        frozen build; those placeholders are removed post-copy so the
        user's workspace ends up with genuinely empty directories.
        """
        self._config.root.mkdir(parents=True, exist_ok=True)
        for item in _TEMPLATE_DIR.iterdir():
            dest = self._config.root / item.name
            if dest.exists():
                continue
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        for gitkeep in self._config.root.rglob(".gitkeep"):
            gitkeep.unlink()

    # ── Repair (placeholder) ─────────────────────────────────────────

    def repair(self) -> None:
        """Repair a damaged workspace.

        Placeholder only — not implemented in this milestone. Intended
        to reconcile a workspace back to a valid structure in a future
        milestone.
        """
        raise NotImplementedError(
            "WorkspaceManager.repair() is a placeholder for a future milestone."
        )


def default_manager() -> WorkspaceManager:
    """Return a WorkspaceManager for the current project-root workspace."""
    return WorkspaceManager()
