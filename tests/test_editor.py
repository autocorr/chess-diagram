"""The editor bridge (gcdiagram.editor), which the browser calls through Pyodide."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from gcdiagram import editor
from gcdiagram.options import RenderOptions
from gcdiagram.render.pdf import render_pdf
from gcdiagram.render.svg import render_svg
from gcdiagram.render.tex import render_tex

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"


def test_info_lists_supported_pieces_and_specials() -> None:
    info = editor.info()
    tokens = {p["token"] for p in info["pieces"]}
    assert {"K", "q", "{Q90}", "{=R180}", "{~P}", "{!n270}"} <= tokens
    assert "{=Q45}" not in tokens and "{!N}" not in tokens
    assert len(info["pieces"]) == 6 * 8 * 2 + 6 * 4 + 6 * 2 + 3 * 2
    assert info["specials"]["equihopper"] == {
        "white": "{@Equihopper}",
        "black": "{@equihopper}",
        "neutral": "{=@equihopper}",
    }
    assert info["specials"]["star"] == {"white": "{@Star}", "black": "{@star}"}
    assert info["specials"]["box"] == dict.fromkeys(["white", "black", "neutral"], "{@box}")


def test_render_returns_canonical_fen_svg_and_geometry() -> None:
    out = editor.render(START + " w KQkq - 0 1", {"border": "double"})
    assert out["fen"] == START
    assert (out["files"], out["ranks"]) == (8, 8)
    assert out["boardX"] == out["boardY"] == 350
    assert out["width"] == 8 * 2000 + 700
    assert out["cells"][7][4] == "K" and out["cells"][4][4] == ""
    root = ET.fromstring(out["svg"])
    assert root.find(".//{http://www.w3.org/2000/svg}use[@data-square='e1']") is not None


def test_render_reports_errors() -> None:
    assert editor.render("8/7") == {
        "error": "rank 2 from the top has 7 squares, the first has 8",
        "code": "uneven-ranks",
    }
    assert editor.render("8", {"arrows": ["a1-a5"]})["code"] == "error"


def test_options_from_ignores_unknown_keys_and_blank_lines() -> None:
    opts = editor.options_from({"caption": ["#2", "  "], "arrows": ["e2-e4"], "bogus": 1})
    assert opts == RenderOptions(caption=("#2",), arrows=("e2-e4",))


def test_set_cell_move_rotate_resize() -> None:
    fen = editor.set_cell("8/8", "e1", "{Q90}")["fen"]
    assert fen == "8/4{Q90}3"
    fen = editor.move(fen, "e1", "e2")["fen"]
    assert fen == "4{Q90}3/8"
    assert editor.rotate(fen, "e2")["fen"] == "4{Q135}3/8"
    assert editor.rotate(fen, "e2", -45)["fen"] == "4{Q45}3/8"
    assert editor.set_cell(fen, "a1", ".")["fen"] == "4{Q90}3/.7"
    assert editor.set_cell(fen, "e2", "")["fen"] == "8/8"
    assert editor.resize(fen, 10, 3)["fen"] == "10/4{Q90}5/10"
    assert editor.resize(fen, 3, 1)["fen"] == "3"  # rank 2 is cut off


def test_rotate_skips_unsupported_angles() -> None:
    fen = editor.set_cell("2", "a1", "{=Q}")["fen"]
    assert editor.rotate(fen, "a1")["fen"] == "{=Q90}1"  # neutral pieces skip 45
    fen = editor.set_cell("2", "a1", "{~Q}")["fen"]
    assert editor.rotate(fen, "a1")["fen"] == "{~Q}1"  # chameleon pieces only exist at 0


def test_recolor_cycles_through_the_colors_the_fonts_have() -> None:
    fen = editor.set_cell("2", "a1", "{N90}")["fen"]
    fen = editor.recolor(fen, "a1")["fen"]
    assert fen == "{n90}1"
    fen = editor.recolor(fen, "a1")["fen"]
    assert fen == "{=N90}1"
    assert editor.recolor(fen, "a1")["fen"] == "{N90}1"
    # No neutral pieces at 45 degrees, and no neutral chameleons: black goes back to white.
    assert editor.recolor("{q45}1", "a1")["fen"] == "{Q45}1"
    assert editor.recolor("{~q}1", "a1")["fen"] == "{~Q}1"
    # Specials: the equihopper has all three colors, the star no neutral, the box none.
    assert editor.recolor("{@equihopper}1", "a1")["fen"] == "{=@equihopper}1"
    assert editor.recolor("{@star}1", "a1")["fen"] == "{@Star}1"
    assert editor.recolor("{@box}1", "a1")["fen"] == "{@box}1"
    # Empty squares, holes and walls are left alone.
    assert editor.recolor("1.*", "a1")["fen"] == "1.*"
    assert editor.recolor("1.*", "b1")["fen"] == "1.*"


def test_shift_moves_figures_and_annotations_but_not_holes_or_walls() -> None:
    # 3x2:  K . *     row 0 (rank 2)
    #       q . n     row 1 (rank 1)
    fen = "K1*/q1n"
    marks = ["circle:a1", "arrow:a1-c2:blue", "label:c1:tr:A"]
    # n falls off the board; the arrow and the label would leave it too.
    assert editor.shift(fen, "right", marks) == {"fen": "1K*/1q1", "annotations": ["circle:b1"]}
    assert editor.shift(fen, "left")["fen"] == "2*/1n1"
    # n would land on the wall.
    assert editor.shift(fen, "up", marks) == {
        "fen": "q1*/3",
        "annotations": ["circle:a2", "label:c2:tr:A"],
    }
    assert editor.shift(fen, "down", ["circle:a2"]) == {
        "fen": "2*/K2",
        "annotations": ["circle:a1"],
    }
    assert editor.shift(".1/K1", "up")["fen"] == ".1/2"  # a hole swallows it too
    assert editor.shift(fen, "sideways")["code"] == "error"


def test_transform_rotates_and_mirrors_the_whole_board() -> None:
    fen = "K1*/q1n"  # 3 files, 2 ranks
    marks = ["arrow:a1-c2", "label:a2:tl:A:green"]
    # Clockwise: the bottom rank becomes the left file.
    assert editor.transform(fen, "cw", marks) == {
        "fen": "qK/2/n*",
        "annotations": ["arrow:a3-b1", "label:b3:tr:A:green"],
    }
    assert editor.transform(fen, "ccw", marks) == {
        "fen": "*n/2/Kq",
        "annotations": ["arrow:b1-a3", "label:a1:bl:A:green"],
    }
    assert editor.transform(fen, "mirror-h", marks) == {
        "fen": "*1K/n1q",
        "annotations": ["arrow:c1-a2", "label:c2:tr:A:green"],
    }
    assert editor.transform(fen, "mirror-v", marks) == {
        "fen": "q1n/K1*",
        "annotations": ["arrow:a2-c1", "label:a1:bl:A:green"],
    }
    # Four quarter turns, or two mirrors, give back the board; figures keep their angle.
    rotated = "{Q90}1./2{@star}"
    for op, times in (("cw", 4), ("ccw", 4), ("mirror-h", 2), ("mirror-v", 2)):
        out: dict[str, Any] = {"fen": rotated, "annotations": marks}
        for _ in range(times):
            out = editor.transform(out["fen"], op, out["annotations"])
        assert out == {"fen": rotated, "annotations": marks}
    assert editor.transform(fen, "flip")["code"] == "error"


def test_transform_moves_holes_and_walls_with_the_board() -> None:
    # 3 files x 4 ranks:  . . K
    #                     * - q
    #                     - - -
    #                     - . n
    fen = "..K/*1q/3/1.n"
    expected = {
        "cw": "2*./.2./n1qK",
        "ccw": "Kq1n/.2./.*2",
        "mirror-h": "K../q1*/3/n.1",
        "mirror-v": "1.n/3/*1q/..K",
    }
    for op, out in expected.items():
        assert editor.transform(fen, op)["fen"] == out
        assert "svg" in editor.render(out)  # the border still runs around the holes


def test_set_colors() -> None:
    fen = "K{q45}{~N}{=R}{@star}{@box}{=@equihopper}1"
    assert editor.set_colors(fen, "black") == {
        "fen": "k{q45}{~n}r{@star}{@box}{@equihopper}1",
        "unchanged": 0,
    }
    # No neutral pieces at 45 degrees, no neutral chameleons and no neutral star.
    assert editor.set_colors(fen, "neutral") == {
        "fen": "{=K}{q45}{~N}{=R}{@star}{@box}{=@equihopper}1",
        "unchanged": 3,
    }
    assert editor.set_colors(fen, "swap") == {
        "fen": "k{Q45}{~n}{=R}{@Star}{@box}{=@equihopper}1",
        "unchanged": 0,
    }
    assert editor.set_colors(fen, "purple")["code"] == "error"


def test_edit_errors() -> None:
    assert editor.set_cell("8", "a1", "{Q30}")["code"] == "bad-angle"
    assert editor.set_cell("8", "a1", "KK")["code"] == "error"
    assert editor.set_cell("8", "a9", "K")["code"] == "error"


def test_export_matches_the_renderers() -> None:
    opts = {"caption": ["#2"], "piece_count": True}
    ro = editor.options_from(opts)
    assert editor.export(START, opts, "svg")["data"] == render_svg(START, ro)
    assert editor.export(START, opts, "pdf")["data"] == render_pdf(START, ro)
    assert editor.export(START, opts, "tex")["data"] == render_tex(START, ro)
    assert editor.export(START, opts, "png")["code"] == "error"


def test_figure_svg() -> None:
    svg = editor.figure_svg("{Q90}", "dark")
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 2000">')
    ET.fromstring(svg)
    assert editor.figure_svg("", "light").count("<path") == 1
