"""
Maintenance Engine — read-only structural validator for the Persistent Memory.

Implements the workflow from docs/maintenance.md in three deterministic steps:
  1. scan_scope(scope, wiki_root)                → ScanResult
  2. validate(scan_result)                       → ValidationResult
  3. generate_report(validation_result, duration) → dict
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


# ── Constants ─────────────────────────────────────────────────────────────

VALID_SCOPES = frozenset({"Entire Wiki", "Entity Pages", "Summary Pages"})

VALID_ENTITY_TYPES = frozenset({
    "Framework", "Method", "Model", "Algorithm",
    "Paradigm", "Architecture", "Concept", "Organization",
})
VALID_STATUSES    = frozenset({"Experimental", "Emerging", "Established", "Deprecated"})
VALID_CONFIDENCES = frozenset({"Low", "Medium", "High"})

REQUIRED_ENTITY_FIELDS = (
    "entity", "type", "aliases", "status",
    "confidence", "last_updated", "sources", "related",
)

_ISO_DATE_RE    = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FILENAME_RE    = re.compile(r"^[A-Za-z0-9_]+\.md$")
_WIKILINK_RE    = re.compile(r"\[\[([^\]]+)\]\]")
_SOURCE_FILE_RE = re.compile(r"[Ss]ource\s+file[:\s]+`?(raw/[^\s`\n]+)`?")


# ── Data Structures ───────────────────────────────────────────────────────

@dataclass
class ScanResult:
    scope: str
    wiki_root: Path
    entity_files: list = field(default_factory=list)     # in-scope Path objects
    summary_files: list = field(default_factory=list)    # in-scope Path objects
    all_entity_stems: set = field(default_factory=set)   # complete reference universe
    all_summary_stems: set = field(default_factory=set)  # complete reference universe
    has_index: bool = False
    has_log: bool = False
    scan_error: str = ""


@dataclass
class Issue:
    id: str
    severity: str     # "CRITICAL" | "WARNING"
    category: str     # "Structure" | "Metadata" | "Relationship" | "Source"
    file: str
    description: str

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "severity":    self.severity,
            "category":    self.category,
            "file":        self.file,
            "description": self.description,
        }


@dataclass
class ValidationResult:
    scan: ScanResult
    categories: dict = field(default_factory=dict)  # category → "PASS"/"WARNING"/"FAIL"
    issues: list = field(default_factory=list)
    _counter: int = field(default=0, repr=False)

    def _add(self, severity: str, category: str, file: str, description: str) -> None:
        self._counter += 1
        self.issues.append(Issue(
            id=f"ISSUE-{self._counter:03d}",
            severity=severity,
            category=category,
            file=file,
            description=description,
        ))


# ── Step 1: Scan ──────────────────────────────────────────────────────────

def scan_scope(scope: str, wiki_root: Path) -> ScanResult:
    """
    Collect the set of files that belong to the requested scope.

    Always reads directory listings for both entities/ and summaries/ so that
    relationship validation has a complete reference universe regardless of scope.
    File content is never read here.
    """
    result = ScanResult(scope=scope, wiki_root=wiki_root)

    if scope not in VALID_SCOPES:
        result.scan_error = (
            f"Unsupported scope '{scope}'. "
            f"Valid scopes: {', '.join(sorted(VALID_SCOPES))}."
        )
        return result

    wiki_dir     = wiki_root / "wiki"
    entities_dir = wiki_dir / "entities"
    summaries_dir = wiki_dir / "summaries"

    if not wiki_dir.is_dir():
        result.scan_error = f"wiki/ directory not found at {wiki_dir}."
        return result

    # Collect entity listings
    if entities_dir.is_dir():
        all_entity = sorted(entities_dir.glob("*.md"))
        result.all_entity_stems = {f.stem for f in all_entity}
        if scope in ("Entire Wiki", "Entity Pages"):
            result.entity_files = all_entity

    # Collect summary listings
    if summaries_dir.is_dir():
        all_summary = sorted(summaries_dir.glob("*.md"))
        result.all_summary_stems = {f.stem for f in all_summary}
        if scope in ("Entire Wiki", "Summary Pages"):
            result.summary_files = all_summary

    if scope == "Entire Wiki":
        result.has_index = (wiki_dir / "index.md").is_file()
        result.has_log   = (wiki_dir / "log.md").is_file()

    return result


# ── Step 2: Validate ──────────────────────────────────────────────────────

def validate(scan: ScanResult) -> ValidationResult:
    """
    Run all four validation categories against the scan result.

    Every category is always executed regardless of other outcomes.
    """
    vr = ValidationResult(scan=scan)

    if scan.scan_error:
        for cat in ("Structure", "Metadata", "Relationship", "Source"):
            vr.categories[cat] = "FAIL"
        vr._add("CRITICAL", "Structure", "", scan.scan_error)
        return vr

    _validate_structure(vr)
    _validate_metadata(vr)
    _validate_relationships(vr)
    _validate_sources(vr)

    return vr


def _result_for(vr: ValidationResult, category: str) -> str:
    issues = [i for i in vr.issues if i.category == category]
    if any(i.severity == "CRITICAL" for i in issues):
        return "FAIL"
    if any(i.severity == "WARNING" for i in issues):
        return "WARNING"
    return "PASS"


# ── Structure Validation ──────────────────────────────────────────────────

def _validate_structure(vr: ValidationResult) -> None:
    scan     = vr.scan
    wiki_dir = scan.wiki_root / "wiki"
    scope    = scan.scope

    if scope in ("Entire Wiki", "Entity Pages"):
        if not (wiki_dir / "entities").is_dir():
            vr._add("CRITICAL", "Structure", "wiki/entities/",
                    "Required directory wiki/entities/ does not exist.")

    if scope in ("Entire Wiki", "Summary Pages"):
        if not (wiki_dir / "summaries").is_dir():
            vr._add("CRITICAL", "Structure", "wiki/summaries/",
                    "Required directory wiki/summaries/ does not exist.")

    if scope == "Entire Wiki":
        if not scan.has_index:
            vr._add("WARNING", "Structure", "wiki/index.md",
                    "wiki/index.md does not exist.")
        if not scan.has_log:
            vr._add("WARNING", "Structure", "wiki/log.md",
                    "wiki/log.md does not exist.")

    for f in scan.entity_files + scan.summary_files:
        if not _FILENAME_RE.match(f.name):
            vr._add("WARNING", "Structure", f"wiki/{f.parent.name}/{f.name}",
                    f"Filename '{f.name}' does not follow the expected convention "
                    "(only letters, digits, and underscores allowed before .md).")

    for files, dir_label in (
        (scan.entity_files,  "entities"),
        (scan.summary_files, "summaries"),
    ):
        seen: dict = {}
        for f in files:
            key = f.stem.lower()
            if key in seen:
                vr._add("CRITICAL", "Structure", f"wiki/{dir_label}/{f.name}",
                        f"Duplicate file (case-insensitive): '{f.name}' "
                        f"conflicts with '{seen[key]}'.")
            else:
                seen[key] = f.name

    vr.categories["Structure"] = _result_for(vr, "Structure")


# ── Front Matter Parser ───────────────────────────────────────────────────

def _parse_frontmatter(path: Path) -> tuple:
    """
    Extract YAML front matter from a markdown file without an external library.

    Handles the specific format used by entity pages: scalar strings and flat
    string lists only. Returns (meta_dict, body_text) or (None, full_text).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None, ""

    if not text.startswith("---\n"):
        return None, text

    end = text.find("\n---", 4)
    if end == -1:
        return None, text

    yaml_block = text[4:end]

    rest_start = end + 4  # skip "\n---"
    if rest_start < len(text) and text[rest_start] == "\n":
        rest_start += 1
    body = text[rest_start:]

    meta = _parse_simple_yaml(yaml_block)
    return meta, body


def _parse_simple_yaml(block: str) -> dict:
    """Parse scalar-and-list YAML front matter into a dict.

    Supports the same YAML forms as gui/data/wiki_loader.py's
    _parse_frontmatter() (kept as a separate, independent implementation
    here since the two modules already had separate hand-rolled parsers
    — this fixes both in place rather than merging them into shared
    code): inline scalar (`key: value`), inline flow list (`key: []`,
    `key: [a, b]`), block list (`key:\\n  - a\\n  - b`), and folded plain
    scalar (`key:\\n  value`). A top-level key is identified by being
    unindented — this is what disambiguates a new key line from an
    indented continuation/list line that happens to contain a colon.
    """
    result: dict = {}
    lines = block.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        if line[:1].isspace() or ":" not in line:
            i += 1  # stray/malformed line outside any key context — skip
            continue

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        if value:
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                result[key] = [] if not inner else [v.strip() for v in inner.split(",")]
            else:
                result[key] = value
            i += 1
            continue

        # Empty inline value — look ahead at the indented lines that
        # follow to decide between a block list and a folded plain
        # scalar (or, if there is no continuation at all, an empty list).
        j = i + 1
        list_items: list = []
        scalar_parts: list = []
        is_list = False
        while j < n:
            nxt = lines[j].rstrip()
            if not nxt.strip():
                j += 1
                continue
            if not nxt[:1].isspace():
                break  # next top-level key — stop looking ahead
            nxt_stripped = nxt.strip()
            if nxt_stripped.startswith("- "):
                is_list = True
                list_items.append(nxt_stripped[2:].strip())
            elif nxt_stripped == "-":
                is_list = True
                list_items.append("")
            elif is_list:
                break  # non-dash line inside a list block — malformed, stop
            else:
                scalar_parts.append(nxt_stripped)
            j += 1

        if is_list:
            result[key] = list_items
        elif scalar_parts:
            result[key] = " ".join(scalar_parts)
        else:
            result[key] = []
        i = j

    return result


# ── Metadata Validation ───────────────────────────────────────────────────

def _validate_metadata(vr: ValidationResult) -> None:
    for path in vr.scan.entity_files:
        rel  = f"wiki/entities/{path.name}"
        meta, _ = _parse_frontmatter(path)

        if meta is None:
            vr._add("CRITICAL", "Metadata", rel,
                    "Entity page is missing YAML front matter.")
            continue

        for fname in REQUIRED_ENTITY_FIELDS:
            if fname not in meta:
                vr._add("WARNING", "Metadata", rel,
                        f"Missing required metadata field: '{fname}'.")

        etype = meta.get("type", "")
        if etype and etype not in VALID_ENTITY_TYPES:
            vr._add("WARNING", "Metadata", rel,
                    f"Invalid entity type '{etype}'. "
                    f"Allowed: {', '.join(sorted(VALID_ENTITY_TYPES))}.")

        status = meta.get("status", "")
        if status and status not in VALID_STATUSES:
            vr._add("WARNING", "Metadata", rel,
                    f"Invalid status '{status}'. "
                    f"Allowed: {', '.join(sorted(VALID_STATUSES))}.")

        confidence = meta.get("confidence", "")
        if confidence and confidence not in VALID_CONFIDENCES:
            vr._add("WARNING", "Metadata", rel,
                    f"Invalid confidence '{confidence}'. "
                    f"Allowed: {', '.join(sorted(VALID_CONFIDENCES))}.")

        last_updated = str(meta.get("last_updated", ""))
        if last_updated and not _ISO_DATE_RE.match(last_updated):
            vr._add("WARNING", "Metadata", rel,
                    f"last_updated '{last_updated}' does not match ISO-8601 "
                    "date format (YYYY-MM-DD).")

        aliases = meta.get("aliases")
        if aliases is not None and not isinstance(aliases, list):
            vr._add("WARNING", "Metadata", rel,
                    f"'aliases' must be a list, got {type(aliases).__name__}.")

    for path in vr.scan.summary_files:
        rel = f"wiki/summaries/{path.name}"
        try:
            path.read_text(encoding="utf-8")
        except OSError as exc:
            vr._add("CRITICAL", "Metadata", rel,
                    f"Cannot read summary file: {exc}.")

    vr.categories["Metadata"] = _result_for(vr, "Metadata")


# ── Relationship Validation ───────────────────────────────────────────────

def _validate_relationships(vr: ValidationResult) -> None:
    scan = vr.scan
    all_valid_stems = scan.all_entity_stems | scan.all_summary_stems

    for path in scan.entity_files:
        rel  = f"wiki/entities/{path.name}"
        meta, body = _parse_frontmatter(path)

        # related: field must reference existing entity pages
        if meta:
            related = meta.get("related") or []
            if isinstance(related, list):
                for ref in related:
                    stem = str(ref).removesuffix(".md")
                    if stem not in scan.all_entity_stems:
                        vr._add("WARNING", "Relationship", rel,
                                f"related: references '{ref}' which does not "
                                "exist in wiki/entities/.")

        # [[wikilinks]] in body may reference entity or summary pages
        for link in _WIKILINK_RE.findall(body or ""):
            stem = link.removesuffix(".md")
            if stem not in all_valid_stems:
                vr._add("WARNING", "Relationship", rel,
                        f"Wikilink [[{link}]] does not resolve to "
                        "any known entity or summary page.")

        # Orphan: no sources and no related links
        if meta:
            sources = meta.get("sources") or []
            related = meta.get("related") or []
            if not sources and not related:
                vr._add("WARNING", "Relationship", rel,
                        "Entity page has no sources and no related entities "
                        "(orphan page).")

    for path in scan.summary_files:
        rel = f"wiki/summaries/{path.name}"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for link in _WIKILINK_RE.findall(text):
            stem = link.removesuffix(".md")
            if stem not in all_valid_stems:
                vr._add("WARNING", "Relationship", rel,
                        f"Wikilink [[{link}]] does not resolve to "
                        "any known entity or summary page.")

    vr.categories["Relationship"] = _result_for(vr, "Relationship")


# ── Source Validation ─────────────────────────────────────────────────────

def _resolve_source_path(wiki_root: Path, wiki_dir: Path, src: str) -> Path | None:
    """Resolve a `sources:` entry to an existing summary file.

    Real entity pages observed in practice use three different, all
    otherwise-reasonable conventions for this field — docs/entity.md's
    "sources" field never specified which:
      1. bare summary filename, e.g. "BERT.md" (relative to wiki/summaries/)
      2. full wiki-relative path, e.g. "wiki/summaries/BERT.md" (relative
         to the workspace root)
      3. a (possibly quoted) [[Name]] wikilink to the summary page's
         display name, e.g. '"[[BERT]]"' -> BERT.md

    The original implementation (`wiki_dir / str(src)`) resolved none of
    these correctly, so every reference failed validation regardless of
    whether the target file existed. Tries every candidate and accepts
    the first that exists; still reports a warning if none do — a
    genuinely missing file remains an issue.
    """
    src = src.strip()
    candidates = [wiki_dir / "summaries" / src, wiki_root / src]

    unquoted = src.strip('"').strip("'")
    if unquoted.startswith("[[") and unquoted.endswith("]]"):
        name = unquoted[2:-2].strip()
        if name and not name.endswith(".md"):
            name += ".md"
        if name:
            candidates.append(wiki_dir / "summaries" / name)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _validate_sources(vr: ValidationResult) -> None:
    scan     = vr.scan
    wiki_dir = scan.wiki_root / "wiki"

    for path in scan.entity_files:
        rel  = f"wiki/entities/{path.name}"
        meta, _ = _parse_frontmatter(path)
        if not meta:
            continue

        sources = meta.get("sources") or []
        if isinstance(sources, list):
            for src in sources:
                if _resolve_source_path(scan.wiki_root, wiki_dir, str(src)) is None:
                    vr._add("WARNING", "Source", rel,
                            f"sources: references '{src}' which does not exist.")

    for path in scan.summary_files:
        rel = f"wiki/summaries/{path.name}"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw_ref in _SOURCE_FILE_RE.findall(text):
            raw_path = scan.wiki_root / raw_ref
            if not raw_path.is_file():
                vr._add("WARNING", "Source", rel,
                        f"References source file '{raw_ref}' which does not "
                        "exist in raw/.")

    vr.categories["Source"] = _result_for(vr, "Source")


# ── Step 3: Generate Report ───────────────────────────────────────────────

def generate_report(vr: ValidationResult, duration: str) -> dict:
    """
    Produce the Maintenance Report dict from a completed ValidationResult.

    Health Score is intentionally omitted per project requirements.
    Overall Status is derived from validation category results.
    """
    cats = vr.categories

    if any(v == "FAIL" for v in cats.values()):
        overall_status = "CRITICAL"
    elif any(v == "WARNING" for v in cats.values()):
        overall_status = "WARNING"
    else:
        overall_status = "HEALTHY"

    scan = vr.scan
    critical_count = sum(1 for i in vr.issues if i.severity == "CRITICAL")
    warning_count  = sum(1 for i in vr.issues if i.severity == "WARNING")

    validation_summary = dict(cats)

    statistics = {
        "scope":           scan.scope,
        "entity_pages":    len(scan.entity_files),
        "summary_pages":   len(scan.summary_files),
        "total_pages":     len(scan.entity_files) + len(scan.summary_files),
        "total_issues":    len(vr.issues),
        "critical_issues": critical_count,
        "warning_issues":  warning_count,
    }

    # Recommendations are generated only when issues exist (spec §Recommendations)
    _REC_TEXT = {
        "Structure": (
            "Review the wiki directory structure. Ensure required directories "
            "and files exist and filenames follow the expected convention."
        ),
        "Metadata": (
            "Review entity page YAML front matter. Ensure all required fields "
            "are present and values match the allowed sets."
        ),
        "Relationship": (
            "Review wikilinks and related fields. Manually resolve broken "
            "references — do not modify wiki files automatically."
        ),
        "Source": (
            "Review source references in entity pages and summaries. Verify "
            "every referenced file exists in wiki/summaries/ or raw/."
        ),
    }

    recommendations: list = []
    for cat in ("Structure", "Metadata", "Relationship", "Source"):
        cat_issues = [i for i in vr.issues if i.category == cat]
        if cat_issues:
            ids = ", ".join(i.id for i in cat_issues)
            recommendations.append(f"[{ids}] {_REC_TEXT[cat]}")

    issue_dicts = [i.to_dict() for i in vr.issues]

    return {
        # Report keys (spec §Maintenance Report)
        "overall_status":     overall_status,
        "validation_summary": validation_summary,
        "detected_issues":    issue_dicts,
        "statistics":         statistics,
        "recommendations":    recommendations,
        "duration":           duration,
        # GUI compatibility aliases (expected by gui/pages/maintenance.py)
        "health":             overall_status,
        "validation":         validation_summary,
        "issues":             issue_dicts,
        "warnings":           warning_count,
        "critical":           critical_count,
    }
