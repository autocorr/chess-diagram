"""PDF output. Tests that need poppler, inkscape or ImageMagick are skipped without them."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from cases import CASES
from helpers import pdf_content

from gcdiagram.fen import parse
from gcdiagram.options import RenderOptions
from gcdiagram.render.pdf import parse_color, render_pdf
from gcdiagram.render.svg import render_svg

needs = {
    tool: shutil.which(tool) is None for tool in ("pdfinfo", "pdftoppm", "inkscape", "compare")
}


def skip_without(*tools: str) -> pytest.MarkDecorator:
    missing = [t for t in tools if needs[t]]
    return pytest.mark.skipif(bool(missing), reason=f"needs {', '.join(missing)}")


def search(pattern: str, text: str) -> str:
    m = re.search(pattern, text)
    assert m, f"{pattern!r} not found"
    return m.group(1)


def test_structure() -> None:
    pdf = render_pdf(parse("K"))
    assert pdf.startswith(b"%PDF-1.4\n")
    assert pdf.endswith(b"%%EOF\n")
    startxref = int(search(r"startxref\n(\d+)", pdf.decode("latin-1")))
    assert pdf[startxref:].startswith(b"xref")
    # Every xref offset points at the start of its object.
    table = pdf[startxref:].split(b"\n")
    count = int(table[1].split()[1])
    for i, line in enumerate(table[3 : 2 + count], start=1):
        offset = int(line.split()[0])
        assert pdf[offset:].startswith(f"{i} 0 obj".encode())


def test_deterministic() -> None:
    fen, opts = CASES["fairy"]
    assert render_pdf(parse(fen), opts) == render_pdf(parse(fen), opts)


def test_no_embedded_fonts() -> None:
    pdf = render_pdf(parse("K"), RenderOptions(caption=["#2"]))
    assert b"/BaseFont/Helvetica" in pdf
    assert b"FontFile" not in pdf


def test_colors() -> None:
    assert parse_color("#fff") == (1, 1, 1)
    assert parse_color("black") == (0, 0, 0)
    assert parse_color("#ff8000")[1] == pytest.approx(128 / 255)
    with pytest.raises(ValueError):
        parse_color("rebeccapurple")


@skip_without("pdfinfo")
@pytest.mark.parametrize("name", CASES)
def test_pdfinfo_accepts_and_sizes(name: str, tmp_path: Path) -> None:
    fen, opts = CASES[name]
    path = tmp_path / "d.pdf"
    path.write_bytes(render_pdf(parse(fen), opts))
    info = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, check=True).stdout
    assert search(r"Pages:\s+(\d+)", info) == "1"
    board = parse(fen)
    w = float(search(r"Page size:\s+([\d.]+)", info))
    assert w >= board.width * opts.square_size


@skip_without("pdftoppm", "inkscape", "compare")
@pytest.mark.parametrize("name", CASES)
def test_pdf_matches_svg_raster(name: str, tmp_path: Path) -> None:
    fen, opts = CASES[name]
    board = parse(fen)
    (tmp_path / "d.pdf").write_bytes(render_pdf(board, opts))
    (tmp_path / "d.svg").write_text(render_svg(board, opts, xlink=True))
    subprocess.run(
        ["pdftoppm", "-png", "-r", "144", "-singlefile", "d.pdf", "pdf"], cwd=tmp_path, check=True
    )
    width = subprocess.run(
        ["identify", "-format", "%w", "pdf.png"], cwd=tmp_path, capture_output=True, text=True
    ).stdout
    subprocess.run(
        ["inkscape", "d.svg", "-o", "svg.png", "-w", width, "-b", "white"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    # A page height that isn't a whole number of pixels rounds up in pdftoppm and to the
    # nearest pixel in Inkscape, so crop both to the size they share.
    heights = [
        int(
            subprocess.run(
                ["identify", "-format", "%h", png], cwd=tmp_path, capture_output=True, text=True
            ).stdout
        )
        for png in ("pdf.png", "svg.png")
    ]
    # Downsample both so anti-aliasing of the fine hatching averages out.
    for png in ("pdf.png", "svg.png"):
        subprocess.run(
            [
                *("convert", png, "-crop", f"{width}x{min(heights)}+0+0", "+repage"),
                *("-alpha", "remove", "-filter", "Box", "-resize", "25%", png),
            ],
            cwd=tmp_path,
            check=True,
        )
    result = subprocess.run(
        ["compare", "-metric", "RMSE", "pdf.png", "svg.png", "null:"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    rmse = float(search(r"\(([\d.e-]+)\)", result.stderr))
    # Captions differ slightly (Helvetica vs. the SVG renderer's sans-serif), and
    # anti-aliasing differs between renderers; geometry errors give far larger values.
    assert rmse < 0.08, rmse


def test_page_transform_keeps_precision() -> None:
    # Regression: 12pt squares need scale 0.006, which two-decimal rounding turned into 0.01.
    pdf = render_pdf(parse("8/8/8/8/8/8/8/8"), RenderOptions(square_size=12, border="none"))
    assert b"/MediaBox[0 0 96 96]" in pdf
    assert pdf_content(pdf).startswith("0.006 0 0 -0.006 0 96 cm")
