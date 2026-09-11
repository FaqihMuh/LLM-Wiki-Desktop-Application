"""
Windows Tesseract auto-discovery fallback.

`pymupdf4llm.ocr.rapidtess_api` needs Tesseract's language data (tessdata)
to be locatable at import time (its module-level
`TESSDATA = pymupdf.get_tessdata()`, see the pymupdf4llm source). PyMuPDF's
own `get_tessdata()` already tries, in order:

    1. an explicit path argument (not used here),
    2. the `TESSDATA_PREFIX` environment variable,
    3. on Windows, `where tesseract` to locate the installed executable and
       derive `<tesseract.exe dir>/tessdata` from it.

That built-in mechanism is sufficient whenever Tesseract-OCR's installer put
`tesseract.exe` on the System PATH. It is not sufficient when Tesseract is
installed but PATH was never updated (a common state for a manual/portable
install) — `where tesseract` then finds nothing and `get_tessdata()` raises
`RuntimeError`, which is exactly the failure this module exists to avoid.

`ensure_tessdata_available()` adds tessdata discovery tiers *before* giving
up, without requiring the user to edit the System PATH themselves:

    0. A `tessdata` folder bundled with this application itself (see
       `gui/app_paths.bundled_assets_root()`) — `assets/tessdata/` next to
       the already-bundled `assets/workspace_template/`. Checked first so a
       frozen build never needs an external Tesseract-OCR install at all
       for the one language this app actually uses ("eng" — see
       gui/runtime/worker.py). Only `eng.traineddata` (plus its Apache-2.0
       LICENSE) is bundled; PyMuPDF's OCR recognition runs through its own
       statically-linked Tesseract library (`Pixmap.pdfocr_tobytes()`), it
       does not spawn a `tesseract.exe` subprocess, so no executable or
       other Tesseract-OCR install files are needed here.
    1. PyMuPDF's own built-in detection, unchanged (TESSDATA_PREFIX, then
       `where tesseract`).
    2. A `tesseract` executable resolvable via this process's own PATH
       (`shutil.which`) — a second, independently-implemented check in case
       PyMuPDF's own `where tesseract` subprocess call fails for reasons
       specific to that call path even though the executable is otherwise
       resolvable.
    3. Only as a last resort: well-known default Tesseract-OCR install
       locations on Windows (under `%ProgramFiles%` / `%ProgramFiles(x86)%`).

Whenever tier 0 finds the bundled folder, or tier 2/3 finds an externally
installed one, `TESSDATA_PREFIX` is set in this process's environment so
PyMuPDF's own mechanism (and this function, on any later call) picks it up
directly through tier 1 from then on. No path is ever hard-coded into a
PyMuPDF/Tesseract call — only used, if found, to populate the same
environment variable PyMuPDF already honors. This also means a system-wide
Tesseract-OCR install, if present, remains fully honored: tier 0 only wins
when the bundled folder actually exists (always true for a packaged build,
never true when running from source without it), matching the requirement
that the app work identically from source, from the PyInstaller dist/, and
after Inno Setup installation.
"""

import os
import shutil
from pathlib import Path

import pymupdf

from ..app_paths import bundled_assets_root


def _tessdata_dir_for_executable(exe_path: str) -> Path | None:
    """Return `<exe's directory>/tessdata` if that folder actually exists."""
    tessdata = Path(exe_path).resolve().parent / "tessdata"
    return tessdata if tessdata.is_dir() else None


def _well_known_windows_install_dirs() -> list[Path]:
    """Default Tesseract-OCR install locations the official Windows
    installer uses, resolved via the environment rather than a hard-coded
    drive letter so this still works on a non-C: install."""
    dirs = []
    for env_var in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_var)
        if base:
            dirs.append(Path(base) / "Tesseract-OCR")
    return dirs


def _bundled_tessdata_dir() -> Path | None:
    """Return the app's own bundled tessdata folder if it exists and
    actually contains eng.traineddata — works under `python -m gui.main`
    (source), a PyInstaller onedir/onefile dist/, and after Inno Setup
    installation alike, since `bundled_assets_root()` is the one canonical
    resolver for all three (see gui/app_paths.py)."""
    tessdata = bundled_assets_root() / "assets" / "tessdata"
    return tessdata if (tessdata / "eng.traineddata").is_file() else None


def ensure_tessdata_available() -> str:
    """Make sure a Tesseract tessdata folder can be found before OCR runs.

    Returns the tessdata folder path on success. Raises `RuntimeError` with
    a clear, actionable message (no raw traceback) if Tesseract cannot be
    located by any of the tiers described in the module docstring.
    """
    # Tier 0: tessdata bundled with this application.
    bundled = _bundled_tessdata_dir()
    if bundled is not None:
        os.environ["TESSDATA_PREFIX"] = str(bundled)
        return str(bundled)

    # Tier 1: PyMuPDF's own built-in detection.
    try:
        return pymupdf.get_tessdata()
    except Exception:
        pass

    # Tier 2: tesseract executable resolvable via this process's PATH.
    exe = shutil.which("tesseract")
    if exe:
        tessdata = _tessdata_dir_for_executable(exe)
        if tessdata is not None:
            os.environ["TESSDATA_PREFIX"] = str(tessdata)
            return str(tessdata)

    # Tier 3: well-known default Windows install locations, last resort only.
    for install_dir in _well_known_windows_install_dirs():
        tessdata = install_dir / "tessdata"
        if tessdata.is_dir():
            os.environ["TESSDATA_PREFIX"] = str(tessdata)
            return str(tessdata)

    raise RuntimeError(
        "Tesseract OCR tidak ditemukan. OCR untuk halaman/gambar hasil scan "
        "membutuhkan Tesseract-OCR terpasang di sistem (lihat "
        "https://github.com/UB-Mannheim/tesseract/wiki) beserta tessdata "
        "bahasa 'eng'. Pastikan Tesseract-OCR terpasang, atau tambahkan "
        "lokasi instalasinya ke System PATH."
    )
