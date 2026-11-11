r"""LaTeX output (route A): a \gcbox call drawn by latex/gcsnippet.sty with the real GC fonts.

The fonts are embedded once per document, so a booklet of many diagrams stays small.
Each rank is one run of glyph characters. All glyph codes are digits, ASCII letters or
Latin-1 symbols, none of which are special to TeX, so ranks are written as plain UTF-8
text. Coordinates are in squares (multiples of \gcsquare) with the y axis pointing up,
so the same snippet can be typeset at any size.

The body is the exact text that latex/gcdiagram.lua emits for the same board and
options (route B); tests/test_latex.py checks this.
"""

from __future__ import annotations

from dataclasses import replace

from ..board import Board
from ..catalog import Catalog, Glyph
from ..geometry import WALL_FILL, Rect, U, layout
from ..markup import parse_markup
from ..options import RenderOptions
from ..svgpath import Segment, fmt
from . import prepare
from .pdf import parse_color

BASELINE = 1500  # font units from the top of a cell down to the glyph baseline

_TEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "#": r"\#",
    "$": r"\$",
    "%": r"\%",
    "&": r"\&",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def tex_escape(text: str) -> str:
    return "".join(_TEX_SPECIALS.get(ch, ch) for ch in text)


def caption_tex(line: str) -> str:
    r"""One caption line as LaTeX: special characters escaped, and <b>/<i> markup as
    \textbf and \textit."""
    out = []
    for run in parse_markup(line):
        text = tex_escape(run.text)
        if run.italic:
            text = rf"\textit{{{text}}}"
        if run.bold:
            text = rf"\textbf{{{text}}}"
        out.append(text)
    return "".join(out)


def _hex(color: str) -> str:
    """A color as RRGGBB, as xcolor's HTML model takes it."""
    return "".join(f"{round(v * 255):02X}" for v in parse_color(color))


def num(units: float) -> str:
    """Font units as a decimal number of squares: 100 -> '.05', -233 -> '-.1165'."""
    return fmt(units / U, 5)


def _cell_glyph(board: Board, r: int, c: int, opts: RenderOptions, cat: Catalog) -> Glyph:
    glyph = cat.cell_glyph(board.cells[r][c], board.shade(r, c), opts.wall)
    return glyph or cat["square:light"]  # a blank glyph that just advances one square


def _rank(board: Board, r: int, opts: RenderOptions, cat: Catalog) -> str:
    runs: list[tuple[str, str]] = []
    for c in range(board.width):
        g = _cell_glyph(board, r, c, opts, cat)
        text = chr(g.code)
        if g.dx:
            text = rf"\gcfix{{{num(g.dx)}}}{{{text}}}"
        if runs and runs[-1][0] == g.font:
            runs[-1] = (g.font, runs[-1][1] + text)
        else:
            runs.append((g.font, text))
    return "".join(rf"\gc{font}{{{text}}}" for font, text in runs)


def tex_parts(
    board: Board | str, options: RenderOptions | None = None, *, catalog: Catalog | None = None
) -> tuple[str, str, str, str]:
    """(width, height, body, piece count) as they appear in the \\gcbox call."""
    board, opts, cat = prepare(board, options, catalog)
    lay = layout(
        board, replace(opts, caption=(), caption_above=(), piece_count=False, padding=0), cat
    )
    height = lay.height

    lines = []
    for r in range(board.height):
        baseline = height - (lay.board_y + r * U + BASELINE)
        lines.append(
            rf"\gcrank{{{num(lay.board_x)}}}{{{num(baseline)}}}{{{_rank(board, r, opts, cat)}}}%"
        )

    def rects(rs: list[Rect]) -> str:
        return "".join(
            rf"\gcr{{{num(x)}}}{{{num(height - y - h)}}}{{{num(w)}}}{{{num(h)}}}"
            for x, y, w, h in rs
        )

    if lay.wall_fills:
        lines.append(rf"\gcfills{{{_hex(WALL_FILL)}}}{{{rects(lay.wall_fills)}}}%")
    if lay.rects:
        lines.append(rf"\gcrects{{{rects(lay.rects)}}}%")
    if lay.arrows:
        paths = "".join(
            rf"\gcm{{{num(pts[0][0])}}}{{{num(height - pts[0][1])}}}"
            + "".join(rf"\gcl{{{num(x)}}}{{{num(height - y)}}}" for x, y in pts[1:])
            + r"\gcz"
            for pts in lay.arrows
        )
        lines.append(
            rf"\gcarrows{{{_hex(opts.arrow_color)}}}{{{opts.arrow_opacity:g}}}{{{paths}}}%"
        )
    for mark in lay.marks:
        path = _tex_path(mark.path, height)
        lines.append(rf"\gcmark{{{_hex(mark.fill)}}}{{{num(mark.halo)}}}{{{path}}}%")

    count = board.piece_count_label() if opts.piece_count else ""
    return num(lay.width), num(height), "\n".join(lines), count


def _tex_path(path: list[Segment], height: float) -> str:
    out = []
    for seg in path:
        if seg[0] == "M":
            out.append(rf"\gcm{{{num(seg[1])}}}{{{num(height - seg[2])}}}")
        elif seg[0] == "L":
            out.append(rf"\gcl{{{num(seg[1])}}}{{{num(height - seg[2])}}}")
        elif seg[0] == "Q":
            _, qx, qy, x, y = seg
            out.append(rf"\gcq{{{num(qx)}}}{{{num(height - qy)}}}{{{num(x)}}}{{{num(height - y)}}}")
        else:
            out.append(r"\gcz")
    return "".join(out)


def render_tex(
    board: Board | str, options: RenderOptions | None = None, *, catalog: Catalog | None = None
) -> str:
    r"""A \gcbox[caption above]{width}{height}{body}{caption}{count} call for
    latex/gcsnippet.sty. The optional argument is only written when there is a caption
    above the board."""
    opts = options or RenderOptions()
    width, height, body, count = tex_parts(board, opts, catalog=catalog)
    caption = r"\\".join(caption_tex(line) for line in opts.caption)
    above = r"\\".join(caption_tex(line) for line in opts.caption_above)
    above = f"[{{{above}}}]" if above else ""
    return f"\\gcbox{above}{{{width}}}{{{height}}}{{%\n{body}\n}}{{{caption}}}{{{count}}}%\n"
