"""The editor bridge (gcdiagram.editor), which the browser calls through Pyodide."""

from __future__ import annotations

import xml.etree.ElementTree as ET

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
    assert info["specials"]["hourglass"] == {
        "white": "{@Hourglass}",
        "black": "{@hourglass}",
        "neutral": "{=@hourglass}",
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
