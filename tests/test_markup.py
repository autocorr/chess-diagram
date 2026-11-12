"""Caption markup (<b>, <i>), captions above the board, and how each format draws them."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from helpers import pdf_content

from gcdiagram.cli import main
from gcdiagram.editor import options_from
from gcdiagram.fen import parse
from gcdiagram.geometry import ASCENT, CAPTION_GAP, LINE_HEIGHT, U, layout, wrap_caption
from gcdiagram.markup import Run, parse_markup
from gcdiagram.options import RenderOptions
from gcdiagram.render.pdf import render_pdf
from gcdiagram.render.svg import render_svg
from gcdiagram.render.tex import caption_tex, render_tex
from gcdiagram.textmetrics import CAP_HEIGHT, text_width

SVG = "{http://www.w3.org/2000/svg}"


def test_parse_markup() -> None:
    assert parse_markup("<b>Helpmate</b> in 2, <i>set <B>play</b></i>") == [
        Run("Helpmate", bold=True),
        Run(" in 2, "),
        Run("set ", italic=True),
        Run("play", bold=True, italic=True),
    ]


def test_markup_leaves_other_text_alone() -> None:
    # '*' marks set play in stipulations, and only <b>, <i> and their ends are tags.
    assert parse_markup("h#2* a<b <u>x</u> 3 < 4") == [Run("h#2* a<b <u>x</u> 3 < 4")]
    assert parse_markup("<b>open to the end") == [Run("open to the end", bold=True)]
    assert parse_markup("<b></b>") == []


def test_bold_is_wider() -> None:
    assert text_width("Helpmate", 1000, bold=True) > text_width("Helpmate", 1000)
    assert text_width(" ", 1000, bold=True) == text_width(" ", 1000)


def test_wrapping_measures_styled_words() -> None:
    size = 1000
    word = text_width("mmmm", size, bold=True)
    # Fits two bold words a line only if they are measured as bold.
    lines = wrap_caption(["<b>mmmm mmmm mmmm</b>"], size, 2 * word + 300, 0)
    assert [[r.text for r in line] for line in lines] == [["mmmm mmmm"], ["mmmm"]]
    # Words keep their own styles; the space joins the preceding run.
    (line,) = wrap_caption(["a <i>b</i> c"], size, 10_000, 0)
    assert line == (Run("a "), Run("b ", italic=True), Run("c"))


def test_caption_above_is_left_aligned_over_the_board() -> None:
    opts = RenderOptions(caption_above=["J. Smith", "<i>The Problemist</i>"], caption=["#2"])
    lay = layout(parse("8/8"), opts)
    size = opts.caption_size * U
    pitch = size * LINE_HEIGHT
    above, first, below = lay.texts
    assert (above.text, first.text, below.text) == ("J. Smith", "The Problemist", "#2")
    assert above.x == first.x == below.x == 0
    assert first.y - above.y == pytest.approx(pitch)
    # The last baseline above is CAPTION_GAP from the frame (100 units thick).
    assert lay.board_y - 100 - first.y == pytest.approx(CAPTION_GAP)
    assert lay.board_y == pytest.approx(ASCENT * size + pitch + CAPTION_GAP + 100)
    assert below.y > lay.board_y + 2 * U
    plain_lay = layout(parse("8/8"), RenderOptions(caption=["#2"]))
    assert lay.height == pytest.approx(plain_lay.height + ASCENT * size + pitch + CAPTION_GAP)


def test_captions_sit_the_same_distance_from_the_frame() -> None:
    # Above: frame to the last baseline. Below: frame to the top of the capitals.
    opts = RenderOptions(caption_above=["J. Smith"], caption=["#2"])
    lay = layout(parse("8/8"), opts)
    above, below = lay.texts
    top = lay.board_y - 100
    bottom = lay.board_y + 2 * U + 100
    cap = CAP_HEIGHT * opts.caption_size * U
    assert top - above.y == pytest.approx(CAPTION_GAP)
    assert (below.y - cap) - bottom == pytest.approx(CAPTION_GAP)


def test_long_word_above_widens_the_diagram() -> None:
    lay = layout(parse("K"), RenderOptions(caption_above=["<b>Supercalifragilistic</b>"]))
    size = RenderOptions().caption_size * U
    assert lay.width == pytest.approx(text_width("Supercalifragilistic", size, bold=True))


def test_svg_uses_tspans_for_styled_runs() -> None:
    opts = RenderOptions(caption_above=["<i>The Problemist</i> 2024"], caption=["#2"])
    root = ET.fromstring(render_svg("8", opts))
    above, below = root.iter(f"{SVG}text")
    assert above.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"
    (span,) = above.iter(f"{SVG}tspan")
    assert (span.get("font-style"), span.text, span.tail) == ("italic", "The Problemist ", "2024")
    assert below.text == "#2" and below.get("{http://www.w3.org/XML/1998/namespace}space") is None


def test_pdf_switches_fonts_within_a_line() -> None:
    pdf = render_pdf("8", RenderOptions(caption=["<b>#2</b> <i>set</i>"]))
    assert b"/BaseFont/Helvetica-Bold/" in pdf and b"/BaseFont/Helvetica-Oblique/" in pdf
    assert b"/BaseFont/Helvetica/" not in pdf  # no plain run, so no plain font
    # Fonts are numbered by style: F1 italic, F2 bold.
    line = r"BT/F2 900 Tf 1 0 0 -1 0 [\d.]+ Tm \(#2 \)Tj/F1 900 Tf\(set\)Tj ET"
    assert re.search(line, pdf_content(pdf))


def test_tex_caption_markup() -> None:
    assert (
        caption_tex("<b>#2</b> & <i>x<b>y</b></i>")
        == r"\textbf{\#2} \& \textit{x}\textbf{\textit{y}}"
    )
    out = render_tex("K", RenderOptions(caption_above=["<i>J. Smith</i>"], caption=["#2"]))
    assert out.startswith(r"\gcbox[{\textit{J. Smith}}]{1.1}{1.1}{%")
    assert out.endswith(r"}{\#2}{}%" + "\n")
    assert not render_tex("K").startswith(r"\gcbox[")


def test_editor_and_cli_pass_captions_above(tmp_path) -> None:
    opts = options_from({"caption_above": ["A", " "], "caption": ["B"]})
    assert opts == RenderOptions(caption_above=("A",), caption=("B",))
    out = tmp_path / "d.svg"
    assert main(["K", "-C", "<b>A</b>", "-c", "B", "-o", str(out)]) == 0
    assert 'font-weight="bold">A</tspan>' in out.read_text()
