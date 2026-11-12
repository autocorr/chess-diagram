"""Hand-transcribed map from semantic glyph keys to (font, code).

Sources: data/GC2004Q.pdf for GC2004D and GC2004X, and the GC2004Y TTF itself, which is
a later revision than the PDF's Y page (it has rank labels 1-26 and file labels a-z).
Verified by eye against tools/contact_sheet.py output.

Conventions found while transcribing:

* Colored figures come in runs of four codes:
  white-on-light, white-on-dark, black-on-light, black-on-dark.
* Neutral figures and colorless specials come in pairs: light, dark.
* Rotation angles are clockwise (a 90-degree queen points its crown to the right).
* Codes skip 0xAD (soft hyphen); the font substitutes another code in that slot
  (e.g. D 0xCB for the 90-degree white knight, X 0xFF for the 225-degree black knight).
* Mirrored knights are the rotated knight reflected left-right, i.e. reflection is
  applied after rotation: mirror 90 is the 90-degree knight flipped horizontally.
* All codes are in 0x20-0xFF, where Windows-1252 equals Unicode, so code == code point.

Key scheme (fields separated by ':'):

    piece:<kind>:<color>:<angle>:<variant>:<shade>
        kind KQRBNP; color white|black|neutral; angle 0..315 step 45;
        variant plain|chameleon|mirror; shade light|dark
    special:<name>:<color>:<shade>      color white|black|neutral|none
    square:<shade>                      empty square
    border:<style>:<side>               side top|bottom|left|right (drawn outside the board)
    corner:double:<pos>                 pos tl|tr|bl|br
    edge:<sides>                        light square with lines inside it, sides joined by '-'
                                        in order top-bottom-left-right
    symbol:<name>                       light square only
    label:<style>:<axis>:<value>        axis rank|file; includes the adjacent border line
"""

from __future__ import annotations

FONTS = {"D": "GC2004D_.TTF", "X": "GC2004X_.TTF", "Y": "GC2004Y_.TTF"}

QUAD = (("white", "light"), ("white", "dark"), ("black", "light"), ("black", "dark"))
PAIR = ("light", "dark")


def _r(first: int, last: int) -> list[int]:
    return list(range(first, last + 1))


# --- Plain pieces: {font: {kind: {angle: [4 codes]}}} -------------------------------------

PLAIN = {
    "D": {
        "K": {
            0: _r(0x30, 0x33),
            90: _r(0x34, 0x37),
            180: [0x38, 0x39, 0x41, 0x42],
            270: _r(0x43, 0x46),
        },
        "Q": {0: _r(0x47, 0x4A), 90: _r(0x4B, 0x4E), 180: _r(0x4F, 0x52), 270: _r(0x53, 0x56)},
        "R": {0: _r(0x57, 0x5A), 90: _r(0x61, 0x64), 180: _r(0x65, 0x68), 270: _r(0x69, 0x6C)},
        "B": {
            0: _r(0x6D, 0x70),
            90: _r(0x71, 0x74),
            180: _r(0x75, 0x78),
            270: [0x79, 0x7A, 0xA7, 0xA8],
        },
        "N": {
            0: _r(0xA9, 0xAC),
            90: [0xCB, 0xAE, 0xAF, 0xB0],
            180: _r(0xB1, 0xB4),
            270: _r(0xB5, 0xB8),
        },
        "P": {0: _r(0xB9, 0xBC), 90: _r(0xBD, 0xC0), 180: _r(0xC1, 0xC4), 270: _r(0xC5, 0xC8)},
    },
    "X": {
        "K": {
            45: _r(0x30, 0x33),
            135: _r(0x34, 0x37),
            225: [0x38, 0x39, 0x41, 0x42],
            315: _r(0x43, 0x46),
        },
        "Q": {45: _r(0x47, 0x4A), 135: _r(0x4B, 0x4E), 225: _r(0x4F, 0x52), 315: _r(0x53, 0x56)},
        "R": {45: _r(0x57, 0x5A), 135: _r(0x61, 0x64), 225: _r(0x65, 0x68), 315: _r(0x69, 0x6C)},
        "B": {
            45: _r(0x6D, 0x70),
            135: _r(0x71, 0x74),
            225: _r(0x75, 0x78),
            315: [0x79, 0x7A, 0xA1, 0xA2],
        },
        "N": {
            45: _r(0xA3, 0xA6),
            135: _r(0xA7, 0xAA),
            225: [0xAB, 0xAC, 0xFF, 0xAE],
            315: _r(0xAF, 0xB2),
        },
        "P": {45: _r(0xB3, 0xB6), 135: _r(0xB7, 0xBA), 225: _r(0xBB, 0xBE), 315: _r(0xBF, 0xC2)},
    },
}

# --- Chameleon pieces (framed), angle 0 only: {kind: (font, [4 codes])} --------------------

CHAMELEON = {
    "K": ("Y", _r(0xC2, 0xC5)),
    "Q": ("D", _r(0xCE, 0xD1)),
    "R": ("D", _r(0xD2, 0xD5)),
    "B": ("D", _r(0xD6, 0xD9)),
    "N": ("D", _r(0xDA, 0xDD)),
    "P": ("D", _r(0xDE, 0xE1)),
}

# --- Mirrored (horizontally reflected) knights, GC2004Y: {angle: [4 codes]} ----------------

MIRROR_KNIGHT = {90: _r(0x30, 0x33), 180: _r(0x34, 0x37), 270: [0x38, 0x39, 0x41, 0x42]}

# --- Neutral pieces (half white, half black): {kind: {angle: (font, [light, dark])}} -------
# GC2004X 0xC3/0xC4 duplicate the 0-degree neutral king of GC2004D and are omitted.

NEUTRAL = {
    "K": {
        0: ("D", [0xEC, 0xED]),
        90: ("X", [0xC5, 0xC6]),
        180: ("X", [0xC7, 0xC8]),
        270: ("X", [0xC9, 0xCA]),
    },
    "Q": {
        0: ("D", [0xEE, 0xEF]),
        90: ("X", [0xCD, 0xCE]),
        180: ("X", [0xCF, 0xD0]),
        270: ("X", [0xD1, 0xD2]),
    },
    "R": {
        0: ("D", [0xF0, 0xF1]),
        90: ("X", [0xD3, 0xD4]),
        180: ("X", [0xD5, 0xD6]),
        270: ("X", [0xD7, 0xD8]),
    },
    "B": {
        0: ("D", [0xF2, 0xF3]),
        90: ("X", [0xD9, 0xDA]),
        180: ("X", [0xDB, 0xDC]),
        270: ("X", [0xDD, 0xDE]),
    },
    "N": {
        0: ("D", [0xF4, 0xF5]),
        90: ("X", [0xDF, 0xE0]),
        180: ("X", [0xE1, 0xE2]),
        270: ("X", [0xE3, 0xE4]),
    },
    "P": {
        0: ("D", [0xF6, 0xF7]),
        90: ("X", [0xE5, 0xE6]),
        180: ("X", [0xE7, 0xE8]),
        270: ("X", [0xE9, 0xEA]),
    },
}

# --- Special figures --------------------------------------------------------------------
# Colored: (font, [4 codes]); colorless or neutral: (font, color, [light, dark]).

SPECIAL_COLORED = {
    "flower": ("D", _r(0xE4, 0xE7)),
    "diamond": ("D", _r(0xF8, 0xFB)),
    "equihopper": ("X", _r(0xEF, 0xF2)),
    "jester": ("Y", _r(0x43, 0x46)),
}

# Pairs where white and black variants are separate glyph pairs rather than a run of four.
SPECIAL_SPLIT = {
    "ring": ("D", [0xE8, 0xE9], [0xEA, 0xEB]),
    "orphan": ("X", [0xF7, 0xF8], [0xF9, 0xFA]),
    "star": ("X", [0xFB, 0xFC], [0xFD, 0xFE]),
}

SPECIAL_PAIRED = {
    "box": ("D", "none", [0xE2, 0xE3]),
    "cross": ("D", "none", [0xFC, 0xFD]),
    "orphan": ("D", "neutral", [0xFE, 0xFF]),
    "equihopper": ("X", "neutral", [0xF5, 0xF6]),
}

# --- Board furniture ----------------------------------------------------------------------

SQUARES = ("D", [0xA3, 0xA4])

BORDERS = {
    "single": ("D", {"top": 0xA6, "bottom": 0xA1, "left": 0xA2, "right": 0xA5}),
    "double": ("Y", {"top": 0x4C, "bottom": 0x53, "left": 0x4E, "right": 0x51}),
}

CORNERS_DOUBLE = {"tl": 0x4B, "tr": 0x4D, "bl": 0x52, "br": 0x54}

EDGES = {
    "bottom-right": 0x57,
    "top-right": 0x58,
    "top-left": 0x59,
    "bottom-left": 0x5A,
    "left-right": 0x65,
    "top-bottom": 0x66,
    "bottom-left-right": 0x61,
    "top-bottom-right": 0x62,
    "top-left-right": 0x63,
    "top-bottom-left": 0x64,
}

SYMBOLS = {
    "D": {"arrow-both": 0xC9, "arrow-right": 0xCA, "check": 0xCD},
    "Y": {
        "arrow-up": 0xC6,
        "arrow-left": 0xC7,
        "arrow-down": 0xC8,
        "arrow-turn": 0xC9,
        "arrow-uturn": 0xCA,
        "arrow-loop": 0xCB,
    },
}

# Glyphs whose outline is misplaced in the shipped font: {(font, code): dx in font units}.
# The catalog outline is shifted by dx; typesetters using the real font must kern by dx
# before the glyph and by -dx after it.
FIXUPS = {
    ("D", 0x37): -233,  # black king, 90 degrees, dark square: drawn 233 units right of its cell
}

# Codes present in the fonts but deliberately left out of the catalog.
IGNORED = {
    "D": {
        0xAD: "near-duplicate of 0xCB (90-degree white knight in the soft-hyphen slot)",
        0xCC: "exact duplicate of 0xCB",
    },
    "X": {
        0xC3: "duplicate of GC2004D 0xEC (0-degree neutral king, light)",
        0xC4: "duplicate of GC2004D 0xED (0-degree neutral king, dark)",
    },
    "Y": {
        0x4F: "same as GC2004D empty light square 0xA3",
        0x50: "same as GC2004D empty dark square 0xA4",
        0x55: "same as GC2004D left border 0xA2 (plus anchor specks)",
        0x56: "same as GC2004D right border 0xA5 (plus anchor specks)",
    },
}

LETTERS = "abcdefghijklmnopqrstuvwxyz"
RANK_SINGLE = _r(0x67, 0x7A) + _r(0xA1, 0xA6)  # 1..26
FILE_SINGLE = _r(0xA7, 0xAC) + _r(0xAE, 0xC1)  # a..z (skips 0xAD)
RANK_DOUBLE = _r(0xCC, 0xE5)  # 1..26
FILE_DOUBLE = _r(0xE6, 0xFF)  # a..z


def entries() -> list[tuple[str, str, int]]:
    """Every catalog entry as (key, font, code)."""
    out: list[tuple[str, str, int]] = []

    def quad(prefix: str, font: str, codes: list[int], suffix: str = "") -> None:
        assert len(codes) == 4, prefix
        for (color, shade), code in zip(QUAD, codes, strict=True):
            out.append((prefix.format(color=color) + suffix + f":{shade}", font, code))

    def pair(prefix: str, font: str, codes: list[int]) -> None:
        assert len(codes) == 2, prefix
        for shade, code in zip(PAIR, codes, strict=True):
            out.append((f"{prefix}:{shade}", font, code))

    for font, kinds in PLAIN.items():
        for kind, angles in kinds.items():
            for angle, codes in angles.items():
                quad(f"piece:{kind}:{{color}}:{angle}:plain", font, codes)
    for kind, (font, codes) in CHAMELEON.items():
        quad(f"piece:{kind}:{{color}}:0:chameleon", font, codes)
    for angle, codes in MIRROR_KNIGHT.items():
        quad(f"piece:N:{{color}}:{angle}:mirror", "Y", codes)
    for kind, angles in NEUTRAL.items():
        for angle, (font, codes) in angles.items():
            pair(f"piece:{kind}:neutral:{angle}:plain", font, codes)

    for name, (font, codes) in SPECIAL_COLORED.items():
        quad(f"special:{name}:{{color}}", font, codes)
    for name, (font, white, black) in SPECIAL_SPLIT.items():
        pair(f"special:{name}:white", font, white)
        pair(f"special:{name}:black", font, black)
    for name, (font, color, codes) in SPECIAL_PAIRED.items():
        pair(f"special:{name}:{color}", font, codes)

    pair("square", *SQUARES)
    for style, (font, sides) in BORDERS.items():
        for side, code in sides.items():
            out.append((f"border:{style}:{side}", font, code))
    for pos, code in CORNERS_DOUBLE.items():
        out.append((f"corner:double:{pos}", "Y", code))
    for sides, code in EDGES.items():
        out.append((f"edge:{sides}", "Y", code))
    for font, symbols in SYMBOLS.items():
        for name, code in symbols.items():
            out.append((f"symbol:{name}", font, code))

    for style, ranks, files in (
        ("single", RANK_SINGLE, FILE_SINGLE),
        ("double", RANK_DOUBLE, FILE_DOUBLE),
    ):
        assert len(ranks) == len(files) == 26
        for i in range(26):
            out.append((f"label:{style}:rank:{i + 1}", "Y", ranks[i]))
            out.append((f"label:{style}:file:{LETTERS[i]}", "Y", files[i]))

    keys = [k for k, _, _ in out]
    assert len(keys) == len(set(keys)), "duplicate catalog keys"
    return out
