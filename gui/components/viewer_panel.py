"""
Scrollable viewer panel that renders structured content as HTML.
Used in Knowledge Explorer pages to display selected item details.
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QTextBrowser, QWidget
from PySide6.QtCore import Qt


_BASE_CSS = """
body {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #334155;
    line-height: 1.8;
    margin: 0;
    padding: 20px;
}
h1 { font-size: 20px; color: #1e293b; margin-bottom: 16px; }
h2 { font-size: 16px; color: #1e293b; margin-top: 20px; margin-bottom: 10px; }
h3 { font-size: 14px; color: #1e293b; margin-top: 18px; margin-bottom: 8px; }
h4 { font-size: 13px; color: #0f172a; margin-bottom: 6px; }
p  { margin: 0 0 10px; }
ul { margin: 0 0 10px 20px; }
li { margin-bottom: 6px; }
strong { color: #1e293b; }
.meta-grid {
    display: table;
    width: 100%;
    margin-bottom: 20px;
}
.meta-row { display: table-row; }
.meta-cell {
    display: table-cell;
    width: 50%;
    padding: 6px 0;
    vertical-align: top;
}
.meta-key { color: #64748b; font-size: 11px; font-weight: bold; text-transform: uppercase; }
.meta-val { color: #1e293b; font-size: 13px; margin-top: 2px; }
.tag {
    display: inline-block;
    background: #eff6ff;
    color: #2563eb;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 11px;
    margin: 2px 4px 2px 0;
}
.placeholder {
    color: #94a3b8;
    font-style: italic;
}
"""


def _meta_grid(pairs: list[tuple[str, str]]) -> str:
    """Render a 2-column metadata grid.

    Values are expected to be plain scalar strings — the actual fix for
    that is the frontmatter parser (gui/data/wiki_loader.py). The
    isinstance check below is only a last-resort display guard so an
    unexpected non-string value (e.g. a stray list) never leaks into the
    page as a raw Python literal; it does not change behavior for the
    well-formed strings the parser now produces.
    """
    rows_html = ""
    for i in range(0, len(pairs), 2):
        cells = ""
        for j in range(2):
            if i + j < len(pairs):
                key, val = pairs[i + j]
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                cells += (
                    f'<td class="meta-cell">'
                    f'<div class="meta-key">{key}</div>'
                    f'<div class="meta-val">{val or "—"}</div>'
                    f'</td>'
                )
        rows_html += f'<tr class="meta-row">{cells}</tr>'
    return f'<table class="meta-grid"><tbody>{rows_html}</tbody></table>'


def _ul(items: list[str]) -> str:
    if not items:
        return '<p class="placeholder">None</p>'
    lis = "".join(f"<li>{i}</li>" for i in items)
    return f"<ul>{lis}</ul>"


class ViewerPanel(QFrame):
    """
    HTML viewer for selected knowledge objects.
    Call show_document(), show_summary(), etc. to populate.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.setStyleSheet("QFrame { background: white; border: none; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setStyleSheet("QTextBrowser { border: none; background: white; }")
        self._browser.document().setDefaultStyleSheet(_BASE_CSS)
        layout.addWidget(self._browser)

        self._show_placeholder()

    # ------------------------------------------------------------------

    def _render(self, html_body: str) -> None:
        self._browser.setHtml(f"<html><body>{html_body}</body></html>")

    def _show_placeholder(self) -> None:
        self._render('<p class="placeholder">Select an item to view details.</p>')

    # ------------------------------------------------------------------
    # Raw document viewer
    # ------------------------------------------------------------------

    def show_document(self, info: dict) -> None:
        meta = _meta_grid([
            ("Filename", info.get("filename", "")),
            ("Size", info.get("size", "—")),
            ("Status", info.get("status", "Available")),
            ("Modified", info.get("modified", "")),
        ])
        html = f"<h2>{info.get('filename', 'Document')}</h2>{meta}"
        html += "<h3>Location</h3><p>raw/" + info.get("filename", "") + "</p>"
        self._render(html)

    # ------------------------------------------------------------------
    # Summary viewer
    # ------------------------------------------------------------------

    def show_summary(self, info: dict) -> None:
        meta = _meta_grid([
            ("Topic", info.get("topic", "")),
            ("Source", info.get("source", "")),
            ("Entities", info.get("entities", "0")),
            ("Updated", info.get("updated", "")),
        ])
        title = info.get("title", "Summary")
        html = f"<h1>{title}</h1>{meta}"

        # Render body markdown-lite
        body = info.get("raw_content", "")
        if body:
            html += _md_to_html(body)
        else:
            html += '<p class="placeholder">No content available.</p>'

        self._render(html)

    # ------------------------------------------------------------------
    # Entity viewer
    # ------------------------------------------------------------------

    def show_entity(self, info: dict) -> None:
        meta = _meta_grid([
            ("Type", info.get("type", "")),
            ("Status", info.get("status", "")),
            ("Confidence", info.get("confidence", "")),
            ("Last Updated", info.get("last_updated", "")),
        ])
        # Defensive-only fallback (see _meta_grid's docstring): the parser
        # is the actual fix and should always hand back a non-empty
        # string here. If it ever doesn't, fall back to the filename
        # (traceable to the real file) rather than a generic label that
        # would quietly hide which entity this is.
        name = info.get("name", "")
        if not isinstance(name, str) or not name.strip():
            name = info.get("filename", "Entity")
        html = f"<h2>{name}</h2>{meta}"

        aliases = info.get("aliases", [])
        if aliases:
            html += "<h3>Aliases</h3>" + _ul(aliases if isinstance(aliases, list) else [aliases])

        related = info.get("related", [])
        if related:
            html += "<h3>Related Entities</h3>" + _ul(related if isinstance(related, list) else [related])

        sources = info.get("sources", [])
        if sources:
            html += "<h3>Sources</h3>" + _ul(sources if isinstance(sources, list) else [sources])

        body = info.get("body", "")
        if body:
            html += _md_to_html(body)

        self._render(html)

    # ------------------------------------------------------------------
    # Knowledge Index viewer
    # ------------------------------------------------------------------

    def show_index_entry(self, info: dict) -> None:
        meta = _meta_grid([
            ("arXiv ID", info.get("arxiv", "")),
            ("Filename", info.get("filename", "")),
            ("Summary Page", info.get("summary_page", "")),
            ("Entity Count", info.get("entities", "")),
            ("Ingest Date", info.get("ingest_date", "")),
            ("Status", info.get("status", "Indexed")),
        ])
        title = info.get("title", "Registry Entry")
        html = f"<h2>{title}</h2>{meta}"
        if info.get("filename"):
            html += f"<h3>Source File</h3><p>raw/{info['filename']}</p>"
        self._render(html)

    # ------------------------------------------------------------------
    # Operation Log viewer
    # ------------------------------------------------------------------

    def show_log_entry(self, info: dict) -> None:
        meta = _meta_grid([
            ("Timestamp", info.get("timestamp", "")),
            ("Result", info.get("result", "")),
            ("Document", info.get("document", "")),
            ("Source", info.get("source", "")),
        ])
        html = f"<h2>{info.get('operation', 'Operation')}</h2>{meta}"

        # Parse raw block for pipeline and timing if available
        raw = info.get("raw_block", "")
        if raw:
            html += _md_to_html(raw)
        else:
            html += f"<h3>Duration</h3><p>{info.get('duration', '—')}</p>"
            html += f"<h3>Tokens</h3><p>{info.get('tokens', '—')}</p>"

        self._render(html)

    # ------------------------------------------------------------------
    # Query result viewer
    # ------------------------------------------------------------------

    def show_query_result(self, answer: str) -> None:
        if answer:
            self._browser.setMarkdown(answer)
        else:
            self._render('<p class="placeholder">No answer received.</p>')

    def show_html(self, html: str) -> None:
        """Render arbitrary HTML content."""
        self._render(html)

    def show_error(self, message: str) -> None:
        self._render(
            f"<p style='color:#dc2626;'><strong>Error:</strong> {message}</p>"
        )

    def clear(self) -> None:
        self._show_placeholder()


# ---------------------------------------------------------------------------
# Lightweight markdown → HTML converter
# ---------------------------------------------------------------------------

def _md_to_html(md: str) -> str:
    """Convert a subset of markdown to HTML for display in QTextBrowser."""
    import re

    lines = md.split("\n")
    html_lines = []
    in_ul = False
    in_code = False
    in_table = False
    code_buf: list[str] = []
    table_buf: list[str] = []

    def _flush_table(buf: list[str]) -> str:
        """Render accumulated table lines as an HTML table."""
        if not buf:
            return ""
        # First non-separator line is the header
        header_cells = [c.strip() for c in buf[0].strip("|").split("|")]
        th = "".join(f"<th>{c}</th>" for c in header_cells)
        rows_html = f"<thead><tr>{th}</tr></thead><tbody>"
        for row_line in buf[2:]:           # skip header + separator
            if not row_line.strip():
                continue
            cells = [c.strip() for c in row_line.strip("|").split("|")]
            # Inline formatting inside cells
            cells = [re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', c) for c in cells]
            cells = [re.sub(r'\*(.+?)\*', r'<em>\1</em>', c) for c in cells]
            cells = [re.sub(r'`(.+?)`', r'<code>\1</code>', c) for c in cells]
            td = "".join(f"<td>{c}</td>" for c in cells)
            rows_html += f"<tr>{td}</tr>"
        rows_html += "</tbody>"
        return (
            "<table style='border-collapse:collapse;width:100%;margin:12px 0;'>"
            + rows_html
            + "</table>"
        )

    def _is_table_row(line: str) -> bool:
        return "|" in line and line.strip().startswith("|")

    for line in lines:
        # Code block
        if line.startswith("```"):
            if in_code:
                html_lines.append(
                    "<pre style='background:#f1f5f9;padding:10px;border-radius:8px;"
                    "font-family:Consolas,monospace;font-size:12px;'>"
                    + "\n".join(code_buf)
                    + "</pre>"
                )
                code_buf = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_buf.append(line)
            continue

        # Table detection
        if _is_table_row(line):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            in_table = True
            table_buf.append(line)
            continue

        if in_table:
            html_lines.append(_flush_table(table_buf))
            table_buf = []
            in_table = False

        # Close open list if needed
        if in_ul and not line.startswith("- ") and line.strip():
            html_lines.append("</ul>")
            in_ul = False

        # Headings
        if line.startswith("### "):
            html_lines.append(f"<h3>{line[4:].strip()}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:].strip()}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{line[2:].strip()}</h1>")
        # List item
        elif line.startswith("- "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            content = line[2:].strip()
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            html_lines.append(f"<li>{content}</li>")
        # Horizontal rule
        elif line.strip() == "---":
            html_lines.append("<hr style='border:none;border-top:1px solid #e5e7eb;margin:16px 0;'>")
        # Blank line
        elif not line.strip():
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append("")
        # Paragraph
        else:
            text = line.strip()
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
            text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
            html_lines.append(f"<p>{text}</p>")

    # Flush any open blocks at end of input
    if in_table:
        html_lines.append(_flush_table(table_buf))
    if in_ul:
        html_lines.append("</ul>")

    return "\n".join(html_lines)
