"""Render every catalog glyph with its key, for checking against data/GC2004Q.pdf.

    uv run python tools/contact_sheet.py [--filter PREFIX] [-o build/contact-sheet.svg]

Each glyph is drawn in its cell with a faint frame. Border, corner and label glyphs that
extend outside the cell are drawn as-is so their placement relative to the board is visible.
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "src" / "gcdiagram" / "data" / "catalog.json"

COLS = 8
PAD = 600  # space around each cell (font units)
LABEL = 220  # label font size (font units)
PX_PER_CELL = 64


def group_of(key: str) -> str:
    parts = key.split(":")
    if parts[0] == "piece":
        return f"piece:{parts[4]}:{parts[2]}"  # variant, color
    if parts[0] in ("special", "label"):
        return ":".join(parts[:2]) if parts[0] == "special" else ":".join(parts[:3])
    return parts[0]


def render(catalog: dict, prefix: str = "") -> str:
    glyphs = {k: g for k, g in catalog["glyphs"].items() if k.startswith(prefix)}
    groups: dict[str, list[str]] = {}
    for key in glyphs:
        groups.setdefault(group_of(key), []).append(key)

    cell = catalog["cell"]
    pitch = cell + 2 * PAD
    defs = [
        f'<path id="{oid}" d="{d}"/>'
        for oid, d in catalog["outlines"].items()
        if any(g["outline"] == oid for g in glyphs.values())
    ]
    body: list[str] = []
    y = 0
    for name, keys in groups.items():
        body.append(
            f'<text x="0" y="{y + 500}" font-size="420" font-weight="bold">{escape(name)}</text>'
        )
        y += 700
        for i, key in enumerate(keys):
            col, row = i % COLS, i // COLS
            x0 = col * pitch + PAD
            y0 = y + row * pitch + PAD
            g = glyphs[key]
            short = ":".join(f for f in key.split(":")[1:] if f not in name.split(":"))
            body.append(
                f'<rect x="{x0}" y="{y0}" width="{cell}" height="{cell}" fill="none" '
                f'stroke="#e33" stroke-width="8"/>'
                f'<use xlink:href="#{g["outline"]}" x="{x0}" y="{y0}"/>'
                f'<text x="{x0}" y="{y0 - 120}" font-size="{LABEL}">'
                f"{escape(short)} · {g['font']} {g['code']:02X}</text>"
            )
        y += ((len(keys) + COLS - 1) // COLS) * pitch + 200

    width = COLS * pitch
    scale = PX_PER_CELL / cell
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {width} {y}" '
        f'width="{width * scale:.0f}" height="{y * scale:.0f}" font-family="sans-serif">'
        f'<rect width="100%" height="100%" fill="#fff"/><defs>{"".join(defs)}</defs>'
        f"{''.join(body)}</svg>\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--filter", default="", help="only keys starting with this prefix")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "contact-sheet.svg")
    args = parser.parse_args()
    catalog = json.loads(CATALOG.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(catalog, args.filter))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
