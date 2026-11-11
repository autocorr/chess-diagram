from __future__ import annotations

import pytest
from fontTools.pens.recordingPen import RecordingPen
from fontTools.svgLib.path import parse_path

from gcdiagram import svgpath
from gcdiagram.catalog import load_catalog


def drawn(d: str) -> list:
    pen = RecordingPen()
    parse_path(d, pen)
    return [(op, [tuple(round(v, 6) for v in pt) for pt in args]) for op, args in pen.value]


@pytest.mark.parametrize(
    ("v", "s"),
    [
        (0, "0"),
        (12, "12"),
        (-3.5, "-3.5"),
        (0.5, ".5"),
        (-0.25, "-.25"),
        (1 / 3, ".33"),
        (-0.0, "0"),
    ],
)
def test_fmt(v: float, s: str) -> None:
    assert svgpath.fmt(v) == s


def test_compact_svg_draws_the_same_outline_for_every_glyph() -> None:
    for d in load_catalog().outlines.values():
        assert drawn(svgpath.to_svg(svgpath.parse(d))) == drawn(d)


def test_compact_svg_is_smaller() -> None:
    outlines = load_catalog().outlines.values()
    before = sum(len(d) for d in outlines)
    after = sum(len(svgpath.to_svg(svgpath.parse(d))) for d in outlines)
    assert after < 0.8 * before


def test_separators() -> None:
    segs = [("M", 0.5, 0.5), ("L", 1.0, 1.0), ("L", 0.5, -1.0), ("Z",)]
    assert svgpath.to_svg(segs) == "m.5.5l.5.5-.5-2z"


def test_pdf_raises_quadratics_to_cubics() -> None:
    ops = svgpath.to_pdf([("M", 0, 0), ("Q", 3, 3, 6, 0), ("L", 6, 6), ("Z",)])
    assert ops.splitlines() == ["0 0 m", "2 2 4 2 6 0 c", "6 6 l", "h"]


def test_rejects_relative_input() -> None:
    with pytest.raises(ValueError):
        svgpath.parse("m0 0l1 1z")
