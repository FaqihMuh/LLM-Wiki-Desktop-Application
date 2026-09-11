"""
Recommended Papers widget for the Entities Explorer.

A client-side, read-only visualization aid — the same category as the
Knowledge Graph — that suggests external arXiv papers related to the
selected entity. It never goes through the LLM Wiki Operating System and
never writes to the Workspace / Persistent Memory. wiki/index.md is only
*read* (via load_index(), already used elsewhere in the app) so that
papers already ingested are not recommended again.

Query strategy (progressive fallback, no AI/embedding/similarity — see
gui/runtime/arxiv_worker.py):
  1. Search using only the selected entity's name.
  2. If fewer than 5 results remain after excluding already-ingested
     papers, add the next related entity — ranked by Degree Centrality
     (the value already computed by EntityGraphWidget, reused here rather
     than recomputed) — combined with OR, and re-query.
  3. Repeat until 5 results are found or up to 3 related entities have
     been added.

Results are cached in memory for the lifetime of the running application
only (never written to disk), keyed by the exact term set used.

Public API:
  set_entity(entity, all_entities, degrees) — populate for one selection
"""

from __future__ import annotations

import html
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QVBoxLayout, QTextBrowser, QWidget
from shiboken6 import isValid

from ..config import WorkspaceConfig
from ..data.wiki_loader import load_index
from ..runtime.arxiv_worker import ArxivRecommendationWorker, normalize_arxiv_id

_MAX_RELATED_TERMS = 3
_TARGET_RESULTS    = 5
_FETCH_BATCH       = 8
_DEBOUNCE_MS       = 300
_CACHE_LIMIT       = 30
_ABSTRACT_LIMIT    = 240

_CSS = """
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 12px; color: #334155; margin: 0; padding: 14px 16px; }
p.muted { color: #64748b; }
p.error { color: #dc2626; }
p.attribution { color: #94a3b8; font-size: 10px; margin-top: 14px; }
.paper { border-top: 1px solid #e5e7eb; padding: 10px 0; }
.paper:first-of-type { border-top: none; padding-top: 0; }
a.title { color: #2563eb; font-weight: bold; font-size: 12.5px; text-decoration: none; }
a.title:hover { text-decoration: underline; }
.meta { color: #64748b; font-size: 11px; margin-top: 3px; }
.abstract { color: #475569; font-size: 11.5px; margin-top: 5px; line-height: 1.5; }
.why { margin-top: 6px; font-size: 11px; }
.why-label { color: #16a34a; font-weight: bold; }
.why ul { margin: 3px 0 0 18px; padding: 0; color: #16a34a; }
"""


# ---------------------------------------------------------------------------
# Related-entity resolution (filename -> display name), ranked by the
# Degree Centrality already computed by EntityGraphWidget._compute_layout().
#
# This duplicates that widget's small stem-matching helper locally by
# design, so gui/components/knowledge_graph.py stays completely untouched.
# ---------------------------------------------------------------------------

def _resolve_related_by_degree(
    entity: dict, all_entities: list[dict], degrees: list[int]
) -> list[str]:
    stem_to_idx: dict[str, int] = {}
    for i, e in enumerate(all_entities):
        stem = Path(e.get("filename", f"entity_{i}.md")).stem
        stem_to_idx[stem] = i
        stem_to_idx[stem.replace("_", " ")] = i

    scored: list[tuple[int, str]] = []
    seen: set[int] = set()
    for rel in entity.get("related", []):
        stem = Path(rel).stem if "." in rel else rel
        idx = stem_to_idx.get(stem)
        if idx is None or idx in seen:
            continue
        seen.add(idx)
        degree = degrees[idx] if idx < len(degrees) else 0
        name = all_entities[idx].get("name", "")
        if name:
            scored.append((degree, name))

    scored.sort(key=lambda t: -t[0])   # highest Degree Centrality first
    return [name for _, name in scored[:_MAX_RELATED_TERMS]]


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class RecommendedPapersWidget(QWidget):
    """Shows arXiv papers recommended for the currently selected entity."""

    def __init__(self, config: WorkspaceConfig, parent: QWidget | None = None):
        super().__init__(parent)
        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = QTextBrowser()
        self._view.setOpenExternalLinks(True)
        self._view.setMinimumHeight(220)
        self._view.setStyleSheet("QTextBrowser { border: none; background: white; }")
        self._view.document().setDefaultStyleSheet(_CSS)
        layout.addWidget(self._view)

        # In-memory only — discarded with the process, never written to
        # the Workspace. Same lifetime guarantee as the GUI's Working
        # Memory (docs/gui.md § Working Memory).
        self._cache: "OrderedDict[str, list[dict]]" = OrderedDict()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._run_pending)

        self._pending: tuple[str, list[str]] | None = None   # (name, related_terms)
        self._request_token = 0
        # Every ArxivRecommendationWorker in flight, keyed by identity (a
        # set, not a single slot) — see _run_pending(). A running QThread
        # must never lose its last Python reference before the thread has
        # actually finished (destroying/GC-ing a still-running QThread is
        # fatal in PySide6/Qt: confirmed by direct reproduction to be the
        # exact cause of the Qt6Core.dll@0x1cf68 crash — a single
        # self._worker slot, overwritten on every new selection, could drop
        # the previous worker's only reference while its network request
        # was still running). Entries are removed only once each worker's
        # own `finished` signal confirms it has actually completed.
        self._active_workers: set[ArxivRecommendationWorker] = set()

        self._render_idle()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_entity(self, entity: dict, all_entities: list[dict], degrees: list[int]) -> None:
        """Populate recommendations for the selected entity (debounced)."""
        name = entity.get("name", "")
        if not name:
            self._pending = None
            self._render_idle()
            return

        related_terms = _resolve_related_by_degree(entity, all_entities, degrees)
        self._pending = (name, related_terms)
        self._render_loading(name)
        self._debounce.start()   # restarting an already-running timer debounces rapid selection

    # ------------------------------------------------------------------
    # Fetch orchestration
    # ------------------------------------------------------------------

    def _run_pending(self) -> None:
        if self._pending is None:
            return
        name, related_terms = self._pending
        self._pending = None

        cache_key = "||".join([name] + related_terms)
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            self._render_results(name, related_terms, self._cache[cache_key])
            return

        self._request_token += 1
        token = str(self._request_token)

        worker = ArxivRecommendationWorker(
            request_token=token,
            entity_name=name,
            related_terms=related_terms,
            excluded_arxiv_ids=self._excluded_arxiv_ids(),
            target_count=_TARGET_RESULTS,
            fetch_batch=_FETCH_BATCH,
        )
        worker.finished_ok.connect(
            lambda tok, papers, key=cache_key, n=name, rt=related_terms:
                self._on_worker_ok(tok, papers, key, n, rt)
        )
        worker.failed.connect(self._on_worker_failed)
        # Keep this worker alive (referenced) until it reports itself done
        # — never cancelled, never terminated, left to finish normally even
        # if a newer selection has already superseded it (the existing
        # token check in _on_worker_ok/_on_worker_failed already discards a
        # stale result; this only prevents the QThread object itself from
        # being destroyed while still running). QThread.finished fires once
        # run() has actually returned, on every path (finished_ok emitted,
        # failed emitted, or an uncaught exception) — only then is it safe
        # to drop the reference.
        worker.finished.connect(lambda w=worker: self._active_workers.discard(w))
        self._active_workers.add(worker)
        worker.start()

    def _excluded_arxiv_ids(self) -> set[str]:
        """arXiv IDs already present in the Source Registry (wiki/index.md),
        read-only — so recommendations don't repeat papers already ingested."""
        try:
            index_rows = load_index(self._config.root)
        except Exception:
            return set()
        ids: set[str] = set()
        for row in index_rows:
            arxiv = row.get("arxiv", "")
            if arxiv and arxiv != "—":
                ids.add(normalize_arxiv_id(arxiv))
        return ids

    def _on_worker_ok(
        self, token: str, papers: list[dict], cache_key: str, name: str, related_terms: list[str]
    ) -> None:
        # A worker's finished_ok/failed signal is delivered via a queued
        # cross-thread connection, so it can still arrive after this widget
        # (and its child QTextBrowser) has already been destroyed — e.g.
        # the user navigated away from Entities while a request was still
        # in flight. self._active_workers (see _run_pending()) keeps the
        # worker itself alive until it finishes, which is what prevents the
        # native QThread-destroyed-while-running crash; it does not, and
        # should not, keep this widget alive. isValid() is the standard
        # PySide6/Shiboken way to detect that the underlying C++ object is
        # already gone before touching it.
        if not isValid(self):
            return
        if token != str(self._request_token):
            return   # stale — a newer selection has already superseded this request
        self._cache[cache_key] = papers
        if len(self._cache) > _CACHE_LIMIT:
            self._cache.popitem(last=False)
        self._render_results(name, related_terms, papers)

    def _on_worker_failed(self, token: str, message: str) -> None:
        if not isValid(self):
            return
        if token != str(self._request_token):
            return
        self._render_error(message)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _set_html(self, body: str) -> None:
        self._view.setHtml(f"<html><body>{body}</body></html>")

    def _render_idle(self) -> None:
        self._set_html('<p class="muted">Select an entity to see recommended papers.</p>')

    def _render_loading(self, name: str) -> None:
        self._set_html(
            f'<p class="muted">Searching arXiv for papers related to '
            f"<b>{html.escape(name)}</b>…</p>"
        )

    def _render_error(self, message: str) -> None:
        self._set_html(f'<p class="error">{html.escape(message)}</p>')

    def _render_results(self, name: str, related_terms: list[str], papers: list[dict]) -> None:
        if not papers:
            self._set_html(
                f'<p class="muted">No recommendations found for <b>{html.escape(name)}</b>.</p>'
            )
            return

        parts = [f'<p class="muted">Related to <b>{html.escape(name)}</b>']
        if related_terms:
            parts.append(
                " &middot; also considering: "
                + ", ".join(html.escape(t) for t in related_terms)
            )
        parts.append("</p>")

        for paper in papers:
            authors = paper.get("authors", [])
            author_line = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
            matched = paper.get("matched_keywords") or []
            why_html = ""
            if matched:
                items = "".join(f"<li>{html.escape(k)}</li>" for k in matched)
                why_html = (
                    '<div class="why"><span class="why-label">Why recommended '
                    f'— matched keywords:</span><ul>{items}</ul></div>'
                )
            parts.append(f"""
            <div class="paper">
              <a class="title" href="{html.escape(paper['url'])}">{html.escape(paper['title'])}</a>
              <div class="meta">{html.escape(author_line)} &middot; {html.escape(paper['year'])}
                &middot; arXiv:{html.escape(paper['arxiv_id'])}</div>
              <div class="abstract">{html.escape(_truncate(paper.get('summary', ''), _ABSTRACT_LIMIT))}</div>
              {why_html}
            </div>
            """)

        parts.append(
            '<p class="attribution">Source: arXiv.org &middot; external recommendations, '
            "not part of Persistent Memory.</p>"
        )
        self._set_html("".join(parts))
