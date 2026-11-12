"""Annotations: arrows, circles, crosses, squares, triangles, dots and labels in fixed colors."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from helpers import pdf_content

from gcdiagram.annotations import FILL, LABEL_CHARS, Annotation, parse_annotation
from gcdiagram.cli import main
from gcdiagram.editor import info, options_from, render
from gcdiagram.fen import parse
from gcdiagram.geometry import HALO, LABEL_CAP, LABEL_INSET, LABEL_SIZE, U, layout
from gcdiagram.options import RenderOptions
from gcdiagram.render.pdf import render_pdf
from gcdiagram.render.svg import render_svg
from gcdiagram.render.tex import render_tex
from gcdiagram.textmetrics import CAP_HEIGHT, text_width

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
        ("label:e4:tr:A", Annotation("label", ("e4",), corner="tr", symbol="A")),
        (" Label : E4 : BL : a : Blue ", Annotation("label", ("e4",), "blue", "bl", "a")),
        ("label:h8:tl:::green", Annotation("label", ("h8",), "green", "tl", ":")),
        ("label:h8:br::", Annotation("label", ("h8",), corner="br", symbol=":")),
        ("label:a1:tl:~", Annotation("label", ("a1",), corner="tl", symbol="~")),
    ],
)
def test_parse(spec: str, parsed: Annotation) -> None:
    assert parse_annotation(spec) == parsed
    assert parse_annotation(str(parsed)) == parsed


def test_text_form_omits_black() -> None:
    assert str(Annotation("square", ("c3",))) == "square:c3"
    assert str(Annotation("arrow", ("e2", "e4"), "gray")) == "arrow:e2-e4:gray"
    assert str(Annotation("label", ("e4",), corner="tr", symbol="A")) == "label:e4:tr:A"
    assert str(Annotation("label", ("e4",), "blue", "br", ":")) == "label:e4:br:::blue"


@pytest.mark.parametrize(
    "spec",
    [
        "e4",
        "star:e4",
        "circle:e4:red",
        "arrow:e2",
        "circle:e2-e4",
        "circle:4e",
        "label:e4",
        "label:e4:tr",
        "label:e4:ne:A",
        "label:e4:tr:AB",
        "label:e4:tr: ",
        "label:e4:tr:\u00e9",
        "label:e4:tr:A:red",
        "label:e2-e4:tr:A",
        "circle:e4:tr:A",
    ],
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
def test_marks_are_centered_in_their_square(kind: str) -> None:
    lay = layout(parse(EMPTY), RenderOptions(annotations=[f"{kind}:e4"]))
    (mark,) = lay.marks
    x0, y0, x1, y1 = _bounds(mark.path)
    # e4 is column 4, row 4 from the top; its center:
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


def test_colors_all_outlined() -> None:
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


def test_only_labels_have_corners_and_symbols() -> None:
    with pytest.raises(ValueError, match="only labels"):
        Annotation("circle", ("e4",), corner="tr")
    with pytest.raises(ValueError, match="corner"):
        Annotation("label", ("e4",), symbol="A")


def test_label_characters_are_printable_ascii() -> None:
    assert LABEL_CHARS[0] == "!" and LABEL_CHARS[-1] == "~" and len(LABEL_CHARS) == 94


@pytest.mark.parametrize(
    ("corner", "anchor", "dx", "baseline"),
    [
        ("tl", "start", LABEL_INSET, LABEL_INSET + LABEL_CAP),
        ("tr", "end", U - LABEL_INSET, LABEL_INSET + LABEL_CAP),
        ("bl", "start", LABEL_INSET, U - LABEL_INSET),
        ("br", "end", U - LABEL_INSET, U - LABEL_INSET),
    ],
)
def test_labels_sit_in_their_corner(corner: str, anchor: str, dx: float, baseline: float) -> None:
    lay = layout(parse(EMPTY), RenderOptions(annotations=[f"label:e4:{corner}:A:green"]))
    assert lay.marks == []
    (label,) = lay.labels
    x0, y0 = lay.board_x + 4 * U, lay.board_y + 4 * U  # e4's top-left corner
    assert (label.x, label.y, label.anchor) == (x0 + dx, y0 + baseline, anchor)
    assert (label.text, label.fill, label.halo) == ("A", "#009E73", HALO)


def test_label_capitals_are_30_percent_of_a_square() -> None:
    assert LABEL_CAP == 0.3 * U and LABEL_INSET == 0.08 * U
    assert LABEL_SIZE * CAP_HEIGHT == pytest.approx(LABEL_CAP)  # noqa: SIM300


def test_label_off_the_board() -> None:
    with pytest.raises(ValueError, match="off the board"):
        layout(parse(EMPTY), RenderOptions(annotations=["label:i1:tl:A"]))


def test_label_svg() -> None:
    opts = RenderOptions(annotations=["label:e4:tr:<:blue", "label:e4:tl:A"])
    root = ET.fromstring(render_svg(EMPTY, opts))
    (group,) = [g for g in root.iter(f"{SVG}g") if g.get("font-weight") == "bold"]
    halo, fill, halo2, fill2 = group.findall(f"{SVG}text")
    assert (halo.text, halo.get("stroke"), halo.get("stroke-width"), halo.get("fill")) == (
        "<",
        "#fff",
        "120",
        "none",
    )
    assert (fill.text, fill.get("fill"), fill.get("text-anchor")) == ("<", "#0072B2", "end")
    assert (fill2.text, fill2.get("text-anchor"), halo2.get("x")) == ("A", None, fill2.get("x"))


def test_label_pdf() -> None:
    pdf = render_pdf(EMPTY, RenderOptions(annotations=["label:e4:br:):vermilion"]))
    content = pdf_content(pdf)
    assert b"/BaseFont/Helvetica-Bold" in pdf
    # Right-aligned by the Helvetica-Bold width; stroked in white, then filled.
    lay = layout(parse(EMPTY), RenderOptions(annotations=["label:e4:br:)"]))
    x = lay.labels[0].x - text_width(")", LABEL_SIZE, bold=True)
    assert f"1 0 0 -1 {x:g} " in content
    assert re.search(r"q 1 G 120 w 1 j BT/F1 [\d.]+ Tf .*? 1 Tr \(\\\)\)Tj ET Q", content)
    assert re.search(r"q \.84 \.37 0 rg BT/F1 .*? \(\\\)\)Tj ET Q", content)


def test_label_tex() -> None:
    out = render_tex(EMPTY, RenderOptions(annotations=["label:e4:tl:%:gray", "label:a1:br:A"]))
    labels = re.findall(r"\\gclabel((?:\{[^}]*\}){7})%", out)
    assert labels == [
        "{808080}{.06}{.41783}{4.13}{3.67}{left}{37}",
        "{000000}{.06}{.41783}{.97}{.13}{right}{65}",
    ]


def test_editor_label_info() -> None:
    label = info()["label"]
    assert (label["chars"], label["size"], label["halo"], label["fills"]) == (
        LABEL_CHARS,
        LABEL_SIZE,
        HALO,
        FILL,
    )
    # Where each corner's label goes, from its square's top-left corner.
    i, cap = LABEL_INSET, LABEL_CAP
    assert label["corners"] == {
        "tl": {"x": i, "y": i + cap, "anchor": "start"},
        "tr": {"x": U - i, "y": i + cap, "anchor": "end"},
        "bl": {"x": i, "y": U - i, "anchor": "start"},
        "br": {"x": U - i, "y": U - i, "anchor": "end"},
    }


def test_editor_lists_annotations_parsed_and_canonical() -> None:
    out = render(EMPTY, {"annotations": [" Label : E4 : TR : a : Blue ", "arrow:e2e4"]})
    assert out["annotations"] == [
        {
            "spec": "label:e4:tr:a:blue",
            "kind": "label",
            "squares": "e4",
            "color": "blue",
            "corner": "tr",
            "symbol": "a",
        },
        {
            "spec": "arrow:e2-e4",
            "kind": "arrow",
            "squares": "e2-e4",
            "color": "black",
            "corner": "",
            "symbol": "",
        },
    ]
