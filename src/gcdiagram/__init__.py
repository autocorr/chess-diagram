"""Chess diagrams from extended FEN using the Good Companion (GC2004) fonts.

    >>> from gcdiagram import render_svg, RenderOptions
    >>> svg = render_svg("{Q90}7/8/8/8/8/8/8/8", RenderOptions(caption=["#2"]))

See ARCHITECTURE.md for the extended FEN grammar.
"""

from .board import HOLE, WALL, Board, Hole, Piece, Special, Square, Wall
from .catalog import Catalog, load_catalog
from .fen import FenError, figure_token, parse, serialize
from .options import RenderOptions
from .render.pdf import render_pdf
from .render.svg import render_svg

__all__ = [
    "HOLE",
    "WALL",
    "Board",
    "Catalog",
    "FenError",
    "Hole",
    "Piece",
    "RenderOptions",
    "Special",
    "Square",
    "Wall",
    "figure_token",
    "load_catalog",
    "parse",
    "render_pdf",
    "render_svg",
    "serialize",
]
