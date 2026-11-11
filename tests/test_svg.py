"""SVG output: structure, options and golden files.

Regenerate golden files after an intended change with:
    GCDIAGRAM_REGEN=1 uv run pytest tests/test_svg.py
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from cases import CASES

from gcdiagram.fen import parse
from gcdiagram.options import RenderOptions
from gcdiagram.render.svg import render_svg

GOLDEN = Path(__file__).parent / "golden"
SVG = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize("name", CASES)
def test_golden(name: str) -> None:
    fen, opts = CASES[name]
    out = render_svg(parse(fen), opts)
    path = GOLDEN / f"{name}.svg"
    if os.environ.get("GCDIAGRAM_REGEN"):
        path.parent.mkdir(exist_ok=True)
        path.write_text(out)
    assert out == path.read_text(), f"{name}.svg changed; regenerate if intended"


@pytest.mark.parametrize("name", CASES)
def test_structure(name: str) -> None:
    fen, opts = CASES[name]
    root = ET.fromstring(render_svg(parse(fen), opts))
    ids = [p.get("id") for p in root.iter(f"{SVG}path") if p.get("id")]
    assert len(ids) == len(set(ids))
    refs = {u.get("href", "")[1:] for u in root.iter(f"{SVG}use")}
    assert refs == set(ids), "every definition is used and every use is defined"
    w, h = (float(v) for v in root.get("viewBox", "").split()[2:])
    assert root.get("width") == f"{w * opts.square_size / 2000:g}pt"
    assert h > 0


def test_id_prefix_and_xlink() -> None:
    out = render_svg(parse("K"), id_prefix="d7", xlink=True)
    assert 'id="d7a"' in out
    assert 'xlink:href="#d7a"' in out
    assert 'xmlns:xlink="http://www.w3.org/1999/xlink"' in out
    ET.fromstring(out)


def test_annotate() -> None:
    out = render_svg(parse("8/8/8/8/8/8/8/4K3"), annotate=True)
    assert 'data-square="e1"' in out


def test_transparent_background() -> None:
    assert "<rect" not in render_svg(parse("K"), RenderOptions(background=None))


def test_caption_is_escaped() -> None:
    out = render_svg(parse("K"), RenderOptions(caption=["<h#2> & more"]))
    assert "&lt;h#2&gt; &amp; more" in out
    ET.fromstring(out)


def test_glyph_defined_once() -> None:
    out = render_svg(parse("8/8/8/8/8/8/8/8"))
    assert len(re.findall(r"<path id=", out)) == 1
    assert len(re.findall(r"<use ", out)) == 32


def test_size_of_standard_position() -> None:
    out = render_svg(parse("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"))
    assert len(out) < 40_000
