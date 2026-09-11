"""
Native PySide6 Knowledge Graph widget with interactive nodes.

Nodes:
  - Draggable (edges update in real time)
  - Selectable (single selection, click to select / click again to deselect)
  - Selected node is highlighted with a bright ring
  - Directly connected nodes stay at full opacity
  - Unrelated nodes are faded
  - Sized by Entity Representation (%) — Degree Centrality relative to the
    entity with the most connections, computed from the existing `related`
    relationships already parsed from wiki/entities/*.md. Purely visual;
    no new data, algorithm, or storage is involved.
  - Hovering a node shows a tooltip (name, type, connections, representation)

Canvas:
  - Mouse wheel zooms in/out, centered on the cursor
  - Dragging empty canvas space pans the view
  - reset_view() restores the default zoom/pan

Signals:
  node_selected(int)  — emitted with the entity index on selection change
                        (not emitted when selection is cleared)

Public API:
  set_entities(list[dict])       — populate from wiki entity list
  select_node_silent(int)        — select without emitting node_selected
  reset_view()                   — reset zoom/pan to the default view
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget, QToolTip
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QCursor,
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TYPE_COLORS: dict[str, str] = {
    "Concept":   "#3b82f6",
    "Method":    "#16a34a",
    "Framework": "#7c3aed",
    "Paradigm":  "#ca8a04",
}
_DEFAULT_COLOR = "#64748b"

_LEGEND = list(_TYPE_COLORS.items()) + [("Unknown", _DEFAULT_COLOR)]


def _safe_type(entity: dict) -> str:
    """Return entity['type'] coerced to a hashable string.

    The actual fix for malformed `type` values is the frontmatter parser
    (gui/data/wiki_loader.py), which now always hands back a plain
    string. This is only a local defensive guard — `type` is used as a
    dict key below (_TYPE_COLORS.get(...)) and in a set comprehension,
    both of which raise TypeError for an unhashable value like a stray
    list; coercing it here prevents that without changing layout, node
    size, opacity, or hit-testing in any way.
    """
    t = entity.get("type", "")
    return t if isinstance(t, str) else ""

_DRAG_THRESHOLD = 6       # pixels before a press becomes a drag
_LEGEND_H      = 24       # pixels reserved at bottom for legend
_NODE_R_RATIO  = 0.048    # base node radius as fraction of min(width, draw_height)
_LAYOUT_RADIUS = 0.36     # circular layout radius (relative coords)
_MARGIN_FACTOR = 2.8      # margin = max node radius * this factor

# Node size range driven by Entity Representation (%) — Degree Centrality
# relative to the most-connected entity. 0% representation (an isolated
# entity) still renders at _MIN_NODE_SCALE of the base radius so it stays
# visible and clickable; 100% (the most-connected entity) renders at
# _MAX_NODE_SCALE. Kept close to 1.0 so the graph stays proportional and
# readable rather than producing extreme size differences.
_MIN_NODE_SCALE = 0.65
_MAX_NODE_SCALE = 1.6

# Zoom range and per-wheel-notch step for the canvas view transform.
_ZOOM_MIN  = 0.4
_ZOOM_MAX  = 3.0
_ZOOM_STEP = 1.15


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class EntityGraphWidget(QWidget):
    """Interactive entity relationship graph rendered with QPainter."""

    node_selected = Signal(int)   # entity index in _entities list

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(340)
        self.setStyleSheet("background: white; border-radius: 10px;")
        # Tracking is needed (not just during clicks/drags) so hovering a
        # node can show a tooltip without requiring a mouse button to be held.
        self.setMouseTracking(True)

        # Data
        self._entities: list[dict] = []
        self._positions: list[tuple[float, float]] = []   # relative [0,1]
        self._edges: list[tuple[int, int]] = []
        self._adjacency: list[set[int]] = []              # per-node neighbour sets
        self._degrees: list[int] = []                     # Degree Centrality per node
        self._representation: list[float] = []             # Entity Representation (%), 0-100

        # Interaction state
        self._selected: int | None = None
        self._drag_node: int | None = None
        self._drag_started: bool = False
        self._press_pos: QPointF = QPointF()
        self._drag_offset_rx: float = 0.0
        self._drag_offset_ry: float = 0.0

        # Canvas view state (zoom / pan) — purely visual, does not affect
        # node positions, edges, or any underlying data.
        self._zoom: float = 1.0
        self._pan: QPointF = QPointF(0.0, 0.0)
        # (pan-at-press, mouse-pos-at-press) while a canvas pan may be in
        # progress; None whenever the press started on a node instead.
        self._pan_start: tuple[QPointF, QPointF] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_entities(self, entities: list[dict]) -> None:
        """Populate the graph from the entity list returned by load_entities()."""
        self._entities = entities
        self._selected = None
        self._compute_layout()
        self.update()

    def select_node_silent(self, idx: int) -> None:
        """Select a node without emitting node_selected (used for table → graph sync)."""
        if idx != self._selected and 0 <= idx < len(self._entities):
            self._selected = idx
            self.update()

    def clear_selection(self) -> None:
        if self._selected is not None:
            self._selected = None
            self.update()

    def reset_view(self) -> None:
        """Reset zoom and pan to the default view. Node positions are unaffected."""
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self.update()

    # ------------------------------------------------------------------
    # Layout computation
    # ------------------------------------------------------------------

    def _compute_layout(self) -> None:
        n = len(self._entities)
        if n == 0:
            self._positions = []
            self._edges = []
            self._adjacency = []
            self._degrees = []
            self._representation = []
            return

        # filename stem → index map
        stem_to_idx: dict[str, int] = {}
        for i, e in enumerate(self._entities):
            stem = Path(e.get("filename", f"entity_{i}.md")).stem
            stem_to_idx[stem] = i
            stem_to_idx[stem.replace("_", " ")] = i

        # Circular positions (start from top: −π/2)
        r = _LAYOUT_RADIUS
        self._positions = [
            (0.5 + r * math.cos(2 * math.pi * i / n - math.pi / 2),
             0.5 + r * math.sin(2 * math.pi * i / n - math.pi / 2))
            for i in range(n)
        ]

        # Edges (undirected, deduplicated)
        seen: set[tuple[int, int]] = set()
        self._edges = []
        self._adjacency = [set() for _ in range(n)]
        for i, entity in enumerate(self._entities):
            for rel in entity.get("related", []):
                stem = Path(rel).stem if "." in rel else rel
                j = stem_to_idx.get(stem)
                if j is not None and j != i:
                    edge = (min(i, j), max(i, j))
                    if edge not in seen:
                        seen.add(edge)
                        self._edges.append(edge)
                    self._adjacency[i].add(j)
                    self._adjacency[j].add(i)

        # Entity Representation (%) — Degree Centrality: each entity's
        # connection count relative to the entity with the most connections.
        # Uses only the adjacency already derived from the `related` field
        # above; no new data source, no additional algorithm.
        self._degrees = [len(adj) for adj in self._adjacency]
        max_degree = max(self._degrees) if self._degrees else 0
        self._representation = [
            (d / max_degree * 100.0) if max_degree > 0 else 0.0
            for d in self._degrees
        ]

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _node_radius(self) -> float:
        """Base node radius (before per-node representation scaling)."""
        w, h = self.width(), self.height()
        draw_h = h - _LEGEND_H
        return min(w, draw_h) * _NODE_R_RATIO

    def _node_radius_for(self, i: int) -> float:
        """
        Per-node radius scaled by Entity Representation (%) — i.e. Degree
        Centrality relative to the most-connected entity. Purely visual:
        does not affect layout, edges, or any stored data.
        """
        base = self._node_radius()
        rep = self._representation[i] if i < len(self._representation) else 0.0
        scale = _MIN_NODE_SCALE + (rep / 100.0) * (_MAX_NODE_SCALE - _MIN_NODE_SCALE)
        return base * scale

    def _to_px(self, rx: float, ry: float) -> QPointF:
        w, h = self.width(), self.height()
        draw_h = h - _LEGEND_H
        # Margin sized for the largest possible node so it never clips.
        r = self._node_radius() * _MAX_NODE_SCALE
        mx, my = r * _MARGIN_FACTOR, r * _MARGIN_FACTOR
        return QPointF(
            mx + rx * (w - 2 * mx),
            my + ry * (draw_h - 2 * my),
        )

    def _to_rel(self, px: float, py: float) -> tuple[float, float]:
        w, h = self.width(), self.height()
        draw_h = h - _LEGEND_H
        r = self._node_radius() * _MAX_NODE_SCALE
        mx, my = r * _MARGIN_FACTOR, r * _MARGIN_FACTOR
        rx = (px - mx) / max(w - 2 * mx, 1)
        ry = (py - my) / max(draw_h - 2 * my, 1)
        return rx, ry

    def _find_node_at(self, px: float, py: float) -> int | None:
        """Return the index of the node whose visual circle contains (px, py).

        (px, py) are in unscaled canvas coordinates — the same space used by
        _to_px()/_to_rel() — i.e. already converted from screen coordinates
        via _screen_to_world() when called from a mouse event.
        """
        for i, (rx, ry) in enumerate(self._positions):
            node_px = self._to_px(rx, ry)
            hit_r = self._node_radius_for(i) * 1.4     # slightly larger hit area
            if math.hypot(px - node_px.x(), py - node_px.y()) <= hit_r:
                return i
        return None

    def _screen_to_world(self, pos: QPointF) -> QPointF:
        """Map a widget-space mouse position to unscaled canvas coordinates,
        inverting the pan/zoom transform applied in paintEvent()."""
        return QPointF(
            (pos.x() - self._pan.x()) / self._zoom,
            (pos.y() - self._pan.y()) / self._zoom,
        )

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        self._press_pos = pos
        self._drag_started = False
        self._pan_start = None

        world = self._screen_to_world(pos)
        self._drag_node = self._find_node_at(world.x(), world.y())

        if self._drag_node is not None:
            node_rx, node_ry = self._positions[self._drag_node]
            mouse_rx, mouse_ry = self._to_rel(world.x(), world.y())
            self._drag_offset_rx = node_rx - mouse_rx
            self._drag_offset_ry = node_ry - mouse_ry
        else:
            # Nothing under the cursor — a subsequent drag pans the canvas
            # (see mouseMoveEvent) instead of moving a node. A plain click
            # (no drag) still falls through to deselect, as before.
            self._pan_start = (QPointF(self._pan), pos)

        event.accept()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()

        # ---- Node drag (unchanged behaviour) ----
        if self._drag_node is not None:
            if not self._drag_started:
                dx = abs(pos.x() - self._press_pos.x())
                dy = abs(pos.y() - self._press_pos.y())
                if dx + dy >= _DRAG_THRESHOLD:
                    self._drag_started = True
                    QToolTip.hideText()

            if self._drag_started:
                world = self._screen_to_world(pos)
                mouse_rx, mouse_ry = self._to_rel(world.x(), world.y())
                rx = max(0.05, min(0.95, mouse_rx + self._drag_offset_rx))
                ry = max(0.05, min(0.95, mouse_ry + self._drag_offset_ry))
                self._positions[self._drag_node] = (rx, ry)
                self.update()
            event.accept()
            return

        # ---- Canvas pan ----
        if self._pan_start is not None:
            if not self._drag_started:
                dx = abs(pos.x() - self._press_pos.x())
                dy = abs(pos.y() - self._press_pos.y())
                if dx + dy >= _DRAG_THRESHOLD:
                    self._drag_started = True
                    QToolTip.hideText()
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)

            if self._drag_started:
                start_pan, start_pos = self._pan_start
                self._pan = QPointF(
                    start_pan.x() + (pos.x() - start_pos.x()),
                    start_pan.y() + (pos.y() - start_pos.y()),
                )
                self.update()
            event.accept()
            return

        # ---- Hover only (no button held) — tooltip ----
        self._update_hover_tooltip(pos)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if not self._drag_started:
            # Click — toggle selection
            if self._drag_node is not None:
                if self._selected == self._drag_node:
                    self._selected = None
                    self.update()
                else:
                    self._selected = self._drag_node
                    self.update()
                    self.node_selected.emit(self._drag_node)
            else:
                # Click on empty space — deselect
                if self._selected is not None:
                    self._selected = None
                    self.update()

        self._drag_node = None
        self._pan_start = None
        self._drag_started = False
        self.unsetCursor()
        event.accept()

    def wheelEvent(self, event) -> None:
        """Mouse-wheel zoom, centered on the cursor position."""
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return

        factor = _ZOOM_STEP if delta > 0 else (1.0 / _ZOOM_STEP)
        new_zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom * factor))
        if new_zoom == self._zoom:
            event.accept()
            return

        # Keep the world point currently under the cursor fixed on screen —
        # standard "zoom toward cursor" behaviour.
        cursor_pos = event.position()
        world_before = self._screen_to_world(cursor_pos)
        self._zoom = new_zoom
        self._pan = QPointF(
            cursor_pos.x() - self._zoom * world_before.x(),
            cursor_pos.y() - self._zoom * world_before.y(),
        )
        QToolTip.hideText()
        self.update()
        event.accept()

    def leaveEvent(self, event) -> None:
        QToolTip.hideText()
        super().leaveEvent(event)

    # ------------------------------------------------------------------
    # Tooltip
    # ------------------------------------------------------------------

    def _update_hover_tooltip(self, pos: QPointF) -> None:
        if not self._entities:
            QToolTip.hideText()
            return

        world = self._screen_to_world(pos)
        idx = self._find_node_at(world.x(), world.y())
        if idx is None:
            QToolTip.hideText()
            return

        entity = self._entities[idx]
        degree = self._degrees[idx] if idx < len(self._degrees) else 0
        rep = self._representation[idx] if idx < len(self._representation) else 0.0

        text = (
            f"{entity.get('name', '')}\n"
            f"Type: {entity.get('type') or 'Unknown'}\n"
            f"Connections: {degree}\n"
            f"Representation: {rep:.0f}%"
        )
        QToolTip.showText(self.mapToGlobal(pos.toPoint()), text, self)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()
        draw_h = h - _LEGEND_H

        if not self._entities:
            painter.setPen(QColor("#94a3b8"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(
                QRectF(0, 0, w, draw_h),
                Qt.AlignmentFlag.AlignCenter,
                "No entities loaded",
            )
            self._draw_legend(painter, w, h)
            return

        sel = self._selected
        connected: set[int] = self._adjacency[sel] if sel is not None else set()

        # Zoom/pan applies only to the graph itself — the legend and empty
        # state stay fixed on screen (drawn outside this save/restore block).
        painter.save()
        painter.translate(self._pan)
        painter.scale(self._zoom, self._zoom)

        # ---- Edges ----
        for i, j in self._edges:
            if sel is None:
                # No selection: all edges light gray
                pen = QPen(QColor("#e2e8f0"), 1.5)
            elif i == sel or j == sel:
                # Edge connected to selected node: highlight
                pen = QPen(QColor("#2563eb"), 2.0)
            else:
                # Unrelated edge: fade
                pen = QPen(QColor("#f1f5f9"), 1.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(self._to_px(*self._positions[i]), self._to_px(*self._positions[j]))

        # ---- Nodes ----
        label_font = QFont("Segoe UI", 7)
        label_font.setWeight(QFont.Weight.Medium)
        painter.setFont(label_font)
        fm = QFontMetrics(label_font)
        label_h = fm.height()

        for i, entity in enumerate(self._entities):
            rx, ry = self._positions[i]
            px = self._to_px(rx, ry)
            cx, cy = px.x(), px.y()

            color_hex = _TYPE_COLORS.get(_safe_type(entity), _DEFAULT_COLOR)
            base_color = QColor(color_hex)

            # Base size reflects Entity Representation (%) — Degree
            # Centrality relative to the most-connected entity — then the
            # existing selection state scales/fades it further, unchanged.
            base_r = self._node_radius_for(i)

            # Determine opacity and ring based on selection state
            if sel is None:
                alpha = 255
                ring_w = 0
                this_r = base_r
            elif i == sel:
                alpha = 255
                ring_w = 3
                this_r = base_r * 1.15
            elif i in connected:
                alpha = 230
                ring_w = 0
                this_r = base_r
            else:
                alpha = 70   # faded
                ring_w = 0
                this_r = base_r * 0.9

            fill = QColor(base_color)
            fill.setAlpha(alpha)

            # Node fill
            painter.setBrush(QBrush(fill))
            if ring_w > 0:
                ring_color = QColor("#2563eb")
                ring_color.setAlpha(alpha)
                painter.setPen(QPen(ring_color, ring_w))
            else:
                border = QColor(base_color.darker(140))
                border.setAlpha(alpha)
                painter.setPen(QPen(border, 1))

            painter.drawEllipse(QPointF(cx, cy), this_r, this_r)

            # Label
            lbl_color = QColor("#334155")
            lbl_color.setAlpha(alpha if sel is not None else 220)
            painter.setPen(lbl_color)

            name = entity.get("name", "")
            label_w = 110
            label_top = cy + this_r + 3 if ry >= 0.5 else cy - this_r - label_h * 2 - 3
            painter.drawText(
                QRectF(cx - label_w / 2, label_top, label_w, label_h * 2 + 4),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                name,
            )

        painter.restore()

        self._draw_legend(painter, w, h)

    # ------------------------------------------------------------------
    # Legend
    # ------------------------------------------------------------------

    def _draw_legend(self, painter: QPainter, w: int, h: int) -> None:
        font = QFont("Segoe UI", 7)
        painter.setFont(font)
        fm = QFontMetrics(font)

        present = {_safe_type(e) for e in self._entities}
        items = [(lbl, col) for lbl, col in _LEGEND if lbl in present]
        if not items:
            items = _LEGEND

        dot_r = 4
        gap = 10
        item_w = dot_r * 2 + gap + max((fm.horizontalAdvance(lbl) for lbl, _ in items), default=50)
        total_w = len(items) * item_w
        x = (w - total_w) / 2
        y_center = h - _LEGEND_H // 2

        for lbl, color_hex in items:
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(x + dot_r, y_center), dot_r, dot_r)

            painter.setPen(QColor("#64748b"))
            text_w = fm.horizontalAdvance(lbl)
            painter.drawText(
                QRectF(x + dot_r * 2 + 4, y_center - fm.height() / 2, text_w + 4, fm.height()),
                Qt.AlignmentFlag.AlignVCenter,
                lbl,
            )
            x += dot_r * 2 + gap + text_w + 12
