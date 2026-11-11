"""Annotations drawn over the board: arrows, circles, crosses, squares, triangles and dots.

Each one has a color from a small fixed set and a white outline, so it stays visible
on dark squares and black pieces. Black is the default. Vermilion (shown as
"Orange" in the editor), blue and bluish green are from the Okabe-Ito palette, whose
colors stay distinguishable for color-blind readers.

The text form, used by the CLI, the editor and its URL, is KIND:SQUARE[:COLOR] or,
for arrows, arrow:FROM-TO[:COLOR]. Examples: "circle:e4", "arrow:e2-e4:vermilion".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast, get_args

Kind = Literal["arrow", "circle", "cross", "square", "triangle", "dot"]
AnnotationColor = Literal["black", "gray", "vermilion", "blue", "green"]
KINDS: tuple[str, ...] = get_args(Kind)
COLORS: tuple[str, ...] = get_args(AnnotationColor)

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


@dataclass(frozen=True)
class Annotation:
    kind: Kind
    squares: tuple[str, ...]  # two for an arrow (from, to), one for the other kinds
    color: AnnotationColor = "black"

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"annotation kind must be one of {KINDS}, not {self.kind!r}")
        if self.color not in COLORS:
            raise ValueError(f"annotation color must be one of {COLORS}, not {self.color!r}")
        need = 2 if self.kind == "arrow" else 1
        if len(self.squares) != need:
            article = "an" if self.kind == "arrow" else "a"
            raise ValueError(f"{article} {self.kind} needs {need} square(s)")

    def __str__(self) -> str:
        color = "" if self.color == "black" else f":{self.color}"
        return f"{self.kind}:{'-'.join(self.squares)}{color}"


def parse_annotation(spec: str | Annotation) -> Annotation:
    """An Annotation from its text form, e.g. 'circle:e4' or 'arrow:e2-e4:blue'."""
    if isinstance(spec, Annotation):
        return spec
    m = _SPEC.fullmatch(spec)
    if not m:
        raise ValueError(
            f"bad annotation {spec!r}; expected e.g. 'circle:e4' or 'arrow:e2-e4:blue'"
        )
    kind, a, b, color = (g.lower() if g else g for g in m.groups())
    squares = (a, b) if b else (a,)
    try:
        # The casts are checked in __post_init__.
        return Annotation(cast(Kind, kind), squares, cast(AnnotationColor, color or "black"))
    except ValueError as e:
        raise ValueError(f"bad annotation {spec!r}: {e}") from None
