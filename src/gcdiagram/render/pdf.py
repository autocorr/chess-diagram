"""Minimal standalone PDF 1.4 writer: vector outlines, no embedded fonts.

Each distinct glyph becomes a Form XObject drawn with Do. The page content applies one
transform that maps layout font units (y down) to PDF points (y up). Captions use the
base-14 Helvetica font, which PDF viewers supply, so nothing is embedded. Output is
deterministic (no timestamps or IDs), so identical input gives identical bytes.
"""

from __future__ import annotations

import re
import zlib

from ..board import Board
from ..catalog import Catalog
from ..geometry import Layout, U, layout
from ..options import RenderOptions
from ..svgpath import fmt, pdf_path, to_pdf
from ..textmetrics import text_width
from . import prepare

_NAMED = {"white": "#fff", "black": "#000"}
# Base-14 fonts for caption runs, by (bold, italic).
_FONTS = {
    (False, False): "Helvetica",
    (True, False): "Helvetica-Bold",
    (False, True): "Helvetica-Oblique",
    (True, True): "Helvetica-BoldOblique",
}


def parse_color(color: str) -> tuple[float, float, float]:
    c = _NAMED.get(color.lower(), color)
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", c)
    if not m:
        raise ValueError(f"PDF output supports #rgb, #rrggbb, white and black, not {color!r}")
    h = m.group(1)
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return r, g, b


def _rgb(color: str, op: str) -> str:
    return " ".join(fmt(v) for v in parse_color(color)) + f" {op}"


def _pdf_string(text: str) -> str:
    raw = text.encode("cp1252", errors="replace").decode("latin-1")
    return "(" + raw.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


class _Writer:
    def __init__(self) -> None:
        self.objects: list[bytes] = []

    def reserve(self) -> int:
        self.objects.append(b"")
        return len(self.objects)

    def set(self, num: int, body: bytes) -> None:
        self.objects[num - 1] = body

    def add(self, body: bytes) -> int:
        num = self.reserve()
        self.set(num, body)
        return num

    def stream(self, data: str, extra: str = "") -> bytes:
        packed = zlib.compress(data.encode("latin-1"), 9)
        head = f"<<{extra}/Length {len(packed)}/Filter/FlateDecode>>stream\n".encode()
        return head + packed + b"\nendstream"

    def output(self, root: int) -> bytes:
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(self.objects, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(self.objects) + 1}\n0000000000 65535 f \n".encode()
        out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
        out += f"trailer\n<</Size {len(self.objects) + 1}/Root {root} 0 R>>\n".encode()
        out += f"startxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)


def render_pdf(
    board: Board | str, options: RenderOptions | None = None, *, catalog: Catalog | None = None
) -> bytes:
    """Render a board as a one-page PDF cropped to the diagram."""
    board, opts, cat = prepare(board, options, catalog)
    return _document(layout(board, opts, cat), opts, cat)


def _document(lay: Layout, opts: RenderOptions, cat: Catalog) -> bytes:
    w = _Writer()
    catalog_obj = w.reserve()
    pages_obj = w.reserve()
    page_obj = w.reserve()

    s = opts.square_size / U
    page_w, page_h = lay.width * s, lay.height * s
    # Full precision here: fmt() keeps two decimals, too few for a scale like 0.006.
    ops = [f"{s:.8g} 0 0 {-s:.8g} 0 {page_h:.8g} cm"]

    if lay.background and opts.background:
        x, y, bw, bh = lay.background
        ops.append(f"{_rgb(opts.background, 'rg')} {fmt(x)} {fmt(y)} {fmt(bw)} {fmt(bh)} re f")
    ops.append("0 g")

    forms: dict[str, str] = {}
    xobjects: list[str] = []
    for use in lay.glyphs:
        g = cat[use.key]
        if g.outline not in forms:
            name = f"G{len(forms)}"
            forms[g.outline] = name
            x0, y0, x1, y1 = g.bbox or (0, 0, U, U)
            num = w.add(
                w.stream(
                    pdf_path(cat.outlines[g.outline]) + "\nf",
                    f"/Type/XObject/Subtype/Form/BBox[{x0 - 1} {y0 - 1} {x1 + 1} {y1 + 1}]",
                )
            )
            xobjects.append(f"/{name} {num} 0 R")
        ops.append(f"q 1 0 0 1 {fmt(use.x)} {fmt(use.y)} cm/{forms[g.outline]} Do Q")

    if lay.rects:
        ops += [f"{fmt(x)} {fmt(y)} {fmt(rw)} {fmt(rh)} re" for x, y, rw, rh in lay.rects]
        ops.append("f")

    resources = []
    if lay.arrows:
        ops.append("q")
        if opts.arrow_opacity < 1:
            gs = w.add(f"<</Type/ExtGState/ca {fmt(opts.arrow_opacity)}>>".encode())
            resources.append(f"/ExtGState<</A {gs} 0 R>>")
            ops.append("/A gs")
        ops.append(_rgb(opts.arrow_color, "rg"))
        for pts in lay.arrows:
            (x0, y0), *rest = pts
            ops.append(
                f"{fmt(x0)} {fmt(y0)} m " + " ".join(f"{fmt(x)} {fmt(y)} l" for x, y in rest)
            )
            ops.append("h")
        ops.append("f Q")

    for mark in lay.marks:
        path = to_pdf(mark.path).replace("\n", " ")
        if mark.halo:
            ops.append(f"q 1 G {fmt(mark.halo)} w 1 j {path} S Q")
        ops.append(f"q {_rgb(mark.fill, 'rg')} {path} f Q")

    if lay.texts:
        # One font object per style used, F1 being plain Helvetica.
        styles = sorted({(r.bold, r.italic) for t in lay.texts for r in t.runs})
        names = {style: f"F{i}" for i, style in enumerate(styles, start=1)}
        fonts = "".join(
            f"/{names[style]} "
            + str(
                w.add(
                    f"<</Type/Font/Subtype/Type1/BaseFont/{_FONTS[style]}"
                    "/Encoding/WinAnsiEncoding>>".encode()
                )
            )
            + " 0 R"
            for style in styles
        )
        resources.append(f"/Font<<{fonts}>>")
        for t in lay.texts:
            width = sum(text_width(r.text, t.size, r.bold) for r in t.runs)
            x = t.x - {"start": 0, "middle": width / 2, "end": width}[t.anchor]
            shows = "".join(
                f"/{names[(r.bold, r.italic)]} {fmt(t.size)} Tf"
                + (f" 1 0 0 -1 {fmt(x)} {fmt(t.y)} Tm " if i == 0 else "")
                + f"{_pdf_string(r.text)}Tj"
                for i, r in enumerate(t.runs)
            )
            ops.append(f"BT{shows} ET")

    if xobjects:
        resources.append("/XObject<<" + "".join(xobjects) + ">>")

    content = w.add(w.stream("\n".join(ops)))
    w.set(
        page_obj,
        (
            f"<</Type/Page/Parent {pages_obj} 0 R/MediaBox[0 0 {page_w:.6g} {page_h:.6g}]"
            f"/Resources<<{''.join(resources)}>>/Contents {content} 0 R>>"
        ).encode(),
    )
    w.set(pages_obj, f"<</Type/Pages/Kids[{page_obj} 0 R]/Count 1>>".encode())
    w.set(catalog_obj, f"<</Type/Catalog/Pages {pages_obj} 0 R>>".encode())
    return w.output(catalog_obj)
