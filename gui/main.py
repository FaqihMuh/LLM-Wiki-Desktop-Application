"""
Entry point for the LLM Wiki Operating System GUI.

Run from the project root:
    python -m gui.main
or:
    python gui/main.py
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path when run directly
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent  # E:\claudellmwiki

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from gui.app import create_app


def main() -> int:
    app, window = create_app(_PROJECT_ROOT)
    if window is None:
        # Startup validation failed; a dialog already explained why.
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
