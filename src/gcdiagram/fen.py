"""Extended FEN parser and serializer (grammar in ARCHITECTURE.md section 5).

    board  := rank ("/" rank)*                  first rank is the top row
    item   := empty | piece | token | "." | "*"  hole, wall
    empty  := [1-9][0-9]*
    piece  := [KQRBNPkqrbnp]
    token  := "{" ("=" | "~" | "!")? letter angle? "}"
            | "{" "="? "@" name "}"

Anything after the first whitespace (side to move, castling, ...) is ignored.
"""

from __future__ import annotations

from .board import (
    ANGLES,
    EMPTY,
    HOLE,
    MAX_SIZE,
    WALL,
    Board,
    Cell,
    Color,
    Figure,
    Piece,
    Special,
    SpecialColor,
    Square,
    Variant,
    Wall,
)
from .catalog import Catalog, load_catalog

PIECE_LETTERS = "KQRBNPkqrbnp"
MODIFIERS: dict[str, Variant | None] = {"~": "chameleon", "!": "mirror", "=": None}


class FenError(ValueError):
    """A parse error. code is stable across implementations (see tests/vectors.json)."""

    def __init__(self, code: str, message: str, pos: int | None = None) -> None:
        self.code = code
        self.pos = pos
        super().__init__(f"{message} (at character {pos + 1})" if pos is not None else message)


def parse(fen: str, catalog: Catalog | None = None) -> Board:
    catalog = catalog or load_catalog()
    text = fen.strip()
    board_text = text.split(maxsplit=1)[0] if text else ""
    if not board_text:
        raise FenError("empty", "empty FEN")

    offset = len(fen) - len(fen.lstrip())
    rows: list[list[Cell]] = []
    row: list[Cell] = []
    i = 0
    n = len(board_text)
    while i <= n:
        ch = board_text[i] if i < n else "/"
        if ch == "/":
            if not row:
                raise FenError("empty-rank", f"rank {len(rows) + 1} is empty", offset + i)
            rows.append(row)
            row = []
            i += 1
        elif ch.isdigit():
            j = i
            while j < n and board_text[j].isdigit():
                j += 1
            count = int(board_text[i:j])
            if board_text[i] == "0":
                raise FenError("bad-count", "empty-square counts cannot start with 0", offset + i)
            if count > MAX_SIZE:
                raise FenError("too-large", f"board is wider than {MAX_SIZE} files", offset + i)
            row.extend([EMPTY] * count)
            i = j
        elif ch in PIECE_LETTERS:
            color: Color = "white" if ch.isupper() else "black"
            row.append(Square(Piece(ch.upper(), color)))
            i += 1
        elif ch == ".":
            row.append(HOLE)
            i += 1
        elif ch == "*":
            row.append(WALL)
            i += 1
        elif ch == "{":
            end = board_text.find("}", i)
            if end < 0:
                raise FenError("unterminated-token", "'{' without matching '}'", offset + i)
            figure = _parse_token(board_text[i + 1 : end], offset + i, catalog)
            row.append(Square(figure))
            i = end + 1
        else:
            raise FenError("bad-char", f"unexpected character {ch!r}", offset + i)
        if len(row) > MAX_SIZE:
            raise FenError("too-large", f"board is wider than {MAX_SIZE} files", offset + i - 1)

    width = len(rows[0])
    for r, cells in enumerate(rows):
        if len(cells) != width:
            raise FenError(
                "uneven-ranks",
                f"rank {r + 1} from the top has {len(cells)} squares, the first has {width}",
            )
    if len(rows) > MAX_SIZE:
        raise FenError("too-large", f"board has more than {MAX_SIZE} ranks")
    return Board(rows)


def _parse_token(body: str, pos: int, catalog: Catalog) -> Figure:
    """Parse the text between '{' and '}'."""
    mod = body[:1] if body[:1] in MODIFIERS else ""
    rest = body[len(mod) :]

    if rest.startswith("@"):
        if mod not in ("", "="):
            raise FenError("bad-token", f"modifier {mod!r} cannot apply to a special", pos)
        return _special(rest[1:], neutral=mod == "=", pos=pos, catalog=catalog)

    if not rest or rest[0] not in PIECE_LETTERS:
        raise FenError("bad-token", f"bad token {{{body}}}", pos)
    letter, angle_text = rest[0], rest[1:]
    angle = 0
    if angle_text:
        if not angle_text.isdigit() or int(angle_text) not in ANGLES:
            raise FenError("bad-angle", f"angle must be one of {ANGLES}, not {angle_text!r}", pos)
        angle = int(angle_text)

    color: Color = "neutral" if mod == "=" else ("white" if letter.isupper() else "black")
    variant: Variant = MODIFIERS.get(mod) or "plain"
    piece = Piece(letter.upper(), color, angle, variant)
    if not catalog.supports(piece):
        raise FenError("unsupported", f"the GC fonts have no {_describe(piece)}", pos)
    return piece


def _special(name: str, *, neutral: bool, pos: int, catalog: Catalog) -> Special:
    key = name.lower()
    colors = catalog.specials.get(key)
    if not name or colors is None:
        known = ", ".join(sorted(catalog.specials))
        raise FenError("unknown-special", f"unknown special {name!r}; known: {known}", pos)
    color: SpecialColor
    if neutral:
        color = "neutral"
    elif colors <= {"none", "neutral"}:
        # Single-variant specials (box, cross, half-circle) accept either case.
        (color,) = colors
    else:
        color = "white" if name[0].isupper() else "black"
    if color not in colors:
        raise FenError("unsupported", f"special {key!r} has no {color} version", pos)
    return Special(key, color)


PIECE_NAMES = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight", "P": "pawn"}


def _describe(p: Piece) -> str:
    variant = "" if p.variant == "plain" else f"{p.variant} "
    return f"{p.color} {variant}{PIECE_NAMES[p.kind]} at {p.angle} degrees"


def serialize(board: Board, catalog: Catalog | None = None) -> str:
    """Canonical extended FEN for a board: serialize(parse(s)) is stable."""
    catalog = catalog or load_catalog()
    return "/".join(_serialize_rank(row, catalog) for row in board.cells)


def _serialize_rank(row: list[Cell], catalog: Catalog) -> str:
    out: list[str] = []
    run = 0
    for cell in row:
        if cell == EMPTY:
            run += 1
            continue
        if run:
            out.append(str(run))
            run = 0
        if isinstance(cell, Square):
            assert cell.figure is not None
            out.append(figure_token(cell.figure, catalog))
        elif isinstance(cell, Wall):
            out.append("*")
        else:
            out.append(".")
    if run:
        out.append(str(run))
    return "".join(out)


def figure_token(figure: Figure, catalog: Catalog | None = None) -> str:
    """The canonical FEN token for one figure, e.g. 'Q', '{n90}', '{=R}', '{@Star}'."""
    if isinstance(figure, Special):
        colors = (catalog or load_catalog()).specials.get(figure.name, set())
        if figure.color == "neutral" and colors != {"neutral"}:
            return f"{{=@{figure.name}}}"
        name = figure.name.capitalize() if figure.color == "white" else figure.name
        return f"{{@{name}}}"
    letter = figure.kind if figure.color != "black" else figure.kind.lower()
    if figure.color == "neutral":
        mod = "="
    else:
        mod = {"plain": "", "chameleon": "~", "mirror": "!"}[figure.variant]
    angle = str(figure.angle) if figure.angle else ""
    if not mod and not angle:
        return letter
    return f"{{{mod}{letter}{angle}}}"
