"""
Application startup validation service.

Performs startup checks and reports whether the application may
continue launching. `gui/startup_flow.py` drives the interactive
(dialog-showing) part of application startup and calls this module as
its single source of validation truth.
"""

import shutil
from dataclasses import dataclass, field

from .config import WorkspaceConfig
from .workspace_manager import WorkspaceManager, default_manager


@dataclass
class StartupStatus:
    """Structured result of a startup validation run.

    `checks` maps a check name (e.g. "workspace") to whether it passed,
    and `issues` holds human-readable problem descriptions. Future
    checks append their own entry to both without requiring new fields
    on this class, so the public shape of StartupStatus stays stable as
    more checks are added.
    """

    can_continue: bool
    workspace: WorkspaceConfig
    checks: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)


class StartupChecker:
    """Single entry point for application startup validation.

    Performs, in order: Claude CLI detection, workspace existence, and
    workspace validity (the latter two via WorkspaceManager). Further
    checks (configuration loading, workspace selection, repair
    workflow) can be added later as additional private `_check_*`
    methods invoked from `run()`; each appends to the same
    `checks`/`issues` containers, so neither `run()`'s signature nor
    `StartupStatus`'s shape needs to change to accommodate them.
    """

    def __init__(self, manager: WorkspaceManager | None = None):
        self._manager = manager or default_manager()

    def run(self) -> StartupStatus:
        """Run all startup checks and return a structured StartupStatus."""
        checks: dict = {}
        issues: list = []

        self._check_claude(checks, issues)
        self._check_workspace_exists(checks, issues)
        self._check_workspace(checks, issues)

        return StartupStatus(
            can_continue=all(checks.values()),
            workspace=self._manager.current_workspace(),
            checks=checks,
            issues=issues,
        )

    # ── Individual checks ────────────────────────────────────────────

    def _check_claude(self, checks: dict, issues: list) -> None:
        """Detect whether the `claude` CLI is available on PATH."""
        available = shutil.which("claude") is not None
        checks["claude"] = available
        if not available:
            issues.append("Claude CLI was not found on PATH.")

    def _check_workspace_exists(self, checks: dict, issues: list) -> None:
        """Check whether the workspace root exists on disk."""
        exists = self._manager.exists()
        checks["workspace_exists"] = exists
        if not exists:
            issues.append(
                f"Workspace does not exist at {self._manager.current_workspace().root}."
            )

    def _check_workspace(self, checks: dict, issues: list) -> None:
        """Validate the current workspace via WorkspaceManager."""
        validation = self._manager.validate()
        checks["workspace"] = validation.valid
        if not validation.valid:
            issues.extend(
                f"Missing required workspace path: {label}"
                for label in validation.missing
            )


def default_checker() -> StartupChecker:
    """Return a StartupChecker for the current project-root workspace."""
    return StartupChecker()
