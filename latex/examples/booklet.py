"""Build a 100-diagram booklet three ways and compare PDF size and compile time.

    uv run python latex/examples/booklet.py [--count 100] [--out build/booklet]

  include   100 standalone PDFs (gcdiagram.render_pdf) placed with \\includegraphics
  routeA    Python-written \\gcbox snippets (gcsnippet.sty), LuaLaTeX and XeLaTeX
  routeB    \\gcdiagram{fen} parsed in Lua (gcdiagram.sty), LuaLaTeX

The positions are pseudo-random but reproducible (fixed seed).
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
import time
from dataclasses import replace
from pathlib import Path

from gcdiagram import Board, Piece, RenderOptions, Special, Square, render_pdf, render_tex
from gcdiagram.board import HOLE
from gcdiagram.catalog import load_catalog
from gcdiagram.fen import serialize
from gcdiagram.render.tex import tex_escape

ROOT = Path(__file__).resolve().parents[2]
SQUARE = 16  # pt; two diagrams per row on an A4/letter text block


def positions(count: int, seed: int = 2026) -> list[tuple[str, RenderOptions]]:
    rng = random.Random(seed)
    cat = load_catalog()
    out = []
    for i in range(count):
        width = height = 8
        if i % 10 == 9:
            width, height = rng.choice([(6, 6), (10, 8), (8, 10)])
        board = Board.empty(width, height)
        if i % 7 == 6:  # irregular board: punch a few holes
            for _ in range(rng.randint(2, 6)):
                board[(rng.randrange(height), rng.randrange(width))] = HOLE
        squares = [(r, c) for r in range(height) for c in range(width)]
        rng.shuffle(squares)
        for kind, color in (("K", "white"), ("K", "black")):
            board[squares.pop()] = Square(Piece(kind, color))
        for _ in range(rng.randint(4, 18)):
            r, c = squares.pop()
            if i % 4 == 3 and rng.random() < 0.3:  # fairy problem
                fig = rng.choice(
                    [
                        Piece(
                            rng.choice("QRBN"),
                            rng.choice(["white", "black"]),
                            rng.choice([90, 180, 270, 45]),
                        ),
                        Piece(rng.choice("QRBN"), "neutral", rng.choice([0, 90, 180, 270])),
                        Piece(rng.choice("QRBNP"), rng.choice(["white", "black"]), 0, "chameleon"),
                        Special(
                            rng.choice(["star", "circle", "flower"]), rng.choice(["white", "black"])
                        ),
                    ]
                )
            else:
                fig = Piece(rng.choice("QRRBBNNPPPP"), rng.choice(["white", "black"]))
            if isinstance(fig, Piece) and fig.kind == "P" and r in (0, height - 1):
                fig = Piece("N", fig.color)
            assert cat.supports(fig), fig
            board[(r, c)] = Square(fig)
        moves = rng.choice(["#2", "#3", "h#2", "s#4", "=", "+"])
        out.append(
            (serialize(board), RenderOptions(caption=[f"{i + 1}. {moves}"], piece_count=True))
        )
    return out


DOC = r"""\documentclass{article}
\usepackage[margin=2cm]{geometry}
%(packages)s
\pagestyle{empty}
\parindent=0pt
\begin{document}
%(body)s
\end{document}
"""


def grid(items: list[str]) -> str:
    rows = []
    for k in range(0, len(items), 2):
        pair = items[k : k + 2]
        rows.append(r"\hfil " + r"\hfil\hfil ".join(pair) + r"\hfil\par\bigskip")
    return "\n".join(rows)


def caption_keys(opts: RenderOptions) -> str:
    return "caption={" + tex_escape(opts.caption[0]) + "}, count"


def build(out: Path, count: int) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    (out / "pdf").mkdir(exist_ok=True)
    (out / "snippets").mkdir(exist_ok=True)
    fonts = f"{ROOT / 'data'}/"
    docs = {}
    items_inc, items_a, items_b = [], [], []
    for i, (fen, opts) in enumerate(positions(count)):
        (out / "pdf" / f"{i:03}.pdf").write_bytes(
            render_pdf(fen, replace(opts, square_size=SQUARE))
        )
        (out / "snippets" / f"{i:03}.tex").write_text(render_tex(fen, opts))
        items_inc.append(rf"\includegraphics{{pdf/{i:03}.pdf}}")
        items_a.append(rf"\input{{snippets/{i:03}}}")
        items_b.append(rf"\gcdiagram[{caption_keys(opts)}]{{{fen}}}")

    setup = rf"\gcfontpath{{{fonts}}}" + "\n" + rf"\gcsquaresize{{{SQUARE}pt}}"
    docs["include"] = DOC % {"packages": r"\usepackage{graphicx}", "body": grid(items_inc)}
    docs["routeA"] = DOC % {
        "packages": r"\usepackage{gcsnippet}" + "\n" + setup,
        "body": grid(items_a),
    }
    docs["routeB"] = DOC % {
        "packages": r"\usepackage{gcdiagram}" + "\n" + setup,
        "body": grid(items_b),
    }
    paths = {}
    for name, source in docs.items():
        paths[name] = out / f"{name}.tex"
        paths[name].write_text(source)
    return paths


def compile_doc(engine: str, tex: Path, jobname: str) -> tuple[float, int, str]:
    env = dict(os.environ)
    env["TEXINPUTS"] = f"{ROOT / 'latex'}//:"
    env["LUAINPUTS"] = f"{ROOT / 'latex'}//:"
    cmd = [engine, "-interaction=nonstopmode", "-halt-on-error", f"-jobname={jobname}", tex.name]
    subprocess.run(cmd, cwd=tex.parent, env=env, capture_output=True, check=False)  # warm caches
    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=tex.parent, env=env, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    pdf = tex.parent / f"{jobname}.pdf"
    if result.returncode != 0:
        raise SystemExit(f"{jobname} failed; see {tex.parent / (jobname + '.log')}")
    pages = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    npages = next(line.split()[-1] for line in pages.splitlines() if line.startswith("Pages:"))
    return elapsed, pdf.stat().st_size, npages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "booklet")
    args = parser.parse_args()
    paths = build(args.out, args.count)
    inputs = sum(p.stat().st_size for p in (args.out / "pdf").iterdir())
    snippets = sum(p.stat().st_size for p in (args.out / "snippets").iterdir())
    print(
        f"{args.count} diagrams: standalone PDFs {inputs / 1024:.0f} KiB in total, "
        f"snippets {snippets / 1024:.0f} KiB in total\n"
    )
    print(f"{'variant':<22}{'engine':<10}{'pages':>6}{'PDF size':>12}{'time':>9}")
    for name, engine in (
        ("include", "lualatex"),
        ("routeA", "lualatex"),
        ("routeA", "xelatex"),
        ("routeB", "lualatex"),
    ):
        jobname = f"{name}-{engine}"
        elapsed, size, pages = compile_doc(engine, paths[name], jobname)
        print(f"{name:<22}{engine:<10}{pages:>6}{size / 1024:>10.0f} KiB{elapsed:>8.2f}s")


if __name__ == "__main__":
    main()
