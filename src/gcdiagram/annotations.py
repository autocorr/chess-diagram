"""Annotations drawn over the board: arrows, circles, crosses, squares, triangles, dots
and labels.

Each one has a color from a small fixed set and a white outline, so it stays visible
on dark squares and black pieces. Black is the default. Vermilion (shown as
"Orange" in the editor), blue and bluish green are from the Okabe-Ito palette, whose
colors stay distinguishable for color-blind readers.

A label is one character in a corner of a square: tl, tr, bl or br (top left, top
right, bottom left, bottom right). Each corner holds one label, so a square can have
four. The character is printable ASCII, which every output can set: the PDF uses the
standard Helvetica-Bold font, whose widths textmetrics.py knows.

The text form, used by the CLI, the editor and its URL, is KIND:SQUARE[:COLOR],
arrow:FROM-TO[:COLOR] for arrows, and label:SQUARE:CORNER:SYMBOL[:COLOR] for labels.
Examples: "circle:e4", "arrow:e2-e4:vermilion", "label:e4:tr:A:blue". A label's
symbol is exactly one character, so it may be ":" itself ("label:e4:tr:::blue").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast, get_args

Kind = Literal["arrow", "circle", "cross", "square", "triangle", "dot", "label"]
AnnotationColor = Literal["black", "gray", "vermilion", "blue", "green"]
Corner = Literal["tl", "tr", "bl", "br"]
KINDS: tuple[str, ...] = get_args(Kind)
COLORS: tuple[str, ...] = get_args(AnnotationColor)
CORNERS: tuple[str, ...] = get_args(Corner)
# The characters a label can show: printable ASCII, without the space.
LABEL_CHARS = "".join(chr(c) for c in range(0x21, 0x7F))

FILL: dict[str, str] = {
    "black": "#000",
    "gray": "#808080",
    "vermilion": "#D55E00",
    "blue": "#0072B2",
    "green": "#009E73",  # Okabe-Ito bluish green
}

_SPEC = re.compile(
    r"\s*([a-z]+)\s*:\s*([a-z][0-9]+)(?:\s*-?\s*([a-z][0-9]+))?\s*(?::\s*([a-z]+)\s*)?",
    re.IGNORECASE,
)
# The symbol is one non-space character and keeps its case.
_LABEL_SPEC = re.compile(
    r"\s*label\s*:\s*([a-z][0-9]+)\s*:\s*([a-z]+)\s*:\s*(\S)\s*(?::\s*([a-z]+)\s*)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Annotation:
    kind: Kind
    squares: tuple[str, ...]  # two for an arrow (from, to), one for the other kinds
    color: AnnotationColor = "black"
    corner: Corner | None = None  # labels only
    symbol: str = ""  # labels only: one character of LABEL_CHARS

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"annotation kind must be one of {KINDS}, not {self.kind!r}")
        if self.color not in COLORS:
            raise ValueError(f"annotation color must be one of {COLORS}, not {self.color!r}")
        need = 2 if self.kind == "arrow" else 1
        if len(self.squares) != need:
            article = "an" if self.kind == "arrow" else "a"
            raise ValueError(f"{article} {self.kind} needs {need} square(s)")
        if self.kind == "label":
            if self.corner not in CORNERS:
                raise ValueError(f"a label's corner must be one of {CORNERS}, not {self.corner!r}")
            if len(self.symbol) != 1 or self.symbol not in LABEL_CHARS:
                raise ValueError(
                    f"a label's symbol must be one printable ASCII character, not {self.symbol!r}"
                )
        elif self.corner is not None or self.symbol:
            raise ValueError(f"only labels have a corner and a symbol, not a {self.kind}")

    def __str__(self) -> str:
        color = "" if self.color == "black" else f":{self.color}"
        if self.kind == "label":
            return f"label:{self.squares[0]}:{self.corner}:{self.symbol}{color}"
        return f"{self.kind}:{'-'.join(self.squares)}{color}"


def parse_annotation(spec: str | Annotation) -> Annotation:
    """An Annotation from its text form, e.g. 'circle:e4', 'arrow:e2-e4:blue' or
    'label:e4:tr:A'."""
    if isinstance(spec, Annotation):
        return spec
    try:
        # The casts are checked in __post_init__.
        if m := _LABEL_SPEC.fullmatch(spec):
            square, corner, symbol, color = m.groups()
            return Annotation(
                "label",
                (square.lower(),),
                cast(AnnotationColor, (color or "black").lower()),
                cast(Corner, corner.lower()),
                symbol,
            )
        if m := _SPEC.fullmatch(spec):
            kind, a, b, color = (g.lower() if g else g for g in m.groups())
            squares = (a, b) if b else (a,)
            return Annotation(cast(Kind, kind), squares, cast(AnnotationColor, color or "black"))
    except ValueError as e:
        raise ValueError(f"bad annotation {spec!r}: {e}") from None
    raise ValueError(
        f"bad annotation {spec!r}; expected e.g. 'circle:e4', 'arrow:e2-e4:blue' or 'label:e4:tr:A'"
    )
