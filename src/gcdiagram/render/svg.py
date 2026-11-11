"""Optimised standalone SVG: each glyph outline is defined once and placed with <use>."""

from __future__ import annotations

from functools import lru_cache
from html import escape

from .. import svgpath
from ..board import Board
from ..catalog import Catalog, load_catalog
from ..fen import parse
from ..geometry import Layout, U, layout
from ..options import RenderOptions
from ..svgpath import fmt

FONT_FAMILY = "Helvetica,Arial,sans-serif"
_ALPHABET = "abcdefghijklmnopqrstuvwxyz"


@lru_cache(maxsize=1024)
def _compact(d: str) -> str:
    return svgpath.to_svg(svgpath.parse(d))


def _ident(prefix: str, n: int) -> str:
    s = ""
    while True:
        s = _ALPHABET[n % 26] + s
        n = n // 26 - 1
        if n < 0:
            return prefix + s


def render_svg(
    board: Board | str,
    options: RenderOptions | None = None,
    *,
    catalog: Catalog | None = None,
    id_prefix: str = "g",
    xlink: bool = False,
    annotate: bool = False,
) -> str:
    """Render a board as an SVG document.

    id_prefix keeps ids unique when several diagrams are inlined into one HTML page.
    xlink=True writes xlink:href for older SVG 1.1 consumers (e.g. some Inkscape builds).
    annotate=True adds data-square attributes to placed glyphs (for scripting).
    """
    opts = options or RenderOptions()
    cat = catalog or load_catalog()
    if isinstance(board, str):
        board = parse(board, cat)
    lay = layout(board, opts, cat)
    return _document(lay, opts, cat, id_prefix, xlink, annotate)


def _document(
    lay: Layout,
    opts: RenderOptions,
    cat: Catalog,
    prefix: str,
    xlink: bool,
    annotate: bool,
) -> str:
    pt = opts.square_size / U
    href = "xlink:href" if xlink else "href"
    ns = ' xmlns:xlink="http://www.w3.org/1999/xlink"' if xlink else ""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg"{ns} viewBox="0 0 {fmt(lay.width)} '
        f'{fmt(lay.height)}" width="{fmt(lay.width * pt)}pt" height="{fmt(lay.height * pt)}pt">'
    ]
    if lay.background and opts.background:
        parts.append(
            f'<rect width="{fmt(lay.width)}" height="{fmt(lay.height)}" '
            f'fill="{escape(opts.background)}"/>'
        )

    ids: dict[str, str] = {}
    for use in lay.glyphs:
        outline = cat[use.key].outline
        if outline not in ids:
            ids[outline] = _ident(prefix, len(ids))
    if ids:
        parts.append("<defs>")
        parts += [f'<path id="{i}" d="{_compact(cat.outlines[o])}"/>' for o, i in ids.items()]
        parts.append("</defs>")

    for use in lay.glyphs:
        attrs = f'{href}="#{ids[cat[use.key].outline]}" x="{fmt(use.x)}" y="{fmt(use.y)}"'
        if annotate:
            attrs += f' data-square="{use.square}"'
        parts.append(f"<use {attrs}/>")

    if lay.rects:
        d = "".join(f"M{fmt(x)} {fmt(y)}h{fmt(w)}v{fmt(h)}h{fmt(-w)}z" for x, y, w, h in lay.rects)
        parts.append(f'<path d="{d}"/>')

    if lay.arrows:
        d = "".join(
            "M" + "L".join(f"{fmt(x)} {fmt(y)}" for x, y in pts) + "z" for pts in lay.arrows
        )
        opacity = f' fill-opacity="{fmt(opts.arrow_opacity)}"' if opts.arrow_opacity < 1 else ""
        parts.append(f'<path d="{d}" fill="{escape(opts.arrow_color)}"{opacity}/>')

    if lay.texts:
        size = lay.texts[0].size
        parts.append(f'<g font-family="{FONT_FAMILY}" font-size="{fmt(size)}">')
        for t in lay.texts:
            anchor = "" if t.anchor == "start" else f' text-anchor="{t.anchor}"'
            parts.append(f'<text x="{fmt(t.x)}" y="{fmt(t.y)}"{anchor}>{escape(t.text)}</text>')
        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts) + "\n"
