"""Helvetica advance widths (Adobe AFM, 1000-unit em) for laying out caption text.

Captions are set in Helvetica: a PDF base-14 font (never embedded) and widely available
as Helvetica/Arial for SVG. Characters outside printable ASCII use an average width.
"""

from __future__ import annotations

# Widths for code points 32..126, in order.
_ASCII = (
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,  # 32-47
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,  # 48-63
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,  # @ A-O
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,  # P-Z [ \ ] ^ _
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,  # ` a-o
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,  # p-z { | } ~
)  # fmt: skip
assert len(_ASCII) == 95

DEFAULT_WIDTH = 556


def text_width(text: str, size: float) -> float:
    """Advance width of text in Helvetica at the given size (same units as size)."""
    total = 0
    for ch in text:
        code = ord(ch)
        total += _ASCII[code - 32] if 32 <= code <= 126 else DEFAULT_WIDTH
    return total * size / 1000
