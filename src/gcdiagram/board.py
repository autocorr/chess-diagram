"""Board model: cells, figures and square shades. Knows nothing about fonts or rendering."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Color = Literal["white", "black", "neutral"]
SpecialColor = Literal["white", "black", "neutral", "none"]
Variant = Literal["plain", "chameleon", "mirror"]
Shade = Literal["light", "dark"]

KINDS = "KQRBNP"
ANGLES = (0, 45, 90, 135, 180, 225, 270, 315)
FILES = "abcdefghijklmnopqrstuvwxyz"
MAX_SIZE = len(FILES)


@dataclass(frozen=True, slots=True)
class Piece:
    """A chess piece. angle is clockwise in degrees; mirror reflects after rotating."""

    kind: str
    color: Color
    angle: int = 0
    variant: Variant = "plain"

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown piece kind {self.kind!r}")
        if self.angle not in ANGLES:
            raise ValueError(f"angle must be one of {ANGLES}, not {self.angle}")


@dataclass(frozen=True, slots=True)
class Special:
    """A non-piece figure from the fonts (star, circle, ...), named as in the catalog."""

    name: str
    color: SpecialColor


Figure = Piece | Special


@dataclass(frozen=True, slots=True)
class Square:
    """A playable square, possibly holding a figure."""

    figure: Figure | None = None


@dataclass(frozen=True, slots=True)
class Hole:
    """A missing square: nothing is drawn and the border runs around it."""


@dataclass(frozen=True, slots=True)
class Wall:
    """A square that exists but is blocked."""


Cell = Square | Hole | Wall

EMPTY = Square()
HOLE = Hole()
WALL = Wall()


@dataclass
class Board:
    """A rectangular grid of cells. cells[row][col], row 0 is the top rank."""

    cells: list[list[Cell]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.cells or not self.cells[0]:
            raise ValueError("board must have at least one cell")
        width = len(self.cells[0])
        if any(len(row) != width for row in self.cells):
            raise ValueError("all ranks must have the same width")
        if width > MAX_SIZE or len(self.cells) > MAX_SIZE:
            raise ValueError(f"board is larger than {MAX_SIZE}x{MAX_SIZE}")

    @classmethod
    def empty(cls, width: int = 8, height: int = 8) -> Board:
        return cls([[EMPTY] * width for _ in range(height)])

    @property
    def width(self) -> int:
        return len(self.cells[0])

    @property
    def height(self) -> int:
        return len(self.cells)

    def shade(self, row: int, col: int) -> Shade:
        """Square color; a1 (bottom-left) is dark, as on a standard board."""
        rank_index = self.height - 1 - row
        return "dark" if (col + rank_index) % 2 == 0 else "light"

    def __getitem__(self, pos: tuple[int, int] | str) -> Cell:
        row, col = parse_square(pos, self.height) if isinstance(pos, str) else pos
        return self.cells[row][col]

    def __setitem__(self, pos: tuple[int, int] | str, cell: Cell) -> None:
        row, col = parse_square(pos, self.height) if isinstance(pos, str) else pos
        self.cells[row][col] = cell

    def square_name(self, row: int, col: int) -> str:
        return f"{FILES[col]}{self.height - row}"

    def contains(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def is_board_square(self, row: int, col: int) -> bool:
        """True for squares and walls (cells that exist), False for holes and off-board."""
        return self.contains(row, col) and not isinstance(self.cells[row][col], Hole)

    def figures(self) -> list[tuple[int, int, Figure]]:
        return [
            (r, c, cell.figure)
            for r, row in enumerate(self.cells)
            for c, cell in enumerate(row)
            if isinstance(cell, Square) and cell.figure is not None
        ]

    def piece_count(self) -> tuple[int, int, int]:
        """(white, black, neutral) piece counts, the usual '(w+b)' diagram annotation."""
        counts = {"white": 0, "black": 0, "neutral": 0}
        for _, _, fig in self.figures():
            if isinstance(fig, Piece):
                counts[fig.color] += 1
        return counts["white"], counts["black"], counts["neutral"]

    def piece_count_label(self) -> str:
        """'(w+b)', or '(w+b+n)' when there are neutral pieces."""
        w, b, n = self.piece_count()
        return f"({w}+{b}+{n})" if n else f"({w}+{b})"


_SQUARE_RE = re.compile(r"([a-z])([1-9][0-9]?)")


def parse_square(name: str, height: int) -> tuple[int, int]:
    """'e2' -> (row, col) on a board with the given number of ranks."""
    m = _SQUARE_RE.fullmatch(name.strip())
    if not m:
        raise ValueError(f"bad square name {name!r}")
    col = FILES.index(m.group(1))
    rank = int(m.group(2))
    if not 1 <= rank <= height:
        raise ValueError(f"square {name!r} is off the board")
    return height - rank, col
