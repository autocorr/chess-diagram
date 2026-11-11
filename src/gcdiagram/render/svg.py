"""Optimised standalone SVG: each glyph outline is defined once and placed with <use>."""

from __future__ import annotations

from html import escape
from string import ascii_lowercase

from ..board import Board
from ..catalog import Catalog
from ..geometry import Layout, Text, U, layout
from ..options import RenderOptions
from ..svgpath import fmt, svg_path, to_svg
from . import prepare

FONT_FAMILY = "Helvetica,Arial,sans-serif"


def _ident(prefix: str, n: int) -> str:
    s = ""
    while True:
        s = ascii_lowercase[n % 26] + s
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
    board, opts, cat = prepare(board, options, catalog)
    return _document(layout(board, opts, cat), opts, cat, id_prefix, xlink, annotate)


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
        parts += [f'<path id="{i}" d="{svg_path(cat.outlines[o])}"/>' for o, i in ids.items()]
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

    for mark in lay.marks:
        d = to_svg(mark.path)
        if mark.halo:
            parts.append(
                f'<path d="{d}" fill="none" stroke="#fff" stroke-width="{fmt(mark.halo)}" '
                'stroke-linejoin="round"/>'
            )
        parts.append(f'<path d="{d}" fill="{mark.fill}"/>')

    if lay.texts:
        size = lay.texts[0].size
        parts.append(f'<g font-family="{FONT_FAMILY}" font-size="{fmt(size)}">')
        for t in lay.texts:
            anchor = "" if t.anchor == "start" else f' text-anchor="{t.anchor}"'
            # Runs end with the space before the next word; xml:space keeps it in
            # renderers that trim each text node.
            space = ' xml:space="preserve"' if len(t.runs) > 1 else ""
            parts.append(f'<text x="{fmt(t.x)}" y="{fmt(t.y)}"{anchor}{space}>{_text(t)}</text>')
        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts) + "\n"


def _text(t: Text) -> str:
    """A line's content: plain text, or a tspan for each bold or italic run."""
    out = []
    for run in t.runs:
        attrs = (' font-weight="bold"' if run.bold else "") + (
            ' font-style="italic"' if run.italic else ""
        )
        out.append(f"<tspan{attrs}>{escape(run.text)}</tspan>" if attrs else escape(run.text))
    return "".join(out)
