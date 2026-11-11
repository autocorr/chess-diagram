"""Rendering options shared by every output format."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

BorderStyle = Literal["single", "double", "outline", "none"]
WallStyle = Literal["solid", "box"]


@dataclass(frozen=True)
class RenderOptions:
    """
    border:  "single"  100-unit frame around the board's bounding rectangle (GC2004D)
             "double"  thin + thick frame (GC2004Y proportions)
             "outline" single line that follows the board shape, no rectangular frame
             "none"    no border and no lines around holes
             With "single" and "double", edges of squares next to holes get single lines.
    caption: lines of text centred under the board (stipulation, author, ...).
    piece_count: add "(w+b)" or "(w+b+n)" right-aligned under the board.
    arrows:  square pairs such as "e2-e4" or ("e2", "e4").
    wall:    "solid" fills blocked squares black; "box" uses the framed GC2004D box.
    square_size: size of one square in points (PDF) or CSS pt (SVG).
    padding: whitespace around the diagram, in points.
    background: fill behind the diagram, or None for transparent.
    """

    square_size: float = 20.0
    border: BorderStyle = "single"
    caption: Sequence[str] = ()
    piece_count: bool = False
    arrows: Sequence[str | tuple[str, str]] = ()
    wall: WallStyle = "solid"
    padding: float = 0.0
    background: str | None = "#fff"
    caption_size: float = 0.45  # caption font size relative to the square size
    arrow_color: str = "#000"
    arrow_opacity: float = 0.6
