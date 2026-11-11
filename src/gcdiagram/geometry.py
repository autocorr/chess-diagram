"""Format-independent layout of a diagram, in font units (one square = 2000).

The layout's y axis points down. Renderers only have to draw what is listed here:
glyph placements, filled rectangles, arrow polygons, annotation marks and text.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from .annotations import FILL, Annotation, parse_annotation
from .board import Board, Hole, Wall, parse_square
from .catalog import Catalog, load_catalog
from .markup import Run, parse_markup
from .options import RenderOptions
from .svgpath import Segment
from .textmetrics import text_width

U = 2000  # one square
SINGLE = 100  # single border line thickness (GC2004D)
DOUBLE_THIN, DOUBLE_GAP, DOUBLE_THICK = 50, 100, 200  # GC2004Y double border
CAPTION_GAP = 0.3 * U
COUNT_GAP = 1.0  # space kept between the caption and the piece count, in caption ems
LINE_HEIGHT = 1.25

ARROW_SHAFT = 200
ARROW_HEAD_LENGTH = 640
ARROW_HEAD_WIDTH = 600

# Annotation marks, centerd in their square.
MARK_LINE = 140  # line thickness of the circle, square and triangle
CIRCLE_RADIUS = 880
SQUARE_HALF = 820
TRIANGLE_RADIUS = 980  # circumradius of the outer edge
CROSS_ARM = 620  # from the center to the end of each bar, along x and y
CROSS_LINE = 160
DOT_RADIUS = 200  # a solid dot a fifth of a square across
HALO = 120  # stroke width of the white outline behind every mark (half shows)

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
    runs: tuple[Run, ...]  # styled pieces of the line, set one after another
    anchor: Literal["start", "middle", "end"] = "middle"

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


@dataclass(frozen=True)
class Mark:
    """A filled annotation shape, drawn over the board."""

    path: list[Segment]
    fill: str
    halo: float = 0  # stroke width of a white outline drawn behind it; 0 for none


Line = tuple[Run, ...]


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
    marks: list[Mark] = field(default_factory=list)
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

    # Captions are left-aligned, and the piece count right-aligned on the first line of
    # the caption below the board. Captions wrap at spaces to the diagram's width, the
    # first line below stopping short of the count; only a word too long for any line
    # widens the diagram.
    size = opts.caption_size * U
    pitch = size * LINE_HEIGHT
    count = board.piece_count_label() if opts.piece_count else ""
    count_w = text_width(count, size) + COUNT_GAP * size if count else 0
    diagram_w = board_w + 2 * t
    words = [w for line in [*opts.caption_above, *opts.caption] for w in caption_words(line)]
    first_words = (caption_words(opts.caption[0]) if opts.caption else [])[:1]
    content_w = max(
        [diagram_w]
        + [line_width(w, size) for w in words]
        + [count_w + line_width(w, size) for w in first_words],
    )
    above = wrap_caption(opts.caption_above, size, content_w, 0)
    lines = wrap_caption(opts.caption, size, content_w, count_w)
    if count and not lines:
        lines = [()]
    width = content_w + 2 * pad
    above_h = (len(above) * pitch + CAPTION_GAP) if above else 0
    caption_h = (CAPTION_GAP + len(lines) * pitch) if lines else 0
    height = above_h + board_h + 2 * t + caption_h + 2 * pad

    bx = pad + (content_w - diagram_w) / 2 + t
    by = pad + above_h + t
    out = Layout(width, height, (0, 0, width, height) if opts.background else None, bx, by)

    # Squares, figures and walls.
    for r, row in enumerate(board.cells):
        for c, cell in enumerate(row):
            x, y = bx + c * U, by + r * U
            glyph = cat.cell_glyph(cell, board.shade(r, c), opts.wall)
            if glyph is None:
                if isinstance(cell, Wall):
                    out.rects.append((x, y, U, U))
            elif glyph.bbox is not None:  # the empty light square is blank
                out.glyphs.append(GlyphUse(glyph.key, x, y, board.square_name(r, c)))

    out.rects.extend(border_rects(board, opts.border, bx, by))
    out.arrows.extend(arrow_polygon(board, spec, bx, by) for spec in opts.arrows)
    out.marks.extend(annotation_mark(board, spec, bx, by) for spec in opts.annotations)

    for i, line in enumerate(above):
        if line:
            out.texts.append(Text(pad, pad + size * 0.8 + i * pitch, size, line, "start"))
    if lines:
        baseline = by + board_h + t + CAPTION_GAP + size * 0.8
        for i, line in enumerate(lines):
            if line:
                out.texts.append(Text(pad, baseline + i * pitch, size, line, "start"))
        if count:
            out.texts.append(Text(pad + content_w, baseline, size, (Run(count),), "end"))
    return out


# --- Captions -----------------------------------------------------------------------------


def caption_words(line: str) -> list[Line]:
    """The words of a caption line (split at whitespace), each as styled runs."""
    words: list[Line] = []
    current: list[Run] = []
    for run in parse_markup(line):
        for i, part in enumerate(re.split(r"(\s+)", run.text)):
            if i % 2:  # whitespace
                if current:
                    words.append(tuple(current))
                    current = []
            elif part:
                current.append(Run(part, run.bold, run.italic))
    if current:
        words.append(tuple(current))
    return words


def line_width(runs: Line, size: float) -> float:
    return sum(text_width(r.text, size, r.bold) for r in runs)


def _join(a: Line, b: Line) -> Line:
    """Two pieces of a line with a space between them (in a's style), merging runs."""
    last = a[-1]
    out = [*a[:-1], Run(last.text + " ", last.bold, last.italic)]
    for run in b:
        prev = out[-1]
        if (prev.bold, prev.italic) == (run.bold, run.italic):
            out[-1] = Run(prev.text + run.text, run.bold, run.italic)
        else:
            out.append(run)
    return tuple(out)


def wrap_caption(caption: Sequence[str], size: float, width: float, count_w: float) -> list[Line]:
    """Break caption lines at spaces so each fits in width, the first line in width -
    count_w (beside the piece count). Explicit lines stay separate, and an empty one
    is (). A word too long for its line is put on it anyway (the caller makes the width
    fit every word)."""
    out: list[Line] = []
    for line in caption:
        words = caption_words(line)
        if not words:
            out.append(())
            continue
        current: Line = ()
        for word in words:
            candidate = _join(current, word) if current else word
            room = width - (count_w if not out else 0)
            if current and line_width(candidate, size) > room:
                out.append(current)
                current = word
            else:
                current = candidate
        out.append(current)
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


# --- Annotations --------------------------------------------------------------------------


def annotation_mark(board: Board, spec: str | Annotation, bx: float, by: float) -> Mark:
    ann = parse_annotation(spec)
    if ann.kind == "arrow":
        a, b = ann.squares
        return Mark(_polygon(arrow_polygon(board, (a, b), bx, by)), FILL[ann.color], HALO)
    (square,) = ann.squares
    r, c = parse_square(square, board.height)
    if c >= board.width:
        raise ValueError(f"annotation {str(ann)!r} is off the board")
    cx, cy = bx + (c + 0.5) * U, by + (r + 0.5) * U
    # Rings are an outer edge drawn one way and an inner edge drawn the other, so the
    # nonzero fill rule (the default in SVG, PDF and PGF) leaves the middle empty.
    if ann.kind == "circle":
        path = _circle(cx, cy, CIRCLE_RADIUS, 1) + _circle(cx, cy, CIRCLE_RADIUS - MARK_LINE, -1)
    elif ann.kind == "square":
        o, i = SQUARE_HALF, SQUARE_HALF - MARK_LINE
        path = _polygon([(cx - o, cy - o), (cx + o, cy - o), (cx + o, cy + o), (cx - o, cy + o)])
        path += _polygon([(cx - i, cy - i), (cx - i, cy + i), (cx + i, cy + i), (cx + i, cy - i)])
    elif ann.kind == "triangle":
        # Point up, with the bounding box centerd in the square. The inner edge is
        # MARK_LINE inside the outer one; an equilateral triangle's inradius is half
        # its circumradius, hence the 2 * MARK_LINE.
        ty = cy + TRIANGLE_RADIUS / 4
        path = _triangle(cx, ty, TRIANGLE_RADIUS, 1)
        path += _triangle(cx, ty, TRIANGLE_RADIUS - 2 * MARK_LINE, -1)
    elif ann.kind == "dot":
        path = _circle(cx, cy, DOT_RADIUS, 1)
    else:
        path = _polygon(_cross(cx, cy))
    return Mark(path, FILL[ann.color], HALO)


def _polygon(points: Sequence[Point]) -> list[Segment]:
    (x0, y0), *rest = points
    return [("M", x0, y0), *(("L", x, y) for x, y in rest), ("Z",)]


def _circle(cx: float, cy: float, r: float, direction: int) -> list[Segment]:
    """A circle as eight quadratic Beziers (within 0.1% of the radius)."""
    n = 8
    k = r / math.cos(math.pi / n)  # control points lie on a larger circle
    path: list[Segment] = [("M", cx + r, cy)]
    for i in range(1, n + 1):
        mid, end = direction * (i - 0.5) * 2 * math.pi / n, direction * i * 2 * math.pi / n
        path.append(
            (
                "Q",
                cx + k * math.cos(mid),
                cy + k * math.sin(mid),
                cx + r * math.cos(end),
                cy + r * math.sin(end),
            )
        )
    return [*path, ("Z",)]


def _triangle(cx: float, cy: float, r: float, direction: int) -> list[Segment]:
    """An upright equilateral triangle with its centroid at (cx, cy), y down."""
    angles = (-90, 30, 150) if direction > 0 else (-90, 150, 30)
    return _polygon(
        [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in angles]
    )


def _cross(cx: float, cy: float) -> list[Point]:
    """The outline of a diagonal cross: two bars, CROSS_LINE thick, meeting at the center."""
    a = CROSS_ARM
    e = CROSS_LINE / 2 / math.sqrt(2)  # half the bar thickness, along x and y
    k = 2 * e  # where the bars' edges cross the axes
    corners = [
        (0, -k), (a - e, -a - e), (a + e, -a + e),
        (k, 0), (a + e, a - e), (a - e, a + e),
        (0, k), (-a + e, a + e), (-a - e, a - e),
        (-k, 0), (-a - e, -a + e), (-a + e, -a - e),
    ]  # fmt: skip
    return [(cx + x, cy + y) for x, y in corners]
