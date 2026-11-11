"""Output formats. Each renderer draws a geometry.Layout."""

from __future__ import annotations

from ..board import Board
from ..catalog import Catalog, load_catalog
from ..fen import parse
from ..options import RenderOptions


def prepare(
    board: Board | str, options: RenderOptions | None, catalog: Catalog | None
) -> tuple[Board, RenderOptions, Catalog]:
    """Fill in default options and catalog, and parse the board if it is a FEN string."""
    cat = catalog or load_catalog()
    if isinstance(board, str):
        board = parse(board, cat)
    return board, options or RenderOptions(), cat
