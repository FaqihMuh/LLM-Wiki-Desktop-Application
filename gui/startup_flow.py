"""
Interactive application startup flow.

Top-level orchestration, `run_startup()`:

    App Start -> AppConfig saved?
        yes -> run_startup_flow()               (unchanged since Milestone 4)
        no  -> Claude OK? -> choose workspace -> create from template
               -> save AppConfig -> run_startup_flow()
    -> Open MainWindow

StartupChecker (non-interactive) remains the single source of startup
validation truth. This module is the only place that turns a
StartupStatus into dialogs — it owns user interaction, StartupChecker
does not.
"""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QDialogButtonBox, QFileDialog,
)

from .app_config import AppConfig, load_app_config, save_app_config
from .config import WorkspaceConfig
from .startup_checker import StartupChecker
from .workspace_manager import WorkspaceManager

_CLAUDE_INSTALL_URL = "https://docs.claude.com/en/docs/claude-code/overview"


def _default_workspace_suggestion() -> Path:
    """Return the workspace folder suggested on first launch.

    Always the current user's Documents folder (never a path inside the
    application install/build directory), so a freshly installed copy
    never suggests a location the user doesn't have write access to.
    """
    return Path.home() / "Documents" / "LLM Wiki"


def run_startup(project_root: Path) -> WorkspaceManager | None:
    """Top-level startup entry point — call this instead of run_startup_flow directly.

    `project_root` is only used on first launch, to run the pre-dialog
    Claude availability check (see `_run_first_launch`); the workspace
    location offered to the user is always `_default_workspace_suggestion()`.

    Returns a WorkspaceManager ready to hand to MainWindow, or None if
    startup should abort (a dialog explaining why has already been shown).
    """
    app_config = load_app_config()

    if app_config.workspace_path:
        # Configuration already exists — startup behaviour is unchanged.
        manager = WorkspaceManager(WorkspaceConfig(Path(app_config.workspace_path)))
        return manager if run_startup_flow(manager) else None

    return _run_first_launch(project_root)


def _run_first_launch(project_root: Path) -> WorkspaceManager | None:
    """First-launch path: no AppConfig has ever been saved.

    Checks Claude availability first (no point asking where to put a
    workspace if Claude isn't installed), then lets the user choose a
    workspace location, creates it from the template, persists the
    choice, and finally reuses run_startup_flow() for the same
    validation + "open MainWindow" decision every other launch uses.
    """
    manager = WorkspaceManager(WorkspaceConfig(project_root))
    status = StartupChecker(manager).run()

    if not status.checks.get("claude", True):
        _show_claude_missing_dialog()
        return None

    chosen_root = _show_first_launch_dialog(_default_workspace_suggestion())
    if chosen_root is None:
        return None   # user cancelled startup

    manager.set_workspace(WorkspaceConfig(chosen_root))
    manager.create()
    save_app_config(AppConfig(workspace_path=str(chosen_root)))

    return manager if run_startup_flow(manager) else None


def run_startup_flow(manager: WorkspaceManager) -> bool:
    """Run startup validation, prompting the user as needed.

    Returns True when it is safe to open MainWindow, False when
    startup should abort (a dialog explaining why has already been
    shown; the caller must not open MainWindow in that case).
    """
    checker = StartupChecker(manager)
    status = checker.run()

    if not status.checks.get("claude", True):
        _show_claude_missing_dialog()
        return False

    if not status.checks.get("workspace_exists", True):
        if _confirm_create_workspace(status.workspace.root):
            manager.create()
            status = checker.run()   # re-validate after creation

    if not status.checks.get("workspace", True):
        _show_validation_issues(status.workspace.root, status.issues)
        return False

    return True


# ── Dialogs ──────────────────────────────────────────────────────────

def _show_claude_missing_dialog() -> None:
    """Explain that the Claude CLI is required and offer the install guide."""
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Claude CLI Required")
    box.setText(
        "LLM Wiki requires Claude CLI to run Ingest and Query operations. "
        "But it could not be found on PATH.\n\n"
        "Install the Claude CLI, then relaunch LLM Wiki."
    )
    guide_btn = box.addButton("Open Installation Guide", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Close", QMessageBox.ButtonRole.RejectRole)

    # Loop so clicking "Open Installation Guide" doesn't dismiss the
    # dialog before the user has a chance to click Close.
    while True:
        box.exec()
        if box.clickedButton() is guide_btn:
            QDesktopServices.openUrl(QUrl(_CLAUDE_INSTALL_URL))
            continue
        break


def _confirm_create_workspace(root) -> bool:
    """Ask the user whether to create the missing workspace. Returns their choice."""
    reply = QMessageBox.question(
        None,
        "Workspace Not Found",
        f"No workspace was found at:\n{root}\n\nCreate it now?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes


def _show_validation_issues(root, issues: list) -> None:
    """Display every workspace validation issue."""
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle("Workspace Invalid")
    body = f"The workspace at:\n{root}\n\nis missing required items:\n\n"
    body += "\n".join(f"- {issue}" for issue in issues)
    box.setText(body)
    box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
    box.exec()


class _FirstLaunchDialog(QDialog):
    """Asks the user where to create their first LLM Wiki workspace."""

    def __init__(self, default_root: Path):
        super().__init__()
        self.setWindowTitle("Welcome to LLM Wiki")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        explain = QLabel(
            "This is the first time LLM Wiki has been launched.\n\n"
            "Choose a folder for your workspace. LLM Wiki will set it up "
            "with everything it needs to get started."
        )
        explain.setWordWrap(True)
        layout.addWidget(explain)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit(str(default_root))
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose Workspace Location", self._path_edit.text()
        )
        if chosen:
            self._path_edit.setText(chosen)

    def chosen_path(self) -> Path:
        return Path(self._path_edit.text())


def _show_first_launch_dialog(default_root: Path) -> Path | None:
    """Show the first-launch workspace picker. Returns the chosen path, or None if cancelled."""
    dialog = _FirstLaunchDialog(default_root)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.chosen_path()
    return None
