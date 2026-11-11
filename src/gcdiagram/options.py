"""Rendering options shared by every output format."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, get_args

from .annotations import Annotation, parse_annotation

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
    caption: lines of text under the board (stipulation, author, ...), left-aligned and
             wrapped at spaces to the diagram's width. <b>bold</b> and <i>italic</i>
             markup is allowed (see markup.py).
    caption_above: lines of text above the board, laid out like the caption.
    piece_count: add "(w+b)" or "(w+b+n)" right-aligned under the board, on the
             caption's first line; the caption wraps before it.
    arrows:  square pairs such as "e2-e4" or ("e2", "e4"), drawn in arrow_color at
             arrow_opacity.
    annotations: arrows, circles, crosses, squares, triangles and dots, each in its own
             color, e.g. "circle:e4" or "arrow:e2-e4:blue" (see annotations.py).
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
    caption_above: Sequence[str] = ()
    annotations: Sequence[str | Annotation] = ()
    wall: WallStyle = "solid"
    padding: float = 0.0
    background: str | None = "#fff"
    caption_size: float = 0.45  # caption font size relative to the square size
    arrow_color: str = "#000"
    arrow_opacity: float = 0.6

    def __post_init__(self) -> None:
        if self.border not in get_args(BorderStyle):
            raise ValueError(f"border must be one of {get_args(BorderStyle)}, not {self.border!r}")
        if self.wall not in get_args(WallStyle):
            raise ValueError(f"wall must be one of {get_args(WallStyle)}, not {self.wall!r}")
        for name in ("caption", "caption_above", "arrows", "annotations"):
            if isinstance(getattr(self, name), str):
                raise TypeError(f"{name} is a sequence of strings, not one string")
        for spec in self.annotations:
            parse_annotation(spec)
        if not self.square_size > 0:
            raise ValueError(f"square_size must be positive, not {self.square_size}")
        if not self.caption_size > 0:
            raise ValueError(f"caption_size must be positive, not {self.caption_size}")
        if not self.padding >= 0:
            raise ValueError(f"padding cannot be negative, not {self.padding}")
        if not 0 <= self.arrow_opacity <= 1:
            raise ValueError(f"arrow_opacity must be between 0 and 1, not {self.arrow_opacity}")
