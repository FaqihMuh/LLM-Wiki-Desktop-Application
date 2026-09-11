"""
Build script for the LLM Wiki desktop application.

Runs PyInstaller against gui.spec to produce a onedir distribution in
dist/LLM Wiki/. This script does not install dependencies — see
README_BUILD.md for prerequisites and the full build procedure.

Usage:
    python build.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SPEC_FILE = PROJECT_ROOT / "gui.spec"


def main() -> int:
    if not SPEC_FILE.exists():
        print(f"Spec file not found: {SPEC_FILE}", file=sys.stderr)
        return 1

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_FILE)]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
