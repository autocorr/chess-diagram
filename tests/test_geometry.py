from __future__ import annotations

import pytest

from gcdiagram.fen import parse
from gcdiagram.geometry import SINGLE, U, border_rects, layout, parse_arrow
from gcdiagram.options import RenderOptions


def covered(rects: list, x: float, y: float) -> bool:
    return any(rx <= x < rx + w and ry <= y < ry + h for rx, ry, w, h in rects)


def test_single_frame_is_four_merged_rects() -> None:
    rects = border_rects(parse("8/8/8/8/8/8/8/8"), "single", SINGLE, SINGLE)
    assert len(rects) == 4
    assert (0, 0, 8 * U + 2 * SINGLE, SINGLE) in rects


def test_no_border() -> None:
    assert border_rects(parse("..2../6"), "none", 0, 0) == []


def test_hole_is_outlined_without_gaps() -> None:
    # Hole at b2 in a 3x3 board: a 100-unit ring inside the hole cell.
    rects = border_rects(parse("3/1.1/3"), "single", 0, 0)
    hx, hy = U, U  # top-left of the hole cell
    for x, y in [
        (hx + 50, hy + 50),  # top-left corner of the ring
        (hx + U - 50, hy + U - 50),  # bottom-right corner
        (hx + U / 2, hy + 50),  # top edge
        (hx + 50, hy + U / 2),  # left edge
    ]:
        assert covered(rects, x, y), (x, y)
    assert not covered(rects, hx + U / 2, hy + U / 2)


def test_outline_follows_shape_and_fills_convex_corners() -> None:
    board = parse(".1/2")  # an L shape: a2 missing
    rects = border_rects(board, "outline", SINGLE, SINGLE)
    o = SINGLE
    assert covered(rects, o + U + 50, o - 50)  # above b2
    assert covered(rects, o + U - 50, o - 50)  # convex corner at b2 top-left
    assert covered(rects, o + 50, o + U - 50)  # above a1 (the hole's floor)
    assert covered(rects, o - 50, o + U - 50)  # convex corner at a1 top-left
    assert not covered(rects, o + 50, o + 50)  # inside the hole


def test_frame_skips_outer_edges_but_keeps_hole_edges() -> None:
    rects = border_rects(parse(".1/2"), "single", SINGLE, SINGLE)
    o = SINGLE
    assert covered(rects, o + U - 50, o + U / 2)  # b2's left edge, facing the hole
    assert covered(rects, o + U / 2, o + U - 50)  # a1's top edge, facing the hole


def test_layout_sizes() -> None:
    lay = layout(parse("8/8/8/8/8/8/8/8"))
    assert (lay.width, lay.height) == (8 * U + 200, 8 * U + 200)
    lay = layout(parse("8/8/8/8/8/8/8/8"), RenderOptions(border="double", padding=10))
    assert lay.width == 8 * U + 700 + 2 * 10 * U / 20


def test_blank_light_squares_are_not_placed() -> None:
    lay = layout(parse("8/8/8/8/8/8/8/8"))
    assert len(lay.glyphs) == 32
    assert {g.key for g in lay.glyphs} == {"square:dark"}


def test_glyph_uses_know_their_square() -> None:
    lay = layout(parse("8/8/8/8/8/8/8/4K3"))
    assert [g.square for g in lay.glyphs if g.key.startswith("piece")] == ["e1"]


def test_walls() -> None:
    assert len(layout(parse("*")).rects) == 5  # wall + 4 frame sides
    lay = layout(parse("*"), RenderOptions(wall="box"))
    assert lay.glyphs[0].key == "special:box:none:dark"


def test_caption_and_piece_count() -> None:
    lay = layout(parse("K6k/8"), RenderOptions(caption=["#2"], piece_count=True))
    texts = {t.text: t for t in lay.texts}
    assert set(texts) == {"#2", "(1+1)"}
    assert texts["(1+1)"].anchor == "end"
    assert lay.height > 2 * U + 200
    lay = layout(parse("{=Q}"), RenderOptions(piece_count=True))
    assert [t.text for t in lay.texts] == ["(0+0+1)"]


def test_wide_caption_widens_diagram() -> None:
    lay = layout(parse("K"), RenderOptions(caption=["a very long caption line"]))
    assert lay.width > U + 200


@pytest.mark.parametrize("spec", ["e2-e4", "e2e4", "e2 > e4", "e2xe4", ("e2", "e4")])
def test_arrow_specs(spec: str | tuple[str, str]) -> None:
    assert parse_arrow(spec) == ("e2", "e4")


def test_arrow_points_from_centre_to_centre() -> None:
    lay = layout(parse("8/8/8/8/8/8/8/8"), RenderOptions(arrows=["a1-a3"]))
    (pts,) = lay.arrows
    tip = pts[3]
    assert tip == (SINGLE + U / 2, SINGLE + 5 * U + U / 2)


@pytest.mark.parametrize("spec", ["a1-a1", "a1-i1", "a1-a9", "nonsense"])
def test_bad_arrows(spec: str) -> None:
    with pytest.raises(ValueError):
        layout(parse("8/8/8/8/8/8/8/8"), RenderOptions(arrows=[spec]))
