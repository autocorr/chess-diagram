from __future__ import annotations

import json
from pathlib import Path

import pytest

from gcdiagram.board import EMPTY, Board, Hole, Piece, Special, Square, Wall
from gcdiagram.fen import FenError, parse, serialize

VECTORS = json.loads((Path(__file__).parent / "vectors.json").read_text())


def describe(board: Board) -> dict[str, str]:
    out: dict[str, str] = {}
    for r, row in enumerate(board.cells):
        for c, cell in enumerate(row):
            name = board.square_name(r, c)
            if isinstance(cell, Hole):
                out[name] = "hole"
            elif isinstance(cell, Wall):
                out[name] = "wall"
            elif cell != EMPTY:
                assert isinstance(cell, Square)
                f = cell.figure
                if isinstance(f, Piece):
                    out[name] = f"piece:{f.kind}:{f.color}:{f.angle}:{f.variant}"
                elif isinstance(f, Special):
                    out[name] = f"special:{f.name}:{f.color}"
    return out


@pytest.mark.parametrize("case", VECTORS["valid"], ids=lambda c: c["fen"][:40])
def test_valid_vectors(case: dict) -> None:
    board = parse(case["fen"])
    assert (board.width, board.height) == (case["width"], case["height"])
    assert describe(board) == case["cells"]
    assert serialize(board) == case["canonical"]
    assert serialize(parse(case["canonical"])) == case["canonical"]


@pytest.mark.parametrize("case", VECTORS["invalid"], ids=lambda c: c["fen"][:40] or "<empty>")
def test_invalid_vectors(case: dict) -> None:
    with pytest.raises(FenError) as info:
        parse(case["fen"])
    assert info.value.code == case["error"]


def test_error_reports_position() -> None:
    with pytest.raises(FenError) as info:
        parse("  8/8/8/8/8/8/8/7X")
    assert info.value.pos == 17
    assert "character 18" in str(info.value)


def test_rest_of_fen_is_ignored() -> None:
    assert serialize(parse("K w - - 0 1")) == "K"
    assert serialize(parse("K\tgarbage {")) == "K"
