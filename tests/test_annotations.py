"""Annotations: arrows, circles, crosses, squares, triangles and dots in fixed colours."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from gcdiagram.annotations import FILL, Annotation, parse_annotation
from gcdiagram.cli import main
from gcdiagram.editor import options_from, render
from gcdiagram.fen import parse
from gcdiagram.geometry import HALO, U, layout
from gcdiagram.options import RenderOptions
from gcdiagram.render.pdf import render_pdf
from gcdiagram.render.svg import render_svg
from gcdiagram.render.tex import render_tex

SVG = "{http://www.w3.org/2000/svg}"
EMPTY = "8/8/8/8/8/8/8/8"


@pytest.mark.parametrize(
    ("spec", "parsed"),
    [
        ("circle:e4", Annotation("circle", ("e4",))),
        (" Cross : h8 : Blue ", Annotation("cross", ("h8",), "blue")),
        ("arrow:e2-e4:vermilion", Annotation("arrow", ("e2", "e4"), "vermilion")),
        ("arrow:e2e4", Annotation("arrow", ("e2", "e4"))),
        ("triangle:a1:green", Annotation("triangle", ("a1",), "green")),
    ],
)
def test_parse(spec: str, parsed: Annotation) -> None:
    assert parse_annotation(spec) == parsed
    assert parse_annotation(str(parsed)) == parsed


def test_text_form_omits_black() -> None:
    assert str(Annotation("square", ("c3",))) == "square:c3"
    assert str(Annotation("arrow", ("e2", "e4"), "gray")) == "arrow:e2-e4:gray"


@pytest.mark.parametrize(
    "spec", ["e4", "star:e4", "circle:e4:red", "arrow:e2", "circle:e2-e4", "circle:4e"]
)
def test_bad_specs(spec: str) -> None:
    with pytest.raises(ValueError, match="bad annotation"):
        parse_annotation(spec)
    with pytest.raises(ValueError):
        RenderOptions(annotations=[spec])


def test_bare_string_is_rejected() -> None:
    with pytest.raises(TypeError):
        RenderOptions(annotations="circle:e4")


@pytest.mark.parametrize("spec", ["circle:i1", "cross:a9", "arrow:a1-i1"])
def test_off_the_board(spec: str) -> None:
    with pytest.raises(ValueError):
        layout(parse(EMPTY), RenderOptions(annotations=[spec]))


def _bounds(path: list) -> tuple[float, float, float, float]:
    xs = [v for seg in path for v in seg[1::2]]
    ys = [v for seg in path for v in seg[2::2]]
    return min(xs), min(ys), max(xs), max(ys)


@pytest.mark.parametrize("kind", ["circle", "cross", "square", "triangle", "dot"])
def test_marks_are_centred_in_their_square(kind: str) -> None:
    lay = layout(parse(EMPTY), RenderOptions(annotations=[f"{kind}:e4"]))
    (mark,) = lay.marks
    x0, y0, x1, y1 = _bounds(mark.path)
    # e4 is column 4, row 4 from the top; its centre:
    cx, cy = lay.board_x + 4.5 * U, lay.board_y + 4.5 * U
    assert (x0 + x1) / 2 == pytest.approx(cx, abs=1)
    assert (y0 + y1) / 2 == pytest.approx(cy, abs=1)
    assert lay.board_x + 4 * U < x0 and x1 < lay.board_x + 5 * U  # inside the square
    assert lay.board_y + 4 * U < y0 and y1 < lay.board_y + 5 * U


def test_rings_have_two_contours_and_the_cross_one() -> None:
    specs = ["circle:a1", "square:b1", "triangle:c1", "cross:d1", "dot:e1"]
    lay = layout(parse(EMPTY), RenderOptions(annotations=specs))
    contours = [sum(seg[0] == "M" for seg in m.path) for m in lay.marks]
    assert contours == [2, 2, 2, 1, 1]


def test_dot_is_a_fifth_of_a_square_across() -> None:
    (mark,) = layout(parse(EMPTY), RenderOptions(annotations=["dot:e4"])).marks
    x0, y0, x1, y1 = _bounds(mark.path)
    assert x1 - x0 == pytest.approx(0.2 * U) and y1 - y0 == pytest.approx(0.2 * U)


def test_arrow_matches_the_plain_arrow() -> None:
    board = parse(EMPTY)
    plain = layout(board, RenderOptions(arrows=["e2-e4"])).arrows[0]
    (mark,) = layout(board, RenderOptions(annotations=["arrow:e2-e4:blue"])).marks
    assert [seg[1:] for seg in mark.path if seg[0] != "Z"] == plain
    assert mark.fill == FILL["blue"] == "#0072B2"


def test_colours_all_outlined() -> None:
    specs = [f"circle:a{i + 1}:{c}" for i, c in enumerate(FILL)]
    marks = layout(parse(EMPTY), RenderOptions(annotations=specs)).marks
    assert [(m.fill, m.halo) for m in marks] == [
        ("#000", HALO),
        ("#808080", HALO),
        ("#D55E00", HALO),
        ("#0072B2", HALO),
        ("#009E73", HALO),
    ]


def test_svg() -> None:
    opts = RenderOptions(annotations=["circle:e4", "cross:d5:vermilion"])
    root = ET.fromstring(render_svg(EMPTY, opts))
    paths = [p for p in root.iter(f"{SVG}path") if p.get("stroke") or p.get("fill")]
    halo, ring, cross_halo, cross = paths[-4:]
    assert (halo.get("fill"), halo.get("stroke"), halo.get("stroke-width")) == (
        "none",
        "#fff",
        "120",
    )
    assert halo.get("d") == ring.get("d") and ring.get("fill") == "#000"
    assert cross.get("fill") == "#D55E00" and cross_halo.get("stroke") == "#fff"


def test_pdf() -> None:
    plain = render_pdf(EMPTY)
    pdf = render_pdf(EMPTY, RenderOptions(annotations=["triangle:e4"]))
    assert pdf != plain and pdf.startswith(b"%PDF-1.4")


def test_tex() -> None:
    out = render_tex(EMPTY, RenderOptions(annotations=["circle:e4", "arrow:e2-e4:gray"]))
    marks = re.findall(r"\\gcmark\{(\w+)\}\{([.\d]+)\}\{(.*?)\}%", out)
    assert [(rgb, halo) for rgb, halo, _ in marks] == [("000000", ".06"), ("808080", ".06")]
    assert r"\gcq{" in marks[0][2] and marks[0][2].count(r"\gcz") == 2


def test_editor_and_cli(tmp_path: Path) -> None:
    opts = options_from({"annotations": ["circle:e4", ""]})
    assert opts == RenderOptions(annotations=("circle:e4",))
    assert render(EMPTY, {"annotations": ["circle:z9"]})["code"] == "error"
    out = tmp_path / "d.svg"
    assert main([EMPTY, "-m", "circle:e4:blue", "-o", str(out)]) == 0
    assert 'fill="#0072B2"' in out.read_text()
    assert main([EMPTY, "-m", "circle:e4:red"]) == 2
