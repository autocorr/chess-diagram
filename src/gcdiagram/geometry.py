"""Format-independent layout of a diagram, in font units (one square = 2000).

The layout's y axis points down. Renderers only have to draw what is listed here:
glyph placements, filled rectangles, arrow polygons and text.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Literal

from .board import Board, Hole, Square, Wall, parse_square
from .catalog import Catalog, figure_key, load_catalog
from .options import RenderOptions
from .textmetrics import text_width

U = 2000  # one square
SINGLE = 100  # single border line thickness (GC2004D)
DOUBLE_THIN, DOUBLE_GAP, DOUBLE_THICK = 50, 100, 200  # GC2004Y double border
CAPTION_GAP = 0.3 * U
LINE_HEIGHT = 1.25

ARROW_SHAFT = 200
ARROW_HEAD_LENGTH = 640
ARROW_HEAD_WIDTH = 600

Rect = tuple[float, float, float, float]  # x, y, w, h
Point = tuple[float, float]


@dataclass(frozen=True)
class GlyphUse:
    key: str  # catalog key
    x: float  # cell top-left
    y: float
    square: str = ""  # square name, e.g. "e4"


@dataclass(frozen=True)
class Text:
    x: float
    y: float  # baseline
    size: float
    text: str
    anchor: Literal["start", "middle", "end"] = "middle"


@dataclass
class Layout:
    width: float
    height: float
    background: Rect | None
    board_x: float = 0  # top-left corner of the board's squares
    board_y: float = 0
    glyphs: list[GlyphUse] = field(default_factory=list)
    rects: list[Rect] = field(default_factory=list)
    arrows: list[list[Point]] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)


def frame_thickness(style: str) -> float:
    return {
        "single": SINGLE,
        "outline": SINGLE,
        "double": DOUBLE_THIN + DOUBLE_GAP + DOUBLE_THICK,
    }.get(style, 0)


def layout(
    board: Board, options: RenderOptions | None = None, catalog: Catalog | None = None
) -> Layout:
    opts = options or RenderOptions()
    cat = catalog or load_catalog()
    scale = U / opts.square_size  # font units per point
    pad = opts.padding * scale
    t = frame_thickness(opts.border)
    board_w, board_h = board.width * U, board.height * U

    # Caption lines (centred) and the piece count (right-aligned on the first line).
    size = opts.caption_size * U
    lines = list(opts.caption)
    count = ""
    if opts.piece_count:
        w, b, n = board.piece_count()
        count = f"({w}+{b}+{n})" if n else f"({w}+{b})"
        if not lines:
            lines = [""]
    text_w = max(
        [text_width(line, size) for line in lines]
        + [text_width(lines[0], size) + 2 * text_width(count, size) + size if count else 0],
    )
    diagram_w = board_w + 2 * t
    content_w = max(diagram_w, text_w)
    width = content_w + 2 * pad
    caption_h = (CAPTION_GAP + len(lines) * size * LINE_HEIGHT) if lines else 0
    height = board_h + 2 * t + caption_h + 2 * pad

    bx = pad + (content_w - diagram_w) / 2 + t
    by = pad + t
    out = Layout(width, height, (0, 0, width, height) if opts.background else None, bx, by)

    # Squares, figures and walls.
    for r, row in enumerate(board.cells):
        for c, cell in enumerate(row):
            x, y = bx + c * U, by + r * U
            shade = board.shade(r, c)
            if isinstance(cell, Square):
                key = figure_key(cell.figure, shade) if cell.figure else f"square:{shade}"
                if cat[key].bbox is not None:  # the empty light square is blank
                    out.glyphs.append(GlyphUse(key, x, y, board.square_name(r, c)))
            elif isinstance(cell, Wall):
                if opts.wall == "box":
                    key = f"special:box:none:{shade}"
                    out.glyphs.append(GlyphUse(key, x, y, board.square_name(r, c)))
                else:
                    out.rects.append((x, y, U, U))

    out.rects.extend(border_rects(board, opts.border, bx, by))
    out.arrows.extend(arrow_polygon(board, spec, bx, by) for spec in opts.arrows)

    if lines:
        baseline = by + board_h + t + CAPTION_GAP + size * 0.8
        centre = pad + content_w / 2
        for i, line in enumerate(lines):
            if line:
                out.texts.append(Text(centre, baseline + i * size * LINE_HEIGHT, size, line))
        if count:
            right = bx + board_w + t if text_w <= diagram_w else pad + content_w
            out.texts.append(Text(right, baseline, size, count, "end"))
    return out


# --- Borders ------------------------------------------------------------------------------

_SIDES = {"top": (-1, 0), "bottom": (1, 0), "left": (0, -1), "right": (0, 1)}


def border_rects(board: Board, style: str, bx: float, by: float) -> list[Rect]:
    """Filled rectangles for the frame and the lines around holes, merged where collinear."""
    if style == "none":
        return []
    t = SINGLE
    horizontal: list[Rect] = []
    vertical: list[Rect] = []
    frame = style in ("single", "double")

    for r in range(board.height):
        for c in range(board.width):
            if isinstance(board.cells[r][c], Hole):
                continue
            exposed = set()
            for side, (dr, dc) in _SIDES.items():
                nr, nc = r + dr, c + dc
                if board.is_board_square(nr, nc):
                    continue
                if frame and not board.contains(nr, nc):
                    continue  # the rectangular frame covers this edge
                exposed.add(side)
            x, y = bx + c * U, by + r * U
            if "top" in exposed:
                horizontal.append((x, y - t, U, t))
            if "bottom" in exposed:
                horizontal.append((x, y + U, U, t))
            if "left" in exposed:
                vertical.append((x - t, y, t, U))
            if "right" in exposed:
                vertical.append((x + U, y, t, U))
            # Fill convex corners where two exposed edges meet.
            for v, h, cx, cy in (
                ("top", "left", x - t, y - t),
                ("top", "right", x + U, y - t),
                ("bottom", "left", x - t, y + U),
                ("bottom", "right", x + U, y + U),
            ):
                if v in exposed and h in exposed:
                    horizontal.append((cx, cy, t, t))

    w, h = board.width * U, board.height * U
    if style == "single":
        horizontal += _ring(bx, by, w, h, 0, SINGLE)[:2]
        vertical += _ring(bx, by, w, h, 0, SINGLE)[2:]
    elif style == "double":
        for inner, thick in ((0, DOUBLE_THIN), (DOUBLE_THIN + DOUBLE_GAP, DOUBLE_THICK)):
            ring = _ring(bx, by, w, h, inner, thick)
            horizontal += ring[:2]
            vertical += ring[2:]
    return _merge(horizontal, axis=0) + _merge(vertical, axis=1)


def _ring(x: float, y: float, w: float, h: float, inner: float, t: float) -> list[Rect]:
    """A rectangular ring 'inner' units outside (x, y, w, h), t thick: top, bottom, left, right."""
    o = inner + t
    return [
        (x - o, y - o, w + 2 * o, t),
        (x - o, y + h + inner, w + 2 * o, t),
        (x - o, y - inner, t, h + 2 * inner),
        (x + w + inner, y - inner, t, h + 2 * inner),
    ]


def _merge(rects: list[Rect], axis: int) -> list[Rect]:
    """Merge touching or overlapping rectangles that share a line along the given axis."""
    groups: dict[tuple[float, float], list[tuple[float, float]]] = {}
    for x, y, w, h in rects:
        if axis == 0:
            groups.setdefault((y, h), []).append((x, x + w))
        else:
            groups.setdefault((x, w), []).append((y, y + h))
    out: list[Rect] = []
    for (pos, thick), spans in sorted(groups.items()):
        spans.sort()
        start, end = spans[0]
        for s, e in [*spans[1:], (math.inf, math.inf)]:
            if s <= end:
                end = max(end, e)
                continue
            out.append(
                (start, pos, end - start, thick) if axis == 0 else (pos, start, thick, end - start)
            )
            start, end = s, e
    return out


# --- Arrows -------------------------------------------------------------------------------

_ARROW_RE = re.compile(r"\s*([a-z][0-9]+)\s*[-x>]?\s*([a-z][0-9]+)\s*")


def parse_arrow(spec: str | tuple[str, str]) -> tuple[str, str]:
    if isinstance(spec, tuple):
        return spec
    m = _ARROW_RE.fullmatch(spec)
    if not m:
        raise ValueError(f"bad arrow {spec!r}; expected e.g. 'e2-e4'")
    return m.group(1), m.group(2)


def arrow_polygon(board: Board, spec: str | tuple[str, str], bx: float, by: float) -> list[Point]:
    a, b = parse_arrow(spec)
    (r0, c0), (r1, c1) = parse_square(a, board.height), parse_square(b, board.height)
    if c1 >= board.width or c0 >= board.width:
        raise ValueError(f"arrow {spec!r} leaves the board")
    ax, ay = bx + (c0 + 0.5) * U, by + (r0 + 0.5) * U
    tx, ty = bx + (c1 + 0.5) * U, by + (r1 + 0.5) * U
    dx, dy = tx - ax, ty - ay
    # sqrt rather than hypot, and no rounding: latex/gcdiagram.lua repeats this arithmetic
    # and must produce bit-identical results.
    length = math.sqrt(dx * dx + dy * dy)
    if length == 0:
        raise ValueError(f"arrow {spec!r} starts and ends on the same square")
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    head = min(ARROW_HEAD_LENGTH, 0.6 * length)
    hx, hy = tx - ux * head, ty - uy * head
    s, w = ARROW_SHAFT / 2, ARROW_HEAD_WIDTH / 2
    pts = [
        (ax + nx * s, ay + ny * s),
        (hx + nx * s, hy + ny * s),
        (hx + nx * w, hy + ny * w),
        (tx, ty),
        (hx - nx * w, hy - ny * w),
        (hx - nx * s, hy - ny * s),
        (ax - nx * s, ay - ny * s),
    ]
    return pts
