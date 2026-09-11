"""
Background operation workers.

Each worker runs one LLM Wiki Operating System operation in a separate thread
by invoking the `claude` CLI as a subprocess.  The prompt is written to stdin;
stdout is streamed line by line so the UI can react to stage markers in real time.
"""

import json
import logging
import time
from pathlib import Path

import pymupdf
import pymupdf4llm
from PySide6.QtCore import QThread, Signal

from ..config import WorkspaceConfig, SOURCE_DOCUMENT_EXTENSIONS
from ..data.wiki_loader import _parse_frontmatter
from .claude_runner import (
    ClaudeProcess,
    parse_stage,
    parse_result,
    REPORT_START,
    REPORT_END,
)
from .ocr_none_guard import guarded_ocr_function


class _OcrDiagnosticLogHandler(logging.Handler):
    """Forwards gui.runtime.ocr_none_guard's "llm_wiki.ocr" diagnostic log
    records (Revision 8b runtime OCR-backend verification) into the same
    Execution Log every other Ingest log line goes through
    (IngestWorker._emit_log / log_appended signal).

    Attached only for the duration of the preprocessing call in
    IngestWorker.run() below and removed immediately after (see the
    try/finally around it) — it never affects Claude CLI output, and
    produces no log lines at all for a document whose pages never enter
    guarded_ocr_function() (i.e. a purely text-based PDF, where hybrid OCR
    selection correctly skips OCR entirely).
    """

    def __init__(self, emit_fn):
        super().__init__()
        self._emit_fn = emit_fn

    def emit(self, record: logging.LogRecord) -> None:
        self._emit_fn(self.format(record))


def _open_for_markdown(src_path: Path) -> str | pymupdf.Document:
    """Return the input pymupdf4llm.to_markdown() should receive for src_path.

    A PDF is passed through by path unchanged — to_markdown() opens PDFs
    itself. An image (PNG/JPG/JPEG) is converted to an in-memory, single-page
    PDF first instead of being handed to to_markdown() as a path.

    This is not the "no conversion needed" path one might expect from
    PyMuPDF being able to open a raster image directly as a one-page
    pseudo-document: that does work far enough to run OCR *detection*, but
    OCR *text insertion* (`page.insert_font()` / `page.insert_text()`,
    called by rapidtess_api.exec_ocr() after a successful detection) then
    fails with an AssertionError under this project's pinned pymupdf==
    1.27.2.3, because that pseudo-document's page has no real PDF page
    object backing it. Converting to an actual (if temporary) PDF first
    sidesteps that entirely and is the simplest fix that keeps working
    regardless of the exact PyMuPDF version in use.

    Nothing is written to disk and the user's original file is never
    touched — the image is read and converted to PDF bytes fully in
    memory; there is no temporary file to clean up. The returned
    `pymupdf.Document` (image case only) is owned by the caller, which is
    responsible for closing it once to_markdown() has finished with it.
    """
    if src_path.suffix.lower() == ".pdf":
        return str(src_path)

    image_doc = pymupdf.open(str(src_path))
    try:
        pdf_bytes = image_doc.convert_to_pdf()
    finally:
        image_doc.close()
    return pymupdf.open("pdf", pdf_bytes)


# ── Operation prompts ──────────────────────────────────────────────────────
# CLAUDE.md is auto-loaded by the subprocess from the project root, so the
# prompt only needs to state the operation and request structured output markers.

# The Ingest prompt is split around the extracted Markdown block instead of
# being one .format() template (same reasoning as the Query prompt below):
# a research paper's extracted Markdown routinely contains literal "{" / "}"
# (LaTeX, code, JSON excerpts) which would raise KeyError if it were run
# through .format() together with the template. Only the header — which
# contains the sole {pdf_path} placeholder — is ever formatted; the Markdown
# itself is concatenated in verbatim.
_INGEST_PROMPT_HEADER = """\
EXECUTE INGEST OPERATION

Source document:
{pdf_path}

The source document has already been converted to Markdown via PyMuPDF4LLM \
before this session started. The Markdown below is the extracted content of \
the source document — treat it as the result of READ_SOURCE and use it \
directly for every content-generating state (READ_SOURCE, CREATE_SUMMARY, \
EXTRACT_CANDIDATE_ENTITIES, etc.) defined in docs/ingest.md.

Do NOT use a tool to open or re-read the PDF file for its content — the \
Markdown below is already the complete document. The PDF path above remains \
relevant only for duplicate detection and Source Registry bookkeeping during \
PRECHECK, exactly as specified in docs/ingest.md.

===EXTRACTED_DOCUMENT_MARKDOWN_START===
"""

_INGEST_PROMPT_FOOTER = """
===EXTRACTED_DOCUMENT_MARKDOWN_END===

The workflow defined in docs/ingest.md is authoritative.

Read docs/summary.md, docs/entity.md, and docs/markdown.md exactly once before generating any knowledge.

Execute the ingest workflow exactly as specified in docs/ingest.md.

Entity selection and relationship generation are separate decisions. Semantic relevance does not imply entity eligibility, and it does not imply relationship eligibility either. Entity creation (ENTITY_RESOLUTION, STATE 5) must be completed, based solely on Knowledge Worthiness Evaluation, before any relationship targeting that entity is generated — never create an entity merely because another page wants to link to it, and never let an already-drafted wikilink influence a CREATE decision. Before writing any wikilink or `related:` entry — in the summary or in any entity page — verify that the target is a member of the Persistent Entity Target Set (docs/entity.md): an entity page that actually exists in wiki/entities/ at that moment (or, for the summary's first pass during CREATE_SUMMARY, in wiki/index.md as loaded during PRECHECK). Never link to a rejected candidate, to a candidate merely considered for creation, or to a concept with no persistent entity page — describe it as ordinary text instead. Use the target's canonical filename, never its display title. Perform the Relationship Population step in STATE 6 before proceeding to STATE 7 — it only reads the final target set and writes links against it; it must never create a new entity.

Output each pipeline stage marker exactly as follows, with each marker on its own line when the corresponding state begins:

===WIKI_STAGE:PRECHECK===
===WIKI_STAGE:READ_SOURCE===
===WIKI_STAGE:CREATE_SUMMARY===
===WIKI_STAGE:EXTRACT_CANDIDATE_ENTITIES===
===WIKI_STAGE:ENTITY_RESOLUTION===
===WIKI_STAGE:UPDATE_ENTITIES===
===WIKI_STAGE:UPDATE_INDEX===
===WIKI_STAGE:UPDATE_LOG===
===WIKI_STAGE:COMPLETE===

After the workflow finishes, output exactly one result marker:

===WIKI_RESULT:SUCCESS===
===WIKI_RESULT:FAILED===
===WIKI_RESULT:ABORTED===
"""

# Query prompt is built at runtime (not as a .format() template) to avoid
# KeyError when the user's question contains literal curly braces.

_MAINTENANCE_PROMPT = """\
EXECUTE MAINTENANCE OPERATION

Scope: {scope}

Follow the Maintenance specification defined in docs/maintenance.md exactly.

When you BEGIN each pipeline state, output the corresponding marker alone on its own line:
===WIKI_STAGE:PRECHECK===
===WIKI_STAGE:SCAN===
===WIKI_STAGE:VALIDATION===
===WIKI_STAGE:QUALITY_ANALYSIS===
===WIKI_STAGE:REPORT===

After completing the analysis, output the maintenance report as valid JSON between:
===WIKI_REPORT_START===
{{
  "health": "HEALTHY",
  "validation": {{
    "Structure": "PASSED",
    "Metadata": "PASSED",
    "Relationships": "PASSED",
    "Source": "PASSED",
    "Knowledge": "PASSED",
    "Index": "PASSED",
    "Log": "PASSED"
  }},
  "issues": [],
  "recommendations": [],
  "warnings": 0,
  "critical": 0
}}
===WIKI_REPORT_END===

Then output:
===WIKI_RESULT:SUCCESS===

This is a read-only operation. Do NOT modify any wiki files.
Execute the complete Maintenance pipeline now.
"""


# ── Query follow-up detection ──────────────────────────────────────────────

_FOLLOW_UP_PRONOUNS = frozenset({"it", "they", "them", "those", "these"})
_FOLLOW_UP_PHRASES  = (
    "that approach", "those systems", "the relationship",
    "the approach", "the model", "the method",
)


def _detect_follow_up(question: str) -> bool:
    """Return True when the question contains references likely resolved by known entities."""
    q = question.lower()
    words = {w.strip("?.,!;:") for w in q.split()}
    return bool(words & _FOLLOW_UP_PRONOUNS) or any(p in q for p in _FOLLOW_UP_PHRASES)


# ── Base Worker ────────────────────────────────────────────────────────────

class BaseWorker(QThread):
    """Common signals and lifecycle helpers for all operation workers."""

    status_changed   = Signal(str)
    stage_changed    = Signal(str)
    log_appended     = Signal(str)
    tokens_updated   = Signal(int, int)
    elapsed_updated  = Signal(str)
    progress_updated = Signal(int)
    finished         = Signal(dict)
    error_occurred   = Signal(str)

    def __init__(self, project_root: Path, parent=None):
        super().__init__(parent)
        self._config = WorkspaceConfig(project_root)
        self._aborted = False
        self._start_time: float = 0.0
        self._process: ClaudeProcess | None = None

    def abort(self) -> None:
        self._aborted = True
        if self._process:
            self._process.kill()

    def _elapsed(self) -> str:
        secs = int(time.time() - self._start_time)
        m, s = divmod(secs, 60)
        return f"{m:02d}:{s:02d}"

    def _emit_log(self, msg: str) -> None:
        if msg.strip():
            ts = time.strftime("%H:%M:%S")
            self.log_appended.emit(f"{ts}  {msg}")


# ── Ingest Worker ──────────────────────────────────────────────────────────

class IngestWorker(BaseWorker):
    """
    Executes one Ingest operation for a single PDF document.

    Invokes the claude CLI with the Ingest prompt and allowed tools
    (Read, Write, Edit).  Emits stage markers as they arrive in stdout.
    """

    document_completed = Signal(str, str)   # (filename, result_code)

    def __init__(
        self,
        pdf_path: str,
        project_root: Path,
        model: str | None = None,
        parent=None,
    ):
        super().__init__(project_root, parent)
        self._pdf_path = pdf_path
        # Multi-Model Claude: CLI model alias ("sonnet"/"opus"/"haiku") for
        # this document's invocation, or None for the CLI's own default.
        # Read once here and never reassigned — the caller (IngestPage) is
        # responsible for keeping this the same value across an entire
        # batch (see gui/pages/ingest.py).
        self._model = model

    # ── Post-Ingest validation (read-only) ───────────────────────────────
    #
    # Reuses the exact same read-only validators Maintenance uses (see
    # gui/runtime/maintenance_engine.py) to check whether this specific
    # ingest run left the Persistent Memory inconsistent — Claude's own
    # SUCCESS marker only reflects what Claude believed it did during this
    # turn, not an independently verified on-disk state (docs/ingest.md's
    # "Atomic Operation"/"wiki SHALL NEVER remain partially updated"
    # invariant is a workflow instruction to Claude, not something this
    # Python layer previously verified). Snapshots are compared before vs.
    # after in run() so a pre-existing, unrelated issue elsewhere in the
    # wiki never fails an otherwise-clean new ingest — only issues newly
    # introduced by this run count. Limited to Structure/Metadata/
    # Relationship — Source is intentionally excluded here (a known,
    # pre-existing gap in sources: path-convention resolution, unrelated
    # to this check; see DIST_R9_BUILD_AND_REGRESSION_REPORT.md §17).
    # Read-only: only calls scan_scope()/validate() from
    # maintenance_engine.py, exactly what "Run Maintenance" would report
    # for this workspace — never writes anything, and never touches
    # wiki/log.md or any file Claude already wrote.
    _PM_VALIDATION_CATEGORIES = frozenset({"Structure", "Metadata", "Relationship"})

    def _snapshot_pm_issues(self) -> set[tuple[str, str, str, str]]:
        """Read-only snapshot of every Structure/Metadata/Relationship issue
        Maintenance's own validators currently detect in this workspace, as
        a set of (severity, category, file, description) tuples — Issue.id
        is excluded since it is only a per-call counter, not stable across
        two separate snapshots taken moments apart."""
        from .maintenance_engine import scan_scope, validate

        scan = scan_scope("Entire Wiki", self._config.root)
        vr = validate(scan)
        return {
            (issue.severity, issue.category, issue.file, issue.description)
            for issue in vr.issues
            if issue.category in self._PM_VALIDATION_CATEGORIES
        }

    def run(self) -> None:
        self._start_time = time.time()
        filename = Path(self._pdf_path).name
        result_code = "FAILED"
        # Read-only pre-ingest snapshot for the post-ingest consistency
        # check below; populated just before Claude starts writing (see
        # the ClaudeProcess construction further down). Stays an empty set
        # on any path that never reaches that point (e.g. a validation
        # failure in _fail_before_claude()), which is safe: the check that
        # uses it only ever runs when result_code == "SUCCESS", and that
        # can only happen after this point has been reached.
        pm_issues_before: set = set()

        # Reports a clear, specific failure that happened before the Claude
        # CLI was ever invoked (no prompt built, no subprocess spawned) —
        # mirrors the normal FAILED completion shape. Used by the input
        # validation checks below and by the preprocessing except-block, so
        # every "failed before Claude" path reports itself the same way.
        def _fail_before_claude(reason: str) -> None:
            self._emit_log(f"ERROR: {reason}")
            self.status_changed.emit("Finished")
            self.document_completed.emit(filename, "FAILED")
            self.finished.emit({
                "result":   "FAILED",
                "filename": filename,
                "duration": self._elapsed(),
                "tokens":   "—",
            })

        try:
            # Prefer a project-relative path in the prompt so it reads naturally
            try:
                pdf_rel = str(Path(self._pdf_path).relative_to(self._config.root))
            except ValueError:
                pdf_rel = self._pdf_path

            self.status_changed.emit("Running")
            self._emit_log(f"Starting ingest for: {filename}")

            src_path = Path(self._pdf_path)
            if not src_path.is_file():
                _fail_before_claude(f"Source document not found — {self._pdf_path}")
                return
            if src_path.suffix.lower() not in SOURCE_DOCUMENT_EXTENSIONS:
                _fail_before_claude(
                    f"Unsupported source format '{src_path.suffix or '(none)'}' — "
                    f"supported: {', '.join(SOURCE_DOCUMENT_EXTENSIONS)}"
                )
                return

            # Preprocess: extract the source document (PDF or image) to
            # Markdown in-memory via PyMuPDF4LLM before the Claude CLI is
            # ever invoked. The result is a plain string held only for the
            # lifetime of this call — nothing is written to disk
            # (write_images/embed_images default to False, so no image or
            # intermediate .md artifacts appear in the Workspace). Duplicate
            # detection (PRECHECK) is unaffected: it still runs against the
            # source path / Source Registry exactly as before, unchanged by
            # this step.
            #
            # The log lines emitted around this step are purely an audit
            # trail (routed through the same log_appended signal as every
            # other Execution Log line) so a user/developer can see that
            # preprocessing genuinely ran before Claude CLI communication
            # starts. They carry no control-flow meaning of their own.
            self._emit_log("Starting source document preprocessing using PyMuPDF4LLM...")
            try:
                # use_ocr=True enables PyMuPDF4LLM's automatic per-page OCR
                # selection (Revision 7/8): pages with no extractable text
                # layer are OCR'd, pages that already have one are left
                # untouched. force_ocr=False is required to keep this hybrid
                # behavior — True would force every page through OCR
                # regardless of whether it already has extractable text.
                # A PNG/JPG/JPEG image opens as a native 1-page PyMuPDF
                # document with no text layer, so it is routed through this
                # same per-page OCR selection automatically — no separate
                # code path is needed for images.
                #
                # ocr_function=guarded_ocr_function (Revision 8) runs
                # PyMuPDF4LLM's rapidtess_api adapter: RapidOCR performs text
                # *detection*, Tesseract performs text *recognition* — see
                # gui/runtime/ocr_none_guard.py. ocr_dpi=300 is the
                # rasterization DPI used only for the pages/images that
                # actually need OCR (benchmarked — see CLAUDE.md).
                # ocr_language="eng" matches LLM Wiki's English-only source
                # scope; passed explicitly even though it is also
                # PyMuPDF4LLM's own default, so this call keeps working the
                # same way if that default ever changes upstream.
                # Runtime OCR-backend diagnostic logging (Revision 8b):
                # attached only around this call, so every "llm_wiki.ocr"
                # log line gui/runtime/ocr_none_guard.py emits while
                # to_markdown() runs lands in the same Execution Log as
                # everything else here — proving, from the actual call
                # path, which backend ran OCR for which page. Removed
                # immediately after (finally below); never active while the
                # Claude CLI subprocess runs.
                ocr_logger = logging.getLogger("llm_wiki.ocr")
                ocr_handler = _OcrDiagnosticLogHandler(self._emit_log)
                ocr_logger.addHandler(ocr_handler)
                try:
                    md_input = _open_for_markdown(src_path)
                    try:
                        markdown = pymupdf4llm.to_markdown(
                            md_input,
                            use_ocr=True,
                            force_ocr=False,
                            ocr_dpi=300,
                            ocr_language="eng",
                            ocr_function=guarded_ocr_function,
                        )
                    finally:
                        # Only the image path returns an owned, temporary
                        # in-memory Document (see _open_for_markdown) — a PDF
                        # path returns the str unchanged, nothing to close here.
                        if isinstance(md_input, pymupdf.Document):
                            md_input.close()
                finally:
                    ocr_logger.removeHandler(ocr_handler)
            except Exception as extract_exc:
                _fail_before_claude(f"Source document preprocessing failed — {extract_exc}")
                return

            # Page count is purely informational for the log line below —
            # pymupdf4llm.to_markdown() doesn't return one, so it's read via
            # a lightweight pymupdf.open() (pymupdf is already a transitive
            # dependency of pymupdf4llm). Read-only; nothing is written to
            # disk, and this never affects duplicate detection or the prompt.
            page_count: int | None = None
            try:
                with pymupdf.open(self._pdf_path) as pdf_doc:
                    page_count = pdf_doc.page_count
            except Exception:
                pass   # informational only — omitted from the log if unavailable

            self._emit_log("PyMuPDF4LLM preprocessing completed")
            self._emit_log(f"  Characters : {len(markdown)}")
            self._emit_log(f"  Words      : {len(markdown.split())}")
            if page_count is not None:
                self._emit_log(f"  Pages      : {page_count}")

            prompt = (
                _INGEST_PROMPT_HEADER.format(pdf_path=pdf_rel)
                + markdown
                + _INGEST_PROMPT_FOOTER
            )
            self._process = ClaudeProcess(
                prompt=prompt,
                config=self._config,
                allowed_tools=["Read", "Write", "Edit"],
                model=self._model,
            )

            # Snapshot taken immediately before Claude can write anything —
            # see _snapshot_pm_issues() docstring above.
            pm_issues_before = self._snapshot_pm_issues()

            self._process.start()

            for line in self._process.iter_lines():
                if self._aborted:
                    self._process.kill()
                    break

                # Log every non-empty line that isn't a raw marker
                if line.strip() and not line.strip().startswith("===WIKI_"):
                    self._emit_log(line)

                stage = parse_stage(line)
                if stage:
                    self.log_appended.emit("")
                    self._emit_log(f"▶ {stage}")
                    self.stage_changed.emit(stage)

                res = parse_result(line)
                if res:
                    result_code = res
                    break

            self._process.wait()

        except Exception as exc:
            self._emit_log(f"ERROR: {exc}")

        if self._aborted:
            self.document_completed.emit(filename, "ABORTED")
            self.finished.emit({"result": "ABORTED", "filename": filename})
            return

        # Post-Ingest validation (read-only) — only when Claude itself
        # reported SUCCESS. Does not run for FAILED/ABORTED results, which
        # already aren't reported as a successful update. See
        # _snapshot_pm_issues() above for what this does and does not do.
        #
        # Structure/Metadata: diagnostic only — does NOT change result_code
        # (unchanged from the original Post-Ingest Validation design).
        #
        # Relationship: escalated to FAILED. A relationship (wikilink or
        # `related:` entry) pointing at a persistent entity that does not
        # exist is the specific semantic-integrity invariant docs/entity.md
        # § Relationship Rules and docs/summary.md § Related Entities
        # require — prompt/spec reinforcement alone cannot guarantee
        # compliance (Claude's own text generation is not deterministic),
        # so this is the "smallest safe integrity mechanism" backstop: it
        # does not roll back, edit, or repair any file Claude already
        # wrote (wiki/log.md keeps recording whatever Claude itself
        # concluded) — it only prevents the GUI/queue from reporting
        # SUCCESS when the on-disk result demonstrably violates the
        # invariant.
        if result_code == "SUCCESS":
            new_pm_issues = self._snapshot_pm_issues() - pm_issues_before
            if new_pm_issues:
                new_relationship_issues = {i for i in new_pm_issues if i[1] == "Relationship"}
                other_new_issues = new_pm_issues - new_relationship_issues

                if new_relationship_issues:
                    result_code = "FAILED"
                    count = len(new_relationship_issues)
                    noun = "issue" if count == 1 else "issues"
                    self._emit_log(
                        f"ERROR: Post-Ingest validation found {count} new relationship "
                        f"consistency {noun} (wikilink or related: target does not exist) "
                        "— result downgraded to FAILED. wiki/log.md is not modified; "
                        "Claude's own log entry for this run may still record SUCCESS."
                    )
                    for severity, category, file, description in sorted(new_relationship_issues):
                        self._emit_log(f"[{severity}] {category} — {file}:\n{description}")

                if other_new_issues:
                    count = len(other_new_issues)
                    noun = "issue" if count == 1 else "issues"
                    self._emit_log(
                        f"WARNING: Post-Ingest validation found {count} new "
                        f"Persistent Memory consistency {noun}."
                    )
                    for severity, category, file, description in sorted(other_new_issues):
                        self._emit_log(f"[{severity}] {category} — {file}:\n{description}")

        self.status_changed.emit("Finished")
        self.document_completed.emit(filename, result_code)
        self.finished.emit({
            "result": result_code,
            "filename": filename,
            "duration": self._elapsed(),
            "tokens": "—",
        })


# ── Query Worker ───────────────────────────────────────────────────────────

class QueryWorker(BaseWorker):
    """
    Executes one Query operation against the Persistent Memory.

    Invokes the claude CLI with the Query prompt (read-only: only the Read
    tool is allowed).  Tracks which wiki/entities/ files Claude actually
    succeeds at reading — a Read tool_use is only recorded once its matching
    tool_result confirms success, and the resulting "Entities Used" name is
    the page's own canonical `entity:` metadata, not the requested filename
    (see _resolve_entity_name()). The final assistant response becomes the
    answer. No output markers are parsed.
    """

    def __init__(
        self,
        question: str,
        working_memory: str,
        project_root: Path,
        model: str | None = None,
        parent=None,
    ):
        super().__init__(project_root, parent)
        self._question = question
        self._working_memory = working_memory
        # Multi-Model Claude: CLI model alias for this query's single
        # invocation, or None for the CLI's own default. See IngestWorker
        # above for the same convention.
        self._model = model

    def _resolve_entity_name(self, file_path: str) -> str | None:
        """Return the canonical `entity:` display name for a confirmed-read
        entity page, or None if that identity cannot be determined.

        Called only after a matching tool_result confirms the Read actually
        succeeded (see run()) — this does not decide success/failure itself,
        it only turns a known-good path into the right display string. The
        file is re-read directly (read-only) and parsed with the same
        frontmatter parser gui/data/wiki_loader.py already uses, so the
        result matches what the Entities page/Knowledge Graph would show for
        the same file. Falls back to the filename-derived name only via the
        exact same rule load_entities() already uses for entities missing an
        `entity:` field (meta.get("entity", stem.replace("_", " "))) — this
        is reuse of the existing, already-shipped fallback, not a new guess.
        Returns None (excluded from "Entities Used") only when the file
        cannot be read at all, e.g. removed between the confirmed Read and
        this lookup.
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self._config.root / path

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None

        meta, _ = _parse_frontmatter(content)
        name = meta.get("entity")
        if isinstance(name, str) and name.strip():
            return name.strip()
        return path.stem.replace("_", " ")

    def run(self) -> None:
        self._start_time = time.time()
        result_code = "FAILED"
        last_answer = ""
        entities: set[str] = set()
        # tool_use id -> file_path, for Read calls under /wiki/entities/ whose
        # outcome (success/failure) hasn't been confirmed by a tool_result yet.
        # Only entries that are later confirmed successful ever reach
        # `entities` — see the "user"/tool_result handling below. An entry
        # that never gets confirmed (e.g. the run is aborted first) simply
        # never becomes an entity, which is the safe default.
        pending_entity_reads: dict[str, str] = {}

        try:
            parts: list[str] = []

            # Follow-up status must be decided BEFORE anything is added to
            # the prompt. Working Memory (SESSION STATE: prior focus,
            # resolved entities) is only ever injected for a genuine
            # follow-up -- determined solely by the current question text
            # referencing prior context, never by Working Memory merely
            # being non-empty. This keeps every independent question a
            # clean Query state: no prior focus, entities, question, answer,
            # or operation context can leak into an unrelated query.
            is_follow_up = bool(self._working_memory) and _detect_follow_up(self._question)

            # Session state precedes the question so that resolved entities
            # and the current subject are loaded before Claude reads the
            # question text.  This allows pronouns and references ("it",
            # "that approach") to resolve immediately without backtracking.
            if is_follow_up:
                parts.append(self._working_memory)
                parts.append("")

            parts.append(self._question)
            parts.append("")

            if is_follow_up:
                parts.append(
                    "Consult docs/query.md to determine the retrieval workflow.\n"
                    "This question explicitly references previously resolved entities or prior "
                    "conversation context, so it qualifies as a genuine follow-up under docs/query.md.\n"
                    "Execution plan:\n"
                    "1. Read the resolved entity pages from Working Memory first.\n"
                    "2. If they provide sufficient evidence, answer immediately.\n"
                    "3. Otherwise read wiki/index.md to identify only the additional entity.\n"
                    "4. Generate the final answer only from retrieved wiki evidence.\n"
                    "5. Do not use Glob or workspace discovery."
                )
            else:
                parts.append(
                    "This is a new, independent question with no prior session context -- "
                    "no Working Memory, prior question, prior answer, or prior operation applies.\n"
                    "Consult docs/query.md to determine the retrieval workflow.\n"
                    "Follow the standard workflow starting fresh from wiki/index.md.\n"
                    "Generate the final answer only from evidence retrieved from the wiki.\n"
                    "Do not use Glob or workspace discovery."
                )

            parts.append(
                "\n\nIf, after retrieval, no supporting evidence for this question exists in the "
                "Persistent Memory, STOP immediately per the Failure Handling and Termination on "
                "Refusal rules in docs/query.md: state that the information is unavailable in the "
                "current Persistent Memory and, if appropriate, recommend ingesting relevant "
                "documents. Do not continue reasoning, generate illustrative examples, or answer "
                "from pretrained knowledge after that refusal -- the refusal is the final output."
            )

            prompt = "\n".join(parts)

            self._process = ClaudeProcess(
                prompt=prompt,
                config=self._config,
                allowed_tools=["Read"],
                model=self._model,
            )

            self.status_changed.emit("Running")
            self._emit_log("Starting query operation...")
            self._process.start()

            for event in self._process.iter_events():
                if self._aborted:
                    self._process.kill()
                    break

                etype = event.get("type", "")

                if etype == "assistant":

                    #
                    # Claude DevTools shows that assistant events contain
                    # content[] blocks directly (not message.content).
                    #

                    text_parts = []

                    for block in event.get("message", {}).get("content", []):

                        btype = block.get("type", "")

                        #
                        # Assistant text
                        #

                        if btype == "text":
                            text_parts.append(block.get("text", ""))

                        #
                        # Tool call
                        #

                        elif btype == "tool_use":

                            name = block.get("name", "")

                            inp = block.get("input", {})

                            file_path = (
                                inp.get("file_path")
                                or inp.get("path", "")
                                or ""
                            )

                            if file_path:
                                self._emit_log(f"  🔧 {name}: {file_path}")

                            if name == "Read" and file_path:

                                normalized = file_path.replace("\\", "/")

                                if "/wiki/entities/" in normalized:
                                    # Not recorded as "used" yet — only the
                                    # request is known so far. Recorded for
                                    # real once the matching tool_result
                                    # below confirms the Read succeeded.
                                    tool_id = block.get("id", "")
                                    if tool_id:
                                        pending_entity_reads[tool_id] = file_path

                    #
                    # Save the assistant answer
                    #

                    text = "\n".join(text_parts).strip()

                    if text:
                        last_answer = text

                elif etype == "user":

                    #
                    # Tool results (the CLI wraps them in a "user" event,
                    # same message.content shape as "assistant" above).
                    # This is the only place a Read's actual success/failure
                    # is known — confirm the matching pending entity Read
                    # here, and resolve its canonical name only now.
                    #

                    for block in event.get("message", {}).get("content", []):

                        if block.get("type") != "tool_result":
                            continue

                        tool_id = block.get("tool_use_id", "")

                        file_path = pending_entity_reads.pop(tool_id, None)

                        if file_path is None:
                            continue

                        if block.get("is_error", False):
                            continue

                        name = self._resolve_entity_name(file_path)

                        if name:
                            entities.add(name)

                elif etype == "result":

                    result_code = (
                        "FAILED"
                        if event.get("is_error", True)
                        else "SUCCESS"
                    )

                    break


                elif etype == "_text":

                    self._emit_log(event.get("text", ""))

            self._process.wait()

        except Exception as exc:
            self._emit_log(f"ERROR: {exc}")

        if self._aborted:
            self.finished.emit({"result": "ABORTED"})
            return

        focus = (
            self._question[:40] + "..."
            if len(self._question) > 40
            else self._question
        )

        entity_list = sorted(entities)

        self.status_changed.emit("Finished")
        self.finished.emit({
            "result":        result_code,
            "question":      self._question,
            "answer":        last_answer,
            "entities":      entity_list,
            "duration":      self._elapsed(),
            "tokens":        "—",
            "entities_used": len(entity_list),
            "focus":         focus,
        })


# ── Maintenance Worker ─────────────────────────────────────────────────────

class MaintenanceWorker(BaseWorker):
    """
    Executes one Maintenance operation against the Persistent Memory.

    Invokes the claude CLI with the Maintenance prompt (read-only).
    Parses the structured JSON report from the output.
    """

    def __init__(self, scope: str, project_root: Path, parent=None):
        super().__init__(project_root, parent)
        self._scope = scope

    def run(self) -> None:
        self._start_time = time.time()
        self.status_changed.emit("Running")
        self._emit_log("Starting maintenance operation...")

        try:
            from .maintenance_engine import scan_scope, validate, generate_report

            # Stage 1: Scan
            self.stage_changed.emit("SCAN")
            self._emit_log(f"▶ Scanning scope: {self._scope}")
            scan = scan_scope(self._scope, self._config.root)
            self._emit_log(
                f"  Found {len(scan.entity_files)} entity page(s), "
                f"{len(scan.summary_files)} summary page(s)."
            )

            if self._aborted:
                self.finished.emit({"result": "ABORTED"})
                return

            # Stage 2: Validate
            self.stage_changed.emit("VALIDATION")
            self._emit_log("▶ Running validation...")
            vr = validate(scan)
            self._emit_log(
                f"  Validation complete: {len(vr.issues)} issue(s) detected."
            )

            if self._aborted:
                self.finished.emit({"result": "ABORTED"})
                return

            # Stage 3: Report
            self.stage_changed.emit("REPORT")
            self._emit_log("▶ Generating Maintenance Report...")
            report = generate_report(vr, self._elapsed())

        except Exception as exc:
            self._emit_log(f"ERROR: {exc}")
            self.status_changed.emit("Finished")
            self.finished.emit({
                "result":             "FAILED",
                "overall_status":     "CRITICAL",
                "validation_summary": {},
                "detected_issues":    [{
                    "id":          "ISSUE-001",
                    "severity":    "CRITICAL",
                    "category":    "Structure",
                    "file":        "",
                    "description": f"Maintenance engine error: {exc}",
                }],
                "statistics": {
                    "scope":           self._scope,
                    "entity_pages":    0,
                    "summary_pages":   0,
                    "total_pages":     0,
                    "total_issues":    1,
                    "critical_issues": 1,
                    "warning_issues":  0,
                },
                "recommendations": [],
                "duration":           self._elapsed(),
                "health":             "CRITICAL",
                "validation":         {},
                "issues":             [],
                "warnings":           0,
                "critical":           1,
            })
            return

        self.status_changed.emit("Finished")
        self.finished.emit({"result": "SUCCESS", "duration": self._elapsed(), **report})
