"""
Wiki data loader — reads Persistent Memory from wiki/ and raw/ directories.
All functions are read-only.
"""

import os
import re
from datetime import datetime
from pathlib import Path

from ..config import SOURCE_DOCUMENT_EXTENSIONS


def _iter_raw_files(raw_dir: Path):
    """Yield every raw/ file whose extension is a supported source document
    format (PDF or image) — single source of truth in gui/config.py, shared
    with the Ingest file picker so the Raw Documents listing/counts always
    match what Ingest can actually accept."""
    for ext in SOURCE_DOCUMENT_EXTENSIONS:
        yield from raw_dir.glob(f"*{ext}")


# ---------------------------------------------------------------------------
# YAML frontmatter parser (no external dependencies)
# ---------------------------------------------------------------------------

def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content.
    Returns (metadata_dict, remaining_body).

    Supports the following valid YAML forms actually produced by Ingest
    across observed entity/summary pages — a top-level key (unindented,
    the only thing that starts a new field; this is what disambiguates a
    key line from an indented continuation/list line that happens to
    contain a colon):
      - inline scalar:      key: value
      - inline flow list:   key: []            key: [a, b, c]
      - block list:         key:\\n  - a\\n  - b
      - folded plain scalar: key:\\n  value      (YAML's own scalar-folds-
                              to-next-line form; multiple continuation
                              lines are joined with a single space, same
                              as standard YAML plain scalar folding)
    An empty inline value with no continuation lines at all (key: followed
    immediately by another key, or end of block) yields an empty list —
    unchanged from the previous behavior for that specific edge case.
    """
    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    yaml_text = content[3:end].strip()
    body = content[end + 4:].strip()

    meta: dict = {}
    lines = yaml_text.split("\n")
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        stripped = line.rstrip()
        if not stripped.strip():
            i += 1
            continue

        # Only an unindented line with a colon starts a new key — this is
        # what lets us tell a key line apart from an indented continuation
        # or list-item line (which may itself contain a colon).
        if line[:1].isspace() or ":" not in stripped:
            i += 1  # stray/malformed line outside any key context — skip
            continue

        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()

        if val:
            # Inline value on the same line as the key.
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                meta[key] = [] if not inner else [v.strip() for v in inner.split(",")]
            else:
                meta[key] = val
            i += 1
            continue

        # Empty inline value — look ahead at the indented lines that
        # follow to decide between a block list and a folded plain
        # scalar (or, if there is no continuation at all, an empty list).
        j = i + 1
        list_items: list[str] = []
        scalar_parts: list[str] = []
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
            meta[key] = list_items
        elif scalar_parts:
            meta[key] = " ".join(scalar_parts)
        else:
            meta[key] = []
        i = j

    return meta, body


# ---------------------------------------------------------------------------
# Markdown table parser
# ---------------------------------------------------------------------------

def _parse_md_table(text: str) -> list[dict]:
    """Parse a GitHub-style markdown table into list of row dicts."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if len(lines) < 3:
        return []

    headers = [h.strip() for h in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        if not line or set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # Strip markdown links from cells: [text](url) → text
        cells = [re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', c) for c in cells]
        if len(cells) >= len(headers):
            rows.append(dict(zip(headers, cells[:len(headers)])))
    return rows


# ---------------------------------------------------------------------------
# Raw documents
# ---------------------------------------------------------------------------

def load_raw_documents(project_root: Path) -> list[dict]:
    """Scan raw/ for supported source documents (PDF/PNG/JPG/JPEG) and
    return file metadata."""
    raw_dir = project_root / "raw"
    if not raw_dir.exists():
        return []

    docs = []
    for f in sorted(_iter_raw_files(raw_dir)):
        stat = f.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
        size_mb = stat.st_size / (1024 * 1024)
        docs.append({
            "filename": f.name,
            "path": str(f),
            "pages": "—",
            "size": f"{size_mb:.1f} MB",
            "status": "Available",
            "modified": mtime,
        })
    return docs


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

def load_entities(project_root: Path) -> list[dict]:
    """Parse all entity markdown files and return metadata + body."""
    entities_dir = project_root / "wiki" / "entities"
    if not entities_dir.exists():
        return []

    entities = []
    for f in sorted(entities_dir.glob("*.md")):
        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue

        meta, body = _parse_frontmatter(content)
        name = meta.get("entity", f.stem.replace("_", " "))
        entities.append({
            "filename": f.name,
            "path": str(f),
            "name": name,
            "type": meta.get("type", ""),
            "status": meta.get("status", ""),
            "confidence": meta.get("confidence", ""),
            "last_updated": meta.get("last_updated", ""),
            "aliases": meta.get("aliases", []),
            "sources": meta.get("sources", []),
            "related": meta.get("related", []),
            "body": body,
            "raw_content": content,
        })
    return entities


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def load_summaries(project_root: Path) -> list[dict]:
    """Parse all summary markdown files."""
    summaries_dir = project_root / "wiki" / "summaries"
    if not summaries_dir.exists():
        return []

    summaries = []
    for f in sorted(summaries_dir.glob("*.md")):
        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue

        meta, body = _parse_frontmatter(content)

        # Source file from YAML frontmatter
        source = meta.get("source_file", "")

        # First H1 heading is the title (search body only, after frontmatter)
        title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else f.stem.replace("_", " ")

        # Extract topic from body heuristics
        topic = _guess_topic(body)

        # Count related entities from [[Entity_Name]] refs in body
        entity_refs = re.findall(r"\[\[([^\]]+)\]\]", body)
        entity_count = len(set(entity_refs))

        # Modification date
        stat = f.stat()
        updated = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")

        # Strip the H1 title line so the viewer doesn't render it twice
        body_content = body[title_match.end():].lstrip("\n") if title_match else body

        summaries.append({
            "filename": f.name,
            "path": str(f),
            "title": title,
            "topic": topic,
            "entities": str(entity_count) if entity_count else "—",
            "entity_refs": list(set(entity_refs)),
            "source": source,
            "updated": updated,
            "raw_content": body_content,
        })
    return summaries


def _guess_topic(content: str) -> str:
    """Heuristic topic extraction from summary content."""
    lower = content.lower()
    if "agent memory" in lower or "agent-native" in lower:
        return "Agent Memory"
    if "retrieval as reasoning" in lower or "self-evolving" in lower:
        return "Reasoning"
    if "vector rag" in lower or "rag" in lower:
        return "Retrieval"
    return "AI Research"


# ---------------------------------------------------------------------------
# Knowledge Index (Source Registry)
# ---------------------------------------------------------------------------

def load_index(project_root: Path) -> list[dict]:
    """Parse wiki/index.md and extract the Source Registry table."""
    index_path = project_root / "wiki" / "index.md"
    if not index_path.exists():
        return []

    try:
        content = index_path.read_text(encoding="utf-8")
    except OSError:
        return []

    # Find the Source Registry section
    registry_match = re.search(
        r"##\s+Source Registry\s*\n(.*?)(?:\n##|\Z)", content, re.DOTALL
    )
    if not registry_match:
        return []

    table_text = registry_match.group(1).strip()
    rows = _parse_md_table(table_text)

    # Normalise column names
    normalized = []
    for row in rows:
        normalized.append({
            "title": row.get("Title", ""),
            "arxiv": row.get("arXiv ID", row.get("arXiv", "")),
            "filename": row.get("Filename", ""),
            "summary_page": row.get("Summary Page", ""),
            "entities": row.get("Entities", row.get("Entity Count", "")),
            "ingest_date": row.get("Ingest Date", ""),
            "status": "Indexed",
        })
    return normalized


def load_index_raw(project_root: Path) -> str:
    """Return raw content of wiki/index.md."""
    index_path = project_root / "wiki" / "index.md"
    try:
        return index_path.read_text(encoding="utf-8")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Operation Log
# ---------------------------------------------------------------------------

def load_log_entries(project_root: Path) -> list[dict]:
    """Parse wiki/log.md and extract individual log entries."""
    log_path = project_root / "wiki" / "log.md"
    if not log_path.exists():
        return []

    try:
        content = log_path.read_text(encoding="utf-8")
    except OSError:
        return []

    entries = []
    # Split by H2 headings (each log entry starts with ## Ingest — <date>)
    blocks = re.split(r"(?=^##\s+)", content, flags=re.MULTILINE)
    for block in blocks:
        block = block.strip()
        if not block or block.startswith("# "):
            continue
        entry = _parse_log_entry(block)
        if entry:
            entries.append(entry)

    return entries  # log.md keeps newest entries at the top


def _parse_log_entry(block: str) -> dict | None:
    """Parse a single log entry block into a dict.

    The log format uses headings like:
        ## 2026-06-26T00:00:00Z — Ingest
    and list items with bold keys like:
        - **Document:** Title text here
        - **Source file:** raw/file.pdf
        - **Result:** SUCCESS   (or ### Result\\nSUCCESS for longer entries)
        - **Total Duration:** ~71s
    """
    heading_match = re.match(r"^##\s+(.+)$", block, re.MULTILINE)
    if not heading_match:
        return None

    heading = heading_match.group(1).strip()

    # Heading format: "TIMESTAMP — OPERATION" (em-dash U+2014 or en-dash U+2013)
    ts_op = re.match(r"^(.+?)\s*[—–]\s*(.+)$", heading)
    if ts_op:
        timestamp = ts_op.group(1).strip()
        operation = ts_op.group(2).strip()
    else:
        timestamp = heading
        operation = "Ingest"

    # **Document:** value  (colon is inside the bold span in this log format)
    doc_match = re.search(
        r"\*\*Document(?:\s+Title)?:?\*\*:?\s*(.+?)(?:\n|$)", block
    )
    document = doc_match.group(1).strip() if doc_match else heading

    # **Source file:** value
    src_match = re.search(
        r"\*\*Source(?:\s+file)?:?\*\*:?\s*(.+?)(?:\n|$)", block, re.IGNORECASE
    )
    source = src_match.group(1).strip() if src_match else ""

    # Result: may appear as "- **Result:** SUCCESS" or under "### Result\nSUCCESS"
    result = "SUCCESS"
    inline_result = re.search(
        r"\*\*Result:?\*\*:?\s*(SUCCESS|FAILED|ABORTED)", block
    )
    if inline_result:
        result = inline_result.group(1)
    else:
        section_result = re.search(
            r"###\s+Result\s*\n+\s*(SUCCESS|FAILED|ABORTED)", block
        )
        if section_result:
            result = section_result.group(1)

    # **Total Duration:** value  — strip any trailing bold markers
    dur_match = re.search(
        r"\*\*Total Duration:?\*\*:?\s*(.+?)(?:\n|$)", block, re.IGNORECASE
    )
    duration = "—"
    if dur_match:
        duration = dur_match.group(1).strip().lstrip("*").strip()

    # Token total (numeric values only)
    tok_match = re.search(r"(?i)Total Tokens?[:\s]+([0-9,]+)", block)
    tokens = "—"
    if tok_match:
        t = tok_match.group(1).replace(",", "")
        tokens = f"{int(t):,}" if t.isdigit() else t

    return {
        "timestamp": timestamp,
        "operation": operation,
        "document": document,
        "source": source,
        "result": result,
        "duration": duration,
        "tokens": tokens,
        "raw_block": block,
    }


# ---------------------------------------------------------------------------
# Convenience: wiki statistics
# ---------------------------------------------------------------------------

def load_wiki_stats(project_root: Path) -> dict:
    """Return high-level wiki statistics for the Home page.

    Home only needs file *counts*, not parsed content, so raw/entities/
    summaries are counted via plain filesystem enumeration instead of
    load_raw_documents()/load_entities()/load_summaries() — those would
    read (and, for entities/summaries, fully parse) every file just to
    throw the result away. load_index() is kept as-is: the Indexed
    Sources count genuinely requires reading the Source Registry table
    in wiki/index.md, and that file is small.
    """
    raw_dir = project_root / "raw"
    entities_dir = project_root / "wiki" / "entities"
    summaries_dir = project_root / "wiki" / "summaries"

    raw_count = sum(1 for _ in _iter_raw_files(raw_dir)) if raw_dir.exists() else 0
    entities_count = sum(1 for _ in entities_dir.glob("*.md")) if entities_dir.exists() else 0
    summaries_count = sum(1 for _ in summaries_dir.glob("*.md")) if summaries_dir.exists() else 0
    index_entries = load_index(project_root)

    return {
        "raw_documents": raw_count,
        "entities": entities_count,
        "summaries": summaries_count,
        "indexed": len(index_entries),
    }
