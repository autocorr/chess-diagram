"""Command-line interface: gcdiagram FEN -o diagram.pdf"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import get_args

from .catalog import load_catalog
from .fen import FenError, parse, serialize
from .options import BorderStyle, RenderOptions, WallStyle
from .render.pdf import render_pdf
from .render.svg import render_svg
from .render.tex import render_tex

FORMATS = ("svg", "pdf", "tex")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcdiagram",
        description="Render a chess diagram from extended FEN using the GC2004 fonts.",
        epilog=(
            "Extended FEN: {Q90} rotated piece (0-315 in steps of 45), {=Q} neutral, "
            "{~Q} chameleon, {!N90} mirrored knight, {@Star}/{@star} white/black special, "
            "'.' hole, '*' wall. Quote the FEN in the shell."
        ),
    )
    p.add_argument("fen", nargs="?", help="extended FEN (only the board field is used)")
    p.add_argument("-o", "--output", type=Path, help="output file (default: SVG to stdout)")
    p.add_argument("-f", "--format", choices=FORMATS, help="output format (default: from -o)")
    p.add_argument("-b", "--border", choices=get_args(BorderStyle), default="single")
    p.add_argument("-c", "--caption", action="append", default=[], help="caption line (repeat)")
    p.add_argument("-n", "--count", action="store_true", help="add the (white+black) count")
    p.add_argument("-a", "--arrow", action="append", default=[], help="arrow such as e2-e4")
    p.add_argument("--wall", choices=get_args(WallStyle), default="solid")
    p.add_argument("-s", "--square-size", type=float, default=20.0, help="points per square")
    p.add_argument("--padding", type=float, default=0.0, help="margin in points")
    p.add_argument("--transparent", action="store_true", help="no background fill")
    p.add_argument("--xlink", action="store_true", help="SVG: use xlink:href (SVG 1.1 tools)")
    p.add_argument("--id-prefix", default="g", help="SVG: prefix for element ids")
    p.add_argument("--canonical", action="store_true", help="print the canonical FEN and exit")
    p.add_argument("--list-specials", action="store_true", help="list special figure names")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_specials:
        for name, colors in sorted(load_catalog().specials.items()):
            print(f"{name:12} {', '.join(sorted(colors))}")
        return 0
    if args.fen is None:
        parser.error("a FEN is required")

    try:
        board = parse(args.fen)
    except FenError as e:
        print(f"gcdiagram: {e}", file=sys.stderr)
        return 2
    if args.canonical:
        print(serialize(board))
        return 0

    fmt = args.format or (args.output.suffix.lower().lstrip(".") if args.output else "svg")
    if fmt not in FORMATS:
        parser.error(f"cannot infer format from {args.output}; use --format")

    try:
        opts = RenderOptions(
            square_size=args.square_size,
            border=args.border,
            caption=args.caption,
            piece_count=args.count,
            arrows=args.arrow,
            wall=args.wall,
            padding=args.padding,
            background=None if args.transparent else "#fff",
        )
        if fmt == "pdf":
            data = render_pdf(board, opts)
        elif fmt == "tex":
            data = render_tex(board, opts).encode()
        else:
            data = render_svg(board, opts, id_prefix=args.id_prefix, xlink=args.xlink).encode()
    except ValueError as e:
        print(f"gcdiagram: {e}", file=sys.stderr)
        return 2

    if args.output:
        args.output.write_bytes(data)
    else:
        sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
