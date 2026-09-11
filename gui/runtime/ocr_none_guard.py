"""
Application-side shim between PyMuPDF4LLM's `rapidtess_api` OCR adapter and
this project's RapidOCR dependency, plus Windows Tesseract auto-discovery
(see tesseract_env.py) and runtime diagnostic logging (Revision 8b).

Target pipeline (Revision 8): RapidOCR performs text *detection* only,
Tesseract performs text *recognition* — this is exactly what
`pymupdf4llm.ocr.rapidtess_api.exec_ocr()` already implements, unmodified.
This module does not reimplement any OCR logic; it only papers over one
defect in one specific dependency combination this project has been
observed running under, and otherwise gets out of the way.

`pymupdf4llm.ocr.rapidtess_api`'s internal shape differs across the
pymupdf4llm versions seen across this project's build (`.venv-build`,
matching the `pymupdf4llm==1.27.2.3` pin in requirements.txt) and its
day-to-day development environment (observed running `pymupdf4llm==1.28.2`,
newer than the pin — flagged separately as a dependency-pin discrepancy,
not something this shim silently "fixes"):

- **1.27.2.3-style** (`ENGINE`-based): a module-level `ENGINE`
  (`rapidocr_onnxruntime.RapidOCR` instance) called directly as
  `ENGINE.text_detector(img)`. With `rapidocr-onnxruntime==1.4.4` (the
  version this project pins), that class stores the detector under
  `self.text_det` instead — there is no `text_detector` attribute at all,
  so calling `rapidtess_api.exec_ocr()` as shipped raises `AttributeError`
  on the first OCR'd page. That detector's `__call__` can also legitimately
  return `(None, 0)` when its own preprocessing step finds nothing to
  detect — a normal outcome for a page/region with no text-shaped content,
  not an error — which `rapidtess_api.py` does not guard against
  (`for box in boxes:` on a `None` result raises `TypeError`). Text
  recognition happens via this shape's own module-level `get_text()`
  function, which calls Tesseract through `pymupdf.Pixmap.pdfocr_tobytes()`
  — PyMuPDF's own built-in Tesseract bridge, NOT the `pytesseract` package.
- **1.28+-style** (backend-auto-detecting `det_only`/`exec_ocr_detection`):
  a redesigned adapter with no `ENGINE` attribute at all, which already
  normalizes an empty/`None` detection result internally
  (`exec_ocr_interface.exec_ocr_detection`: `if not result: return`) — no
  correctness shim is needed for this shape. Detection is the module-level
  `det_only` callable; recognition is `exec_ocr_interface.get_text()`,
  which — same as the older shape — calls Tesseract via
  `pymupdf.Pixmap.pdfocr_tobytes()`, not `pytesseract`.

Only the ENGINE-based shape needs a *correctness* patch, and only when it
is actually present: `getattr(rapidtess_api, "ENGINE", None)` returns
`None` under the 1.28+ shape.

Where the older shape is used, the fix replaces `ENGINE.text_detector`
(aliasing whichever of `text_detector`/`text_det` is actually present) with
a small wrapper function, rather than patching a dunder method on the
detector instance. A dunder patch would not work here: `rapidtess_api.py`
invokes the detector via implicit call syntax (`ENGINE.text_detector(img)`),
and Python resolves implicit `obj(...)` calls through the object's *type*,
not its instance `__dict__` — so an instance-level `__call__` override
would silently never run. Replacing the `text_detector` attribute itself
sidesteps that: `ENGINE.text_detector` is a regular (non-dunder) attribute
lookup on `ENGINE`, so the replacement is found and called exactly as
`rapidtess_api` expects, and it fully delegates to the real, unmodified
detector instance for the actual detection work — only a `None` result is
normalized to an empty, iterable one before being handed back.

── Runtime diagnostic logging (Revision 8b) ────────────────────────────────

Added on top of the shim above, for BOTH rapidtess_api shapes, purely to
give runtime proof — not a hardcoded string — that OCR genuinely went
through RapidOCR detection + Tesseract recognition via rapidtess_api. The
same attribute-replacement technique used for the correctness shim above is
reused here: the module-level detection callable
(`ENGINE.text_detector`/`ENGINE.text_det`, or `det_only`) and the
module-level recognition function (`get_text`, in `rapidtess_api` or
`exec_ocr_interface` depending on shape) are each wrapped with a thin
logging layer that calls straight through to the real, unmodified
function/object and reports on what it actually returned — not on what was
configured. No pymupdf4llm source file is modified.

Everything is logged through the standard-library `logging` module on the
`"llm_wiki.ocr"` logger (INFO level) rather than printed directly, so it
carries no behavior of its own: gui/runtime/worker.py attaches a handler
that forwards these records into the same Execution Log every other Ingest
log line uses, only for the duration of the preprocessing call, and no
records are emitted (or, without a handler attached, go anywhere at all)
for pages that never reach guarded_ocr_function() — i.e. only pages the
hybrid OCR selection actually routes through OCR ever produce OCR log
lines.

Scope note: `rapidtess_api.ENGINE` (and the diagnostic wrappers below) are
process-wide singletons that this application only ever reaches through
`IngestWorker.run()`'s call to `pymupdf4llm.to_markdown()` —
`gui/pages/ingest.py` runs at most one `IngestWorker` at a time (a single
`self._worker` slot draining a sequential queue), and Query/Maintenance
never import `pymupdf4llm`. Patching these process-wide singletons, and
sharing the `_diagnostic_state` counters below across calls, is therefore
safe under the current architecture: pages are always OCR'd one at a time,
strictly sequentially, never concurrently.

Lazy import — IMPORTANT: `pymupdf4llm.ocr.rapidtess_api` is deliberately
NOT imported at module level here. That submodule's own top-level code does
`ENGINE = RapidOCR()` (loads RapidOCR's ONNX models, ~0.68s measured) and
`TESSDATA = pymupdf.get_tessdata()` (the Tesseract auto-discovery this
module's `ensure_tessdata_available()` call must run *before*, so the
env-var fallback is already in place the first time that module-level line
executes). worker.py imports `guarded_ocr_function` from this module at
application-startup time (via gui/runtime/__init__.py), so a module-level
import here would pay both costs on every app launch, even for sessions
that never run Ingest. The import stays deferred into
`guarded_ocr_function()` itself, matching pymupdf4llm's own default
(lazy/on-demand) behavior.

── Recognition-time geometry guard ─────────────────────────────────────────

Both `_get_text` wrappers below additionally guard against a defect in
`rapidtess_api.exec_ocr()` (present in both shapes, upstream in the
pymupdf4llm package, not modified here): it builds the region `IRect`
passed to `get_text()` from only two of RapidOCR's four quadrilateral
detection corners (`tl`, `br`), assuming an axis-aligned box. For a
sufficiently rotated/slanted detection this assumption does not hold —
`tl.y` can end up greater than `br.y` (or the equivalent for x), producing
a degenerate (empty/inverted) `IRect`. Handing that `IRect` to
`Pixmap.pdfocr_tobytes()` reaches native MuPDF's pdfocr band writer, which
rejects it with `FzErrorArgument: code=4: Invalid bandwriter header
dimensions/setup` — previously an uncaught exception that aborted
preprocessing (and, in turn, the whole Ingest attempt) for the entire
document over a single malformed region on one page.

The guard checks `irect.is_empty` (a property already provided by
`pymupdf.IRect`) before calling the real `get_text()`; when empty, that one
region is skipped (returns `""`, incrementing
`_diagnostic_state["recognize_skipped"]`) instead of being recognized.
This is deliberately not `irect.normalize()`: normalizing would silently
guess a crop from only two of the four original corners, which is not
guaranteed to reconstruct the rotated quad's true bounding box, and could
insert wrong or truncated text instead of just omitting that one region.
"""

import logging

from .tesseract_env import ensure_tessdata_available

logger = logging.getLogger("llm_wiki.ocr")
logger.setLevel(logging.INFO)

# Recognition happens once per detected text region/box (rapidtess_api's own
# exec_ocr loop calls get_text() once per box found), so counts are
# accumulated here across however many real calls one page's OCR makes and
# logged as one summary line per page — rather than one log line per box,
# which would flood the Execution Log for a text-dense scanned page. Reset
# at the top of every guarded_ocr_function() call. See the "Scope note"
# above for why sharing this module-level state across calls is safe here.
_diagnostic_state = {"recognize_calls": 0, "recognize_chars": 0, "recognize_skipped": 0}


def _install_engine_shims(engine, rapidtess_api) -> None:
    """1.27.x-style (ENGINE-based) rapidtess_api: install the attribute/
    None-safety compatibility shim described in the module docstring, plus
    diagnostic logging on the real detection and recognition call sites.
    Idempotent — installed once per process."""
    if not hasattr(engine, "_diagnostic_guard_installed"):
        real_detector = getattr(engine, "text_detector", None) or getattr(engine, "text_det", None)
        if real_detector is not None:
            detector_cls = type(real_detector)

            def _text_detector(img, **kwargs):
                boxes, elapse = real_detector(img, **kwargs)
                n = 0 if boxes is None else len(boxes)
                # Real runtime evidence for claim (2): this logs the actual
                # class of the object that just ran detection — a
                # rapidocr_onnxruntime TextDetector instance, not a string
                # we assert is true.
                logger.info(
                    "[OCR][detect] RapidOCR %s.%s instance called -> %d region(s) found",
                    detector_cls.__module__, detector_cls.__name__, n,
                )
                if boxes is None:
                    return [], elapse
                return boxes, elapse

            engine.text_detector = _text_detector
        engine._diagnostic_guard_installed = True

    if not getattr(rapidtess_api, "_diagnostic_recognizer_installed", False):
        real_get_text = rapidtess_api.get_text

        def _get_text(pixmap, irect, language="eng"):
            # Defensive guard: rapidtess_api.exec_ocr() builds this irect
            # from only two of RapidOCR's four quadrilateral corners
            # (tl, br), without accounting for rotation — see module
            # docstring "Recognition-time geometry guard" below. For a
            # sufficiently rotated/slanted detection this can produce a
            # degenerate (empty/inverted) IRect that
            # Pixmap.pdfocr_tobytes() cannot handle (native MuPDF raises
            # "Invalid bandwriter header dimensions/setup"). Deliberately
            # NOT irect.normalize(): normalizing would silently guess a
            # crop from only two of the four original corners, which is
            # not guaranteed to be the region's true bounding box for a
            # rotated quad. Skipping instead leaves only this one region
            # unrecognized (empty string — the same outcome exec_ocr()
            # already produces when no boxes are found at all) rather
            # than risk inserting wrong/truncated text.
            if irect.is_empty:
                _diagnostic_state["recognize_skipped"] += 1
                logger.info(
                    "[OCR][recognize] Skipped degenerate/empty region "
                    "irect=%s (would raise MuPDF pdfocr bandwriter error) "
                    "— no text recognized for this region only.",
                    irect,
                )
                return ""
            text = real_get_text(pixmap, irect, language=language)
            _diagnostic_state["recognize_calls"] += 1
            _diagnostic_state["recognize_chars"] += len(text)
            return text

        rapidtess_api.get_text = _get_text
        rapidtess_api._diagnostic_recognizer_installed = True


def _install_det_only_shims(rapidtess_api) -> None:
    """1.28+-style rapidtess_api: no correctness fix is needed (see module
    docstring), only diagnostic logging on the real detection callable
    (`det_only`) and the real recognition function
    (`exec_ocr_interface.get_text`). Idempotent — installed once per
    process."""
    if not getattr(rapidtess_api, "_diagnostic_guard_installed", False):
        real_det_only = getattr(rapidtess_api, "det_only", None)
        if real_det_only is not None:
            backend_name = getattr(rapidtess_api, "rapidocr_backend", "?")
            det_module = getattr(real_det_only, "__module__", "?")

            def _det_only(img):
                result = real_det_only(img)
                n = 0 if not result else len(result)
                # Real runtime evidence for claim (2): backend_name/det_module
                # are introspected from the actual callable pymupdf4llm chose
                # (detect_rapidocr_backend()), not a hardcoded label.
                logger.info(
                    "[OCR][detect] RapidOCR det_only() [backend=%s, module=%s] "
                    "called -> %d region(s) found",
                    backend_name, det_module, n,
                )
                return result

            rapidtess_api.det_only = _det_only
        rapidtess_api._diagnostic_guard_installed = True

    from pymupdf4llm.ocr import exec_ocr_interface
    if not getattr(exec_ocr_interface, "_diagnostic_recognizer_installed", False):
        real_get_text = exec_ocr_interface.get_text

        def _get_text(pixmap, irect, language="eng"):
            # Same defensive guard as _install_engine_shims()'s _get_text
            # above — see that function's comment and the module docstring
            # "Recognition-time geometry guard" section for the full
            # explanation. Kept as a separate, duplicated wrapper rather
            # than shared code because this function belongs to the
            # 1.28+-style shim, installed only when that shape is
            # actually present (see guarded_ocr_function() below).
            if irect.is_empty:
                _diagnostic_state["recognize_skipped"] += 1
                logger.info(
                    "[OCR][recognize] Skipped degenerate/empty region "
                    "irect=%s (would raise MuPDF pdfocr bandwriter error) "
                    "— no text recognized for this region only.",
                    irect,
                )
                return ""
            text = real_get_text(pixmap, irect, language=language)
            _diagnostic_state["recognize_calls"] += 1
            _diagnostic_state["recognize_chars"] += len(text)
            return text

        exec_ocr_interface.get_text = _get_text
        exec_ocr_interface._diagnostic_recognizer_installed = True


def guarded_ocr_function(page, dpi=300, pixmap=None, language="eng", keep_ocr_text=False):
    """Drop-in replacement for pymupdf4llm's rapidtess_api ocr_function.

    Delegates entirely to the real, unmodified `rapidtess_api.exec_ocr()`
    for all OCR work (RapidOCR text detection, Tesseract text recognition);
    the effective changes are the tessdata auto-discovery, the
    attribute/None-safety shim, and the diagnostic logging described in the
    module docstring above. This function is only ever invoked by
    PyMuPDF4LLM for a page/image that its own hybrid OCR selection decided
    actually needs OCR (see gui/runtime/worker.py's to_markdown() call:
    use_ocr=True, force_ocr=False) — so every log line below is, by
    construction, evidence for a page that genuinely went through OCR.
    """
    page_no = getattr(page, "number", "?")
    # Claims (4) and (5): dpi/language are logged from the actual arguments
    # this call received from pymupdf4llm — not restated from a config
    # constant — so this line breaks if the real values ever diverge.
    logger.info(
        "[OCR] page=%s entering OCR path (ocr_dpi=%s, ocr_language=%s)",
        page_no, dpi, language,
    )

    # Claim (6): tessdata must be locatable BEFORE rapidtess_api is first
    # imported below — its module-level `TESSDATA = pymupdf.get_tessdata()`
    # only runs once, the first time that module is imported into the
    # process — so this call, and this log line, always happen before any
    # detection/recognition below.
    tessdata_dir = ensure_tessdata_available()
    logger.info(
        "[OCR][tessdata] Tesseract tessdata found at %s (verified before OCR execution)",
        tessdata_dir,
    )

    from pymupdf4llm.ocr import rapidtess_api  # deferred — see module docstring

    # Claim (1): __name__/__file__ are introspected from the actual module
    # object this import statement just bound — proof this call path is
    # really going through pymupdf4llm.ocr.rapidtess_api and not, say, the
    # old rapidocr_api (which did detection AND recognition with RapidOCR
    # alone, no Tesseract involved).
    backend_info = f"module={rapidtess_api.__name__} ({rapidtess_api.__file__})"
    if hasattr(rapidtess_api, "rapidocr_backend"):
        backend_info += f", rapidocr_backend={rapidtess_api.rapidocr_backend}"
    logger.info("[OCR] backend = rapidtess_api, %s", backend_info)

    _diagnostic_state["recognize_calls"] = 0
    _diagnostic_state["recognize_chars"] = 0
    _diagnostic_state["recognize_skipped"] = 0

    engine = getattr(rapidtess_api, "ENGINE", None)
    if engine is not None:
        _install_engine_shims(engine, rapidtess_api)
    else:
        _install_det_only_shims(rapidtess_api)

    result = rapidtess_api.exec_ocr(
        page, dpi=dpi, pixmap=pixmap, language=language, keep_ocr_text=keep_ocr_text
    )

    # Claim (3): Tesseract recognition, counted from the real, wrapped
    # get_text() call site — the function that actually calls
    # pymupdf.Pixmap.pdfocr_tobytes(). Called out explicitly as PyMuPDF's
    # own built-in Tesseract bridge, NOT the separate `pytesseract` package
    # (which this project does not use anywhere).
    logger.info(
        "[OCR][recognize] Tesseract recognition via PyMuPDF "
        "Pixmap.pdfocr_tobytes(language=%s) — NOT pytesseract — "
        "called %d time(s), %d char(s) recognized, %d region(s) skipped "
        "(degenerate/empty geometry)",
        language, _diagnostic_state["recognize_calls"], _diagnostic_state["recognize_chars"],
        _diagnostic_state["recognize_skipped"],
    )
    logger.info("[OCR] page=%s OCR path complete", page_no)
    return result
