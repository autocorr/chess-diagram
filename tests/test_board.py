from __future__ import annotations

import pytest

from gcdiagram.board import EMPTY, HOLE, WALL, Board, Piece, Special, Square, parse_square
from gcdiagram.catalog import load_catalog


def test_a1_is_dark_and_shades_alternate() -> None:
    b = Board.empty()
    assert b.shade(7, 0) == "dark"  # a1
    assert b.shade(0, 7) == "dark"  # h8
    assert b.shade(0, 0) == "light"  # a8
    assert b.shade(7, 1) == "light"  # b1


def test_a1_dark_on_odd_heights() -> None:
    b = Board.empty(5, 5)
    assert b.shade(4, 0) == "dark"
    assert b.shade(0, 0) == "dark"


def test_square_names_round_trip() -> None:
    b = Board.empty(10, 12)
    assert parse_square("a1", 12) == (11, 0)
    assert parse_square("j12", 12) == (0, 9)
    for r in range(b.height):
        for c in range(b.width):
            assert parse_square(b.square_name(r, c), b.height) == (r, c)


def test_bad_square_names() -> None:
    for name in ("", "a0", "a9", "1a", "A1"):
        with pytest.raises(ValueError):
            parse_square(name, 8)


def test_indexing_by_name() -> None:
    b = Board.empty()
    b["e4"] = Square(Piece("Q", "white"))
    assert b[(4, 4)] == Square(Piece("Q", "white"))


def test_rejects_ragged_and_oversized() -> None:
    with pytest.raises(ValueError):
        Board([[EMPTY, EMPTY], [EMPTY]])
    with pytest.raises(ValueError):
        Board.empty(27, 1)


def test_board_square_excludes_holes_not_walls() -> None:
    b = Board([[HOLE, WALL, EMPTY]])
    assert [b.is_board_square(0, c) for c in range(-1, 4)] == [False, False, True, True, False]


def test_piece_validation() -> None:
    with pytest.raises(ValueError):
        Piece("X", "white")
    with pytest.raises(ValueError):
        Piece("Q", "white", 30)


def test_piece_count() -> None:
    b = Board(
        [
            [
                Square(Piece("K", "white")),
                Square(Piece("K", "black")),
                Square(Piece("Q", "neutral")),
                Square(Special("star", "white")),
            ]
        ]
    )
    assert b.piece_count() == (1, 1, 1)


def test_catalog_resolves_figures() -> None:
    cat = load_catalog()
    g = cat.figure_glyph(Piece("Q", "white", 90), "dark")
    assert (g.font, g.code) == ("D", 0x4C)
    assert cat.figure_glyph(Piece("K", "black", 90), "dark").dx == -233
    assert cat.supports(Piece("N", "black", 180, "mirror"))
    assert not cat.supports(Piece("N", "black", 0, "mirror"))
    assert not cat.supports(Piece("Q", "neutral", 45))
    assert cat.specials["hourglass"] == {"white", "black", "neutral"}
    assert cat.specials["box"] == {"none"}
    with pytest.raises(KeyError, match="no glyph"):
        cat.figure_glyph(Special("nope", "white"), "light")


def test_catalog_resolves_cells() -> None:
    cat = load_catalog()
    queen = Piece("Q", "white", 90)
    assert cat.cell_glyph(Square(queen), "dark") == cat.figure_glyph(queen, "dark")
    assert cat.cell_glyph(EMPTY, "light") == cat["square:light"]
    assert cat.cell_glyph(HOLE, "dark") is None
    assert cat.cell_glyph(WALL, "dark") is None
    assert cat.cell_glyph(WALL, "dark", "box") == cat["special:box:none:dark"]
