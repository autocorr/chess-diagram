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
from ..geometry import U, layout
from ..options import RenderOptions
from ..svgpath import fmt
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
    lay = layout(board, replace(opts, caption=(), piece_count=False, padding=0), cat)
    height = lay.height

    lines = []
    for r in range(board.height):
        baseline = height - (lay.board_y + r * U + BASELINE)
        lines.append(
            rf"\gcrank{{{num(lay.board_x)}}}{{{num(baseline)}}}{{{_rank(board, r, opts, cat)}}}%"
        )
    if lay.rects:
        rects = "".join(
            rf"\gcr{{{num(x)}}}{{{num(height - y - h)}}}{{{num(w)}}}{{{num(h)}}}"
            for x, y, w, h in lay.rects
        )
        lines.append(rf"\gcrects{{{rects}}}%")
    if lay.arrows:
        paths = "".join(
            rf"\gcm{{{num(pts[0][0])}}}{{{num(height - pts[0][1])}}}"
            + "".join(rf"\gcl{{{num(x)}}}{{{num(height - y)}}}" for x, y in pts[1:])
            + r"\gcz"
            for pts in lay.arrows
        )
        rgb = "".join(f"{round(v * 255):02X}" for v in parse_color(opts.arrow_color))
        lines.append(rf"\gcarrows{{{rgb}}}{{{opts.arrow_opacity:g}}}{{{paths}}}%")

    count = board.piece_count_label() if opts.piece_count else ""
    return num(lay.width), num(height), "\n".join(lines), count


def render_tex(
    board: Board | str, options: RenderOptions | None = None, *, catalog: Catalog | None = None
) -> str:
    r"""A \gcbox{width}{height}{body}{caption}{count} call for latex/gcsnippet.sty."""
    opts = options or RenderOptions()
    width, height, body, count = tex_parts(board, opts, catalog=catalog)
    caption = r"\\".join(tex_escape(line) for line in opts.caption)
    return f"\\gcbox{{{width}}}{{{height}}}{{%\n{body}\n}}{{{caption}}}{{{count}}}%\n"
