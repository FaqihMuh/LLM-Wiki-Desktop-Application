# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the LLM Wiki desktop application — onedir build.

Build with:
    pyinstaller gui.spec
or:
    python build.py

See README_BUILD.md for prerequisites, the build command, and the
expected dist/ layout. This file only prepares the build; Milestone 7
does not run it (no executable is produced by this milestone).
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

# SPECPATH is injected by PyInstaller at spec-execution time — it is
# the directory containing this spec file, i.e. the project root.
PROJECT_ROOT = Path(SPECPATH)

block_cipher = None

# rapidocr-onnxruntime (Revision 7) ships its OCR models (config.yaml,
# models/*.onnx) as package data next to its Python modules, and resolves
# them at runtime via a path relative to its own __file__ — there is no
# PyInstaller community hook for this package (unlike onnxruntime/cv2/
# shapely, which already have one), so this data must be collected
# explicitly or OCR silently has no engine available once frozen.
rapidocr_datas = collect_data_files("rapidocr_onnxruntime")

# pymupdf-layout (transitive dependency of pymupdf4llm, Revision 7) ships
# its layout-detection ONNX models and matching .yaml configs under
# pymupdf/layout/resources/onnx/, and resolves them at runtime via a path
# relative to its own __file__ — same situation as rapidocr above, and
# likewise has no PyInstaller community hook. Without this, pymupdf.layout
# (imported transitively by pymupdf4llm) raises FileNotFoundError for
# layout_rf2.4.1+imf1.yaml the moment the frozen app starts.
pymupdf_layout_datas = collect_data_files("pymupdf.layout")

a = Analysis(
    [str(PROJECT_ROOT / "gui" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # Bundle the workspace template as-is; WorkspaceManager.create()
        # copies from this directory into any newly created workspace.
        # See README_BUILD.md and the Milestone 7 report for the known
        # risk around how the app locates this once frozen.
        (str(PROJECT_ROOT / "assets" / "workspace_template"), "assets/workspace_template"),
        # Bundled Tesseract tessdata (eng.traineddata + its Apache-2.0
        # LICENSE) so OCR works without a separate Tesseract-OCR install.
        # See gui/runtime/tesseract_env.py's Tier 0 for how this is found
        # at runtime via the same bundled_assets_root() resolver used for
        # assets/workspace_template above. Only "eng" is bundled — the only
        # OCR language this application uses (gui/runtime/worker.py).
        (str(PROJECT_ROOT / "assets" / "tessdata"), "assets/tessdata"),
    ] + rapidocr_datas + pymupdf_layout_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LLM Wiki",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / "icons" / "ClaudeLLMWiki.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LLM Wiki",
)
