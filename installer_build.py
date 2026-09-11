"""
Build script for the LLM Wiki Windows installer.

Packages the existing PyInstaller build (dist\\LLM Wiki\\) with Inno
Setup, using installer.iss. Does not change application, runtime, or
build (build.py / gui.spec) behavior — this script only orchestrates
the two existing steps:

    1. python build.py        (PyInstaller onedir build -> dist\\LLM Wiki\\)
    2. iscc installer.iss      (Inno Setup -> installer\\output\\*.exe)

Usage:
    python installer_build.py            # build app, then package installer
    python installer_build.py --skip-build   # package installer only,
                                              # reusing an existing dist\\LLM Wiki\\
"""

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BUILD_SCRIPT = PROJECT_ROOT / "build.py"
ISS_FILE = PROJECT_ROOT / "installer.iss"
DIST_DIR = PROJECT_ROOT / "dist" / "LLM Wiki"

_ISCC_CANDIDATES = [
    "ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def _find_iscc() -> str | None:
    for candidate in _ISCC_CANDIDATES:
        found = shutil.which(candidate)
        if found:
            return found
        if Path(candidate).is_file():
            return candidate
    return None


def main() -> int:
    skip_build = "--skip-build" in sys.argv

    if not skip_build:
        if not BUILD_SCRIPT.exists():
            print(f"Build script not found: {BUILD_SCRIPT}", file=sys.stderr)
            return 1
        print("Running:", sys.executable, BUILD_SCRIPT.name)
        result = subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=PROJECT_ROOT)
        if result.returncode != 0:
            return result.returncode

    if not DIST_DIR.exists():
        print(f"PyInstaller output not found: {DIST_DIR}\n"
              "Run `python build.py` first, or omit --skip-build.", file=sys.stderr)
        return 1

    if not ISS_FILE.exists():
        print(f"Inno Setup script not found: {ISS_FILE}", file=sys.stderr)
        return 1

    iscc = _find_iscc()
    if iscc is None:
        print(
            "ISCC.exe (Inno Setup command-line compiler) was not found on PATH "
            "or in its default install location.\n"
            "Install Inno Setup 6 (https://jrsoftware.org/isdl.php) and re-run "
            "this script, or run `iscc installer.iss` manually once it's "
            "installed.",
            file=sys.stderr,
        )
        return 1

    cmd = [iscc, str(ISS_FILE)]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
