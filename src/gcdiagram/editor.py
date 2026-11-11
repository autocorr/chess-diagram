"""JSON-friendly operations for the browser editor (web/), which runs this package in Pyodide.

The editor keeps the board as a canonical FEN string and options as a dict of
RenderOptions fields. Every function takes and returns plain data, so it can be called
from JavaScript; errors come back as {"error": message, "code": code}.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from . import svgpath
from .board import (
    ANGLES,
    EMPTY,
    KINDS,
    Board,
    Cell,
    Color,
    Hole,
    Piece,
    Shade,
    Square,
    Variant,
    Wall,
)
from .catalog import load_catalog
from .fen import FenError, figure_token, parse, serialize
from .geometry import layout
from .options import RenderOptions
from .render.pdf import render_pdf
from .render.svg import render_svg
from .render.tex import render_tex

_OPTION_FIELDS = {f.name for f in fields(RenderOptions)}
_COLORS: tuple[Color, ...] = ("white", "black", "neutral")
_VARIANTS: tuple[Variant, ...] = ("plain", "chameleon", "mirror")


def options_from(data: dict[str, Any] | None) -> RenderOptions:
    """RenderOptions from a dict, ignoring unknown keys and converting lists."""
    data = dict(data or {})
    kwargs = {k: v for k, v in data.items() if k in _OPTION_FIELDS}
    for key in ("caption", "arrows"):
        if key in kwargs:
            kwargs[key] = tuple(str(v) for v in kwargs[key] if str(v).strip())
    return RenderOptions(**kwargs)


def info() -> dict[str, Any]:
    """Everything the palette needs: supported pieces and specials."""
    cat = load_catalog()
    pieces = []
    for kind in KINDS:
        for color in _COLORS:
            for variant in _VARIANTS:
                for angle in ANGLES:
                    p = Piece(kind, color, angle, variant)
                    if cat.supports(p):
                        pieces.append(
                            {
                                "token": figure_token(p),
                                "kind": kind,
                                "color": color,
                                "variant": variant,
                                "angle": angle,
                            }
                        )
    specials = {name: sorted(colors) for name, colors in sorted(cat.specials.items())}
    return {"pieces": pieces, "specials": specials}


def _error(e: Exception) -> dict[str, Any]:
    return {"error": str(e), "code": getattr(e, "code", "error")}


def render(fen: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Canonical FEN, SVG and the geometry needed to map pointer positions to squares."""
    try:
        board = parse(fen)
        opts = options_from(options)
        lay = layout(board, opts)
        svg = render_svg(board, opts, annotate=True, id_prefix="ed")
    except (FenError, ValueError) as e:
        return _error(e)
    return {
        "fen": serialize(board),
        "svg": svg,
        "width": lay.width,
        "height": lay.height,
        "boardX": lay.board_x,
        "boardY": lay.board_y,
        "files": board.width,
        "ranks": board.height,
        "cells": [[_describe(cell) for cell in row] for row in board.cells],
    }


def _describe(cell: Cell) -> str:
    """'' for an empty square, '.' hole, '*' wall, else the figure's FEN token."""
    if isinstance(cell, Hole):
        return "."
    if isinstance(cell, Wall):
        return "*"
    assert isinstance(cell, Square)
    return figure_token(cell.figure) if cell.figure else ""


def _cell(token: str) -> Cell:
    """A cell from '' (empty), '.', '*' or one figure token such as '{Q90}'."""
    if token == "":
        return EMPTY
    board = parse(token)
    if (board.width, board.height) != (1, 1):
        raise ValueError(f"{token!r} is not a single cell")
    return board.cells[0][0]


def set_cell(fen: str, square: str, token: str) -> dict[str, Any]:
    """Put a figure (or empty, hole, wall) on a square."""
    try:
        board = parse(fen)
        board[square] = _cell(token)
    except (FenError, ValueError) as e:
        return _error(e)
    return {"fen": serialize(board)}


def move(fen: str, source: str, target: str) -> dict[str, Any]:
    """Move a cell's contents; the source becomes an empty square."""
    try:
        board = parse(fen)
        cell = board[source]
        if source != target:
            board[target] = cell
            board[source] = EMPTY
    except (FenError, ValueError) as e:
        return _error(e)
    return {"fen": serialize(board)}


def rotate(fen: str, square: str, step: int = 45) -> dict[str, Any]:
    """Rotate the piece on a square to the next angle the fonts support for it."""
    try:
        board = parse(fen)
        cell = board[square]
        if not (isinstance(cell, Square) and isinstance(cell.figure, Piece)):
            return {"fen": serialize(board)}
        p = cell.figure
        cat = load_catalog()
        i = ANGLES.index(p.angle)
        for k in range(1, len(ANGLES) + 1):
            angle = ANGLES[(i + k * (1 if step > 0 else -1)) % len(ANGLES)]
            candidate = Piece(p.kind, p.color, angle, p.variant)
            if cat.supports(candidate):
                board[square] = Square(candidate)
                break
    except (FenError, ValueError) as e:
        return _error(e)
    return {"fen": serialize(board)}


def resize(fen: str, width: int, height: int) -> dict[str, Any]:
    """Resize, keeping rank 1 at the bottom and file a on the left."""
    try:
        board = parse(fen)
        cells = []
        for r in range(height):
            old_r = board.height - height + r
            cells.append(
                [board.cells[old_r][c] if board.contains(old_r, c) else EMPTY for c in range(width)]
            )
        new = Board(cells)
    except (FenError, ValueError) as e:
        return _error(e)
    return {"fen": serialize(new)}


def export(fen: str, options: dict[str, Any] | None, fmt: str) -> dict[str, Any]:
    """The diagram as an SVG, PDF (bytes) or TeX snippet, exactly as the CLI writes it."""
    try:
        board = parse(fen)
        opts = options_from(options)
        if fmt == "svg":
            return {"data": render_svg(board, opts), "mime": "image/svg+xml"}
        if fmt == "pdf":
            return {"data": render_pdf(board, opts), "mime": "application/pdf"}
        if fmt == "tex":
            return {"data": render_tex(board, opts), "mime": "application/x-tex"}
    except (FenError, ValueError) as e:
        return _error(e)
    return {"error": f"unknown format {fmt!r}", "code": "error"}


def figure_svg(token: str, shade: str = "light") -> str:
    """One glyph (a figure, or the empty square for '') on a square, for palette buttons."""
    if shade not in ("light", "dark"):
        raise ValueError(f"shade must be 'light' or 'dark', not {shade!r}")
    sh: Shade = "light" if shade == "light" else "dark"
    cell = _cell(token)
    cat = load_catalog()
    glyph = cat.cell_glyph(cell if isinstance(cell, Square) else EMPTY, sh)
    assert glyph is not None
    d = svgpath.to_svg(svgpath.parse(cat.outlines[glyph.outline]))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 2000"><path d="{d}"/></svg>'
