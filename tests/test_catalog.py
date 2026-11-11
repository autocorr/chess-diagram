"""Catalog completeness and consistency with the spec, the fonts and the Lua copy."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import build_catalog
import catalog_spec
import pytest

ROOT = Path(__file__).resolve().parent.parent
CATALOG = json.loads(build_catalog.JSON_OUT.read_text())
GLYPHS = CATALOG["glyphs"]

KINDS = "KQRBNP"
ANGLES = range(0, 360, 45)
SHADES = ("light", "dark")


def test_every_plain_piece_angle_color_shade() -> None:
    for kind in KINDS:
        for angle in ANGLES:
            for color in ("white", "black"):
                for shade in SHADES:
                    assert f"piece:{kind}:{color}:{angle}:plain:{shade}" in GLYPHS


def test_neutral_pieces_at_right_angles() -> None:
    for kind in KINDS:
        for angle in (0, 90, 180, 270):
            for shade in SHADES:
                assert f"piece:{kind}:neutral:{angle}:plain:{shade}" in GLYPHS
        assert f"piece:{kind}:neutral:45:plain:light" not in GLYPHS


def test_chameleon_and_mirror_sets() -> None:
    for kind in KINDS:
        for color in ("white", "black"):
            for shade in SHADES:
                assert f"piece:{kind}:{color}:0:chameleon:{shade}" in GLYPHS
    for angle in (90, 180, 270):
        for color in ("white", "black"):
            for shade in SHADES:
                assert f"piece:N:{color}:{angle}:mirror:{shade}" in GLYPHS


def test_board_furniture() -> None:
    for shade in SHADES:
        assert f"square:{shade}" in GLYPHS
    for style in ("single", "double"):
        for side in ("top", "bottom", "left", "right"):
            assert f"border:{style}:{side}" in GLYPHS
    for pos in ("tl", "tr", "bl", "br"):
        assert f"corner:double:{pos}" in GLYPHS
    for style in ("single", "double"):
        assert f"label:{style}:rank:26" in GLYPHS
        assert f"label:{style}:file:z" in GLYPHS


KEY_PATTERNS = [
    r"piece:[KQRBNP]:(white|black|neutral):(0|45|90|135|180|225|270|315)"
    r":(plain|chameleon|mirror):(light|dark)",
    r"special:[a-z-]+:(white|black|neutral|none):(light|dark)",
    r"square:(light|dark)",
    r"border:(single|double):(top|bottom|left|right)",
    r"corner:double:(tl|tr|bl|br)",
    r"edge:(top|bottom|left|right)(-(top|bottom|left|right))+",
    r"symbol:[a-z-]+",
    r"label:(single|double):(rank:([1-9]|1[0-9]|2[0-6])|file:[a-z])",
]


@pytest.mark.parametrize("key", list(GLYPHS))
def test_key_is_well_formed(key: str) -> None:
    assert any(re.fullmatch(p, key) for p in KEY_PATTERNS), key
    assert GLYPHS[key]["outline"] in CATALOG["outlines"]


def test_codes_are_latin1_and_used_once_per_font() -> None:
    usage = Counter((g["font"], g["code"]) for g in GLYPHS.values())
    assert all(0x20 < code <= 0xFF for _, code in usage)
    assert [k for k, n in usage.items() if n > 1] == []


def test_outlines_are_in_cell_coordinates() -> None:
    # Board-square glyphs (pieces, specials, squares) must sit within the cell, allowing
    # for the slight overshoot of the dark-square hatching.
    for key, g in GLYPHS.items():
        if key.split(":")[0] in ("piece", "special", "square") and g["bbox"]:
            x0, y0, x1, y1 = g["bbox"]
            assert min(x0, y0) >= -20 and max(x1, y1) <= 2020, key


def test_catalog_json_is_up_to_date() -> None:
    fresh = build_catalog.build()
    assert fresh == CATALOG, "run: uv run python tools/build_catalog.py"


def test_lua_catalog_matches_json() -> None:
    lua = build_catalog.LUA_OUT.read_text()
    entries = {
        key: (font, int(code, 16), int(dx or 0))
        for key, font, code, dx in re.findall(
            r'\["([^"]+)"\] = \{ "(\w)", 0x([0-9A-F]+)(?:, (-?\d+))? \}', lua
        )
    }
    assert entries == {k: (g["font"], g["code"], g.get("dx", 0)) for k, g in GLYPHS.items()}


def test_spec_has_no_duplicate_keys() -> None:
    keys = [k for k, _, _ in catalog_spec.entries()]
    assert len(keys) == len(set(keys))
