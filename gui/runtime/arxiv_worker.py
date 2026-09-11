"""
arXiv Recommended Papers background worker.

Fetches recommended papers for a selected Entity from the public arXiv API
(https://info.arxiv.org/help/api/index.html) in a background QThread, so
network I/O never blocks the GUI thread — the same pattern already used by
IngestWorker/QueryWorker/MaintenanceWorker in gui/runtime/worker.py.

This is intentionally NOT a BaseWorker subclass: BaseWorker's shape (a
ClaudeProcess subprocess, abort()-by-kill, stage markers) is specific to
invoking the `claude` CLI for an LLM Wiki Operating System operation.
Recommended Papers is a client-side visualization aid for the Entities
Explorer (the same category as the Knowledge Graph) — it never goes
through the Operating System and never touches the Workspace / Persistent
Memory. This module has no filesystem access at all; the caller is
responsible for reading wiki/index.md (read-only) to decide which arXiv
IDs to exclude as already ingested.

Query strategy — progressive fallback, no AI / embedding / similarity:
  1. Search using only the selected entity's name.
  2. If fewer than `target_count` results remain (after excluding already
     -ingested papers), add the next related entity — already ranked by
     Degree Centrality by the caller — combined with OR, and re-query.
  3. Repeat until `target_count` results are found or every related term
     has been added.

"Why recommended" is answered deterministically: for each paper, which of
the query terms actually appear (case-insensitive substring) in its title
or abstract — plain text containment, not a model or a score.
"""

from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import certifi
from PySide6.QtCore import QThread, Signal

_API_URL = "http://export.arxiv.org/api/query"
_USER_AGENT = "LLM-Wiki-Desktop/1.0 (Knowledge Explorer - Recommended Papers)"
_TIMEOUT_SECS = 10
_ATOM_NS = "{http://www.w3.org/2005/Atom}"

# Built once and reused for every request (SSLContext is safe to share
# across concurrent connections/threads once configured). Python's stdlib
# ssl module does not automatically trust the same CA bundle Windows/other
# tools use, which made every HTTPS request (arXiv redirects http -> https)
# fail with SSLCertVerificationError: unable to get local issuer
# certificate — not a connectivity problem. Pointing the context at
# certifi's bundled CA file restores standard, verified TLS (verification
# stays fully enabled; this is not ssl._create_unverified_context()).
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

_VERSION_SUFFIX = re.compile(r"v\d+$")


def normalize_arxiv_id(raw: str) -> str:
    """Strip a trailing version suffix, e.g. '1706.03762v7' -> '1706.03762'."""
    return _VERSION_SUFFIX.sub("", raw.strip())


def _phrase(term: str) -> str:
    return f'all:"{term}"'


def _build_query(terms: list[str]) -> str:
    """terms[0] (the selected entity) is always required (AND); any further
    terms (related entities) are combined with OR, keeping recall wide
    enough that the progressive fallback in fetch_recommendations() can
    still find results without narrowing too aggressively."""
    if len(terms) == 1:
        return _phrase(terms[0])
    related_clause = " OR ".join(_phrase(t) for t in terms[1:])
    return f"{_phrase(terms[0])} AND ({related_clause})"


def _entry_text(entry, tag: str) -> str:
    el = entry.find(f"{_ATOM_NS}{tag}")
    return (el.text or "").strip() if el is not None else ""


def _parse_entry(entry) -> dict | None:
    raw_id = _entry_text(entry, "id")   # e.g. http://arxiv.org/abs/1706.03762v7
    if not raw_id:
        return None
    short_id = raw_id.rsplit("/", 1)[-1]
    arxiv_id = normalize_arxiv_id(short_id)

    title = re.sub(r"\s+", " ", _entry_text(entry, "title")).strip()
    summary = re.sub(r"\s+", " ", _entry_text(entry, "summary")).strip()
    published = _entry_text(entry, "published")
    year = published[:4] if len(published) >= 4 else "—"

    authors = []
    for author_el in entry.findall(f"{_ATOM_NS}author"):
        name_el = author_el.find(f"{_ATOM_NS}name")
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    return {
        "arxiv_id": arxiv_id,
        "title": title or "(untitled)",
        "authors": authors,
        "year": year,
        "summary": summary,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
    }


def fetch_arxiv(terms: list[str], max_results: int) -> list[dict]:
    """One arXiv API call for the given term set. Raises on network/parse
    failure — the caller (worker thread) is responsible for catching."""
    query = _build_query(terms)
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    })
    req = urllib.request.Request(
        f"{_API_URL}?{params}",
        headers={"User-Agent": _USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECS, context=_SSL_CONTEXT) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    papers = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        paper = _parse_entry(entry)
        if paper is not None:
            papers.append(paper)
    return papers


def matched_keywords(paper: dict, terms: list[str]) -> list[str]:
    """Deterministic 'Why Recommended' evidence: which of the query terms
    literally appear in this paper's title/abstract. Plain case-insensitive
    substring containment — no AI, no scoring."""
    haystack = f"{paper.get('title', '')} {paper.get('summary', '')}".lower()
    return [t for t in terms if t.lower() in haystack]


class ArxivRecommendationWorker(QThread):
    """
    Runs the progressive-fallback arXiv search for one entity selection.

    Signals:
      finished_ok(str, list)  — (request_token, list[dict]) on success
      failed(str, str)        — (request_token, user-facing error message)

    `request_token` is echoed back unchanged so the caller can detect and
    discard a stale result (the user already selected a different entity
    before this fetch completed) without needing to kill the thread.
    """

    finished_ok = Signal(str, list)
    failed      = Signal(str, str)

    def __init__(
        self,
        request_token: str,
        entity_name: str,
        related_terms: list[str],
        excluded_arxiv_ids: set[str],
        target_count: int = 5,
        fetch_batch: int = 8,
        parent=None,
    ):
        super().__init__(parent)
        self._token = request_token
        self._entity_name = entity_name
        self._related_terms = related_terms
        self._excluded = excluded_arxiv_ids
        self._target_count = target_count
        self._fetch_batch = fetch_batch

    def run(self) -> None:
        try:
            candidates: dict[str, dict] = {}   # arxiv_id -> paper (+ matched_keywords)
            terms = [self._entity_name]

            for step in range(len(self._related_terms) + 1):
                if step > 0:
                    terms = [self._entity_name] + self._related_terms[:step]

                results = fetch_arxiv(terms, self._fetch_batch)

                for paper in results:
                    if paper["arxiv_id"] in self._excluded:
                        continue
                    if paper["arxiv_id"] in candidates:
                        continue   # keep the first (most relevant) match's term set
                    paper["matched_keywords"] = matched_keywords(paper, terms)
                    candidates[paper["arxiv_id"]] = paper

                if len(candidates) >= self._target_count:
                    break

            ordered = list(candidates.values())[: self._target_count]
            self.finished_ok.emit(self._token, ordered)

        except (urllib.error.URLError, TimeoutError, OSError):
            self.failed.emit(
                self._token,
                "Recommendations unavailable — check your internet connection.",
            )
        except ET.ParseError:
            self.failed.emit(
                self._token,
                "Recommendations unavailable — could not read the arXiv response.",
            )
        except Exception:
            self.failed.emit(self._token, "Recommendations unavailable.")
