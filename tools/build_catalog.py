"""Build the glyph catalog from the GC2004 TTFs.

    uv run python tools/build_catalog.py

Writes:
  src/gcdiagram/data/catalog.json   codes + outlines (Python, web editor)
  latex/gcdiagram-catalog.lua       codes only (LuaLaTeX package)

Outlines are SVG path data in *cell coordinates*: the cell's top-left corner is (0, 0),
y points down, and a board square spans 0..2000 on both axes. (In font units the square
spans y = -500..1500 with y up, so y_cell = 1500 - y_font.) Border glyphs extend
outside 0..2000; renderers place them in the cell next to the board.

Tiny "anchor" specks that GC2004Y puts in cell corners (contours of at most
SPECK x SPECK units, presumably to stabilize bounding boxes in word processors)
are removed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).parent))
from catalog_spec import FIXUPS, FONTS, IGNORED, entries

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JSON_OUT = ROOT / "src" / "gcdiagram" / "data" / "catalog.json"
LUA_OUT = ROOT / "latex" / "gcdiagram-catalog.lua"

CELL = 2000
BASELINE = 1500  # y_cell = BASELINE - y_font
SPECK = 20
VERSION = 1


def _contours(recording: list[tuple[str, tuple]]) -> list[list[tuple[str, tuple]]]:
    contours: list[list[tuple[str, tuple]]] = []
    current: list[tuple[str, tuple]] = []
    for op, args in recording:
        current.append((op, args))
        if op in ("closePath", "endPath"):
            contours.append(current)
            current = []
    if current:
        contours.append(current)
    return contours


def _points(contour: list[tuple[str, tuple]]) -> list[tuple[float, float]]:
    return [pt for _, args in contour for pt in args if pt is not None]


def _is_speck(contour: list[tuple[str, tuple]]) -> bool:
    pts = _points(contour)
    if not pts:
        return True
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return max(xs) - min(xs) <= SPECK and max(ys) - min(ys) <= SPECK


def _cmap(font: TTFont) -> dict[int, str]:
    cmap = font.getBestCmap()
    assert cmap is not None, "font has no Unicode cmap"
    return cmap


def glyph_outline(font: TTFont, code: int, dx: int = 0) -> tuple[str, list[int] | None, int]:
    """Return (svg path in cell coords, bbox [x0, y0, x1, y1] in cell coords, specks removed).

    dx shifts the outline horizontally (font fix-ups, see catalog_spec.FIXUPS).
    """
    glyph_set = font.getGlyphSet()
    name = _cmap(font)[code]
    rec = DecomposingRecordingPen(glyph_set)
    glyph_set[name].draw(rec)

    kept = [c for c in _contours(rec.value) if not _is_speck(c)]
    removed = len(_contours(rec.value)) - len(kept)

    svg = SVGPathPen(glyph_set, ntos=lambda v: f"{v:g}")
    pen = TransformPen(svg, (1, 0, 0, -1, dx, BASELINE))
    for contour in kept:
        for op, args in contour:
            getattr(pen, op)(*args)

    pts = [p for c in kept for p in _points(c)]
    bbox = None
    if pts:
        xs = [p[0] + dx for p in pts]
        ys = [BASELINE - p[1] for p in pts]
        bbox = [round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys))]
    return svg.getCommands(), bbox, removed


def build() -> dict:
    fonts = {key: TTFont(DATA / filename) for key, filename in FONTS.items()}
    outline_ids: dict[str, str] = {}
    outlines: dict[str, str] = {}
    glyphs: dict[str, dict] = {}
    used: dict[str, set[int]] = {key: set() for key in fonts}
    specks = 0

    for key, font_key, code in entries():
        font = fonts[font_key]
        if code not in _cmap(font):
            raise SystemExit(f"{key}: code 0x{code:02X} not in {FONTS[font_key]}")
        used[font_key].add(code)
        dx = FIXUPS.get((font_key, code), 0)
        path, bbox, removed = glyph_outline(font, code, dx)
        specks += removed
        if path not in outline_ids:
            outline_ids[path] = f"o{len(outline_ids)}"
            outlines[outline_ids[path]] = path
        glyphs[key] = {"font": font_key, "code": code, "outline": outline_ids[path], "bbox": bbox}
        if dx:
            glyphs[key]["dx"] = dx

    for font_key, font in fonts.items():
        unused = sorted(
            c
            for c in _cmap(font)
            if 0x21 <= c <= 0xFF
            and c not in used[font_key]
            and c not in IGNORED[font_key]
            and glyph_outline(font, c)[0]
        )
        if unused:
            print(
                f"note: {FONTS[font_key]} codes not in catalog:",
                " ".join(f"{c:02X}" for c in unused),
            )
    print(f"{len(glyphs)} glyphs, {len(outlines)} distinct outlines, {specks} specks removed")

    return {
        "version": VERSION,
        "unitsPerEm": 2000,
        "cell": CELL,
        "baseline": BASELINE,
        "fonts": FONTS,
        "outlines": outlines,
        "glyphs": glyphs,
    }


def write_json(catalog: dict) -> None:
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    head = {k: v for k, v in catalog.items() if k not in ("outlines", "glyphs")}
    lines = ["{"]
    lines += [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in head.items()]
    for section in ("outlines", "glyphs"):
        items = list(catalog[section].items())
        lines.append(f'  "{section}": {{')
        lines += [
            f"    {json.dumps(k)}: {json.dumps(v, separators=(',', ':'))}"
            + ("," if i < len(items) - 1 else "")
            for i, (k, v) in enumerate(items)
        ]
        lines.append("  }," if section == "outlines" else "  }")
    lines.append("}")
    JSON_OUT.write_text("\n".join(lines) + "\n")


def write_lua(catalog: dict) -> None:
    LUA_OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "-- Generated by tools/build_catalog.py; do not edit.",
        "return {",
        f"  version = {catalog['version']},",
        "  fonts = {" + ", ".join(f'{k} = "{v}"' for k, v in catalog["fonts"].items()) + "},",
        "  -- [key] = { font, code [, dx] }: kern dx/2000 em before and -dx after the glyph",
        "  glyphs = {",
    ]
    for key, g in catalog["glyphs"].items():
        dx = f", {g['dx']}" if "dx" in g else ""
        lines.append(f'    ["{key}"] = {{ "{g["font"]}", 0x{g["code"]:02X}{dx} }},')
    lines += ["  },", "}"]
    LUA_OUT.write_text("\n".join(lines) + "\n")


def main() -> None:
    catalog = build()
    write_json(catalog)
    write_lua(catalog)
    print(f"wrote {JSON_OUT.relative_to(ROOT)} and {LUA_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
