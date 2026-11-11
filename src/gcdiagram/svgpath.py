"""Parse catalog outline paths and re-encode them for SVG (compact) and PDF (cubic).

Catalog paths use absolute M, L, H, V, Q and Z commands, possibly with implicit repeats.
"""

from __future__ import annotations

import re
from functools import lru_cache

Segment = tuple  # ("M", x, y) | ("L", x, y) | ("Q", x1, y1, x, y) | ("Z",)

_TOKEN = re.compile(r"[MLHVQZmlhvqz]|-?(?:\d+\.?\d*|\.\d+)")
_ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "Z": 0}


def parse(d: str) -> list[Segment]:
    """Absolute segments; H and V become L. Only absolute commands are accepted."""
    tokens = _TOKEN.findall(d)
    out: list[Segment] = []
    i = 0
    cmd = ""
    x = y = 0.0
    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            if tok.islower():
                raise ValueError(f"relative path command {tok!r} not supported")
            cmd = tok
            i += 1
            if cmd == "Z":
                out.append(("Z",))
                continue
        elif not cmd or cmd == "Z":
            raise ValueError(f"number without command in path: {d[:40]!r}")
        n = _ARITY[cmd]
        args = [float(t) for t in tokens[i : i + n]]
        if len(args) != n:
            raise ValueError(f"truncated {cmd} in path")
        i += n
        if cmd == "M":
            x, y = args
            out.append(("M", x, y))
            cmd = "L"  # implicit repeats after a moveto are linetos
        elif cmd == "L":
            x, y = args
            out.append(("L", x, y))
        elif cmd == "H":
            x = args[0]
            out.append(("L", x, y))
        elif cmd == "V":
            y = args[0]
            out.append(("L", x, y))
        elif cmd == "Q":
            out.append(("Q", *args))
            x, y = args[2], args[3]
    return out


def fmt(v: float, places: int = 2) -> str:
    """Shortest decimal form with at most `places` (>= 1) decimals: 12, -3.5, .5, -.25."""
    s = f"{v:.{places}f}".rstrip("0").rstrip(".")
    if s in ("-0", ""):
        return "0"
    if s.startswith("0."):
        return s[1:]
    if s.startswith("-0."):
        return "-" + s[2:]
    return s


def _join(tokens: list[str]) -> str:
    """Join command letters and numbers with the minimum separators SVG allows."""
    out: list[str] = []
    prev = ""
    for tok in tokens:
        if (
            prev
            and not prev.isalpha()
            and not tok.isalpha()
            and not tok.startswith("-")
            and not (tok.startswith(".") and "." in prev)
        ):
            out.append(" ")
        out.append(tok)
        prev = tok
    return "".join(out)


def to_svg(segments: list[Segment]) -> str:
    """Compact relative SVG path data."""
    tokens: list[str] = []
    last = ""
    x = y = sx = sy = 0.0

    def emit(cmd: str, nums: list[float]) -> None:
        nonlocal last
        if cmd != last or cmd in ("m", "z"):
            tokens.append(cmd)
        tokens.extend(fmt(v) for v in nums)
        last = cmd

    for seg in segments:
        op = seg[0]
        if op == "M":
            emit("m", [seg[1] - x, seg[2] - y])
            x, y = seg[1], seg[2]
            sx, sy = x, y
        elif op == "L":
            dx, dy = seg[1] - x, seg[2] - y
            if dy == 0:
                emit("h", [dx])
            elif dx == 0:
                emit("v", [dy])
            else:
                emit("l", [dx, dy])
            x, y = seg[1], seg[2]
        elif op == "Q":
            emit("q", [seg[1] - x, seg[2] - y, seg[3] - x, seg[4] - y])
            x, y = seg[3], seg[4]
        else:
            emit("z", [])
            x, y = sx, sy
    return _join(tokens)


def to_pdf(segments: list[Segment]) -> str:
    """PDF path construction operators (quadratics raised to cubics), without a paint op."""
    ops: list[str] = []
    x = y = sx = sy = 0.0
    for seg in segments:
        op = seg[0]
        if op == "M":
            x, y = seg[1], seg[2]
            sx, sy = x, y
            ops.append(f"{fmt(x)} {fmt(y)} m")
        elif op == "L":
            x, y = seg[1], seg[2]
            ops.append(f"{fmt(x)} {fmt(y)} l")
        elif op == "Q":
            qx, qy, ex, ey = seg[1:]
            c1x, c1y = x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y)
            c2x, c2y = ex + 2 / 3 * (qx - ex), ey + 2 / 3 * (qy - ey)
            ops.append(" ".join(fmt(v) for v in (c1x, c1y, c2x, c2y, ex, ey)) + " c")
            x, y = ex, ey
        else:
            ops.append("h")
            x, y = sx, sy
    return "\n".join(ops)


@lru_cache(maxsize=1024)
def svg_path(d: str) -> str:
    """Catalog path data as compact SVG path data (cached: glyphs repeat across diagrams)."""
    return to_svg(parse(d))


@lru_cache(maxsize=1024)
def pdf_path(d: str) -> str:
    """Catalog path data as PDF path construction operators (cached)."""
    return to_pdf(parse(d))
