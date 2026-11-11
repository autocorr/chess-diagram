# Architecture

This project renders chess diagrams, including fairy and problem diagrams, from an
extended FEN string. It uses the **Good Companion (GC2004)** fonts by David L. Brown.

It has three goals:

1. **A browser editor**: an interactive diagram editor that runs in a web browser.
2. **Standalone PDF and SVG files**: self-contained files that render identically everywhere.
3. **LaTeX booklets**: diagrams set directly in LaTeX, so a document with about 100
   diagrams embeds the font **once** instead of once per included figure.

There are two scope decisions:

- **No PostScript output.** Its purpose was to keep figures small in LaTeX, and the LaTeX
  integration does that better.
- **Standalone files use vector outlines.** They draw glyph outlines taken from the fonts
  and never embed the fonts.

---

## 1. Source material

| File | Contents |
|---|---|
| `data/GC2004D_.TTF` | Empty squares, single border, pieces at 0/90/180/270°, chameleon (framed) Q R B N P, neutral pieces at 0°, symbols (↔ → ✓), special markers (box, flower, ring, diamond, cross, half-circle) |
| `data/GC2004X_.TTF` | Pieces at 45/135/225/315°, neutral pieces at 90/180/270°, special markers (equihopper, circle, star) |
| `data/GC2004Y_.TTF` | Double border and corners, 2- and 3-sided edge squares, arrows, mirrored knights at 90/180/270°, chameleon king, jester figures, rank labels 1–26 and file labels a–z in single and double styles |
| `data/GC2004Q.pdf` | Quick reference showing the code and image for every glyph |

Facts about the fonts, verified in Phase 1:

- All three are TrueType (`glyf`) fonts with 2000 units per em.
- Every glyph advances 2000 units. A board square spans y = −500…1500 in font units, so
  each cell is 2000 × 2000.
- All codes used are in 0x21–0xFF, where Windows-1252 and Unicode agree, so
  **code = Unicode code point** and fontspec can address glyphs with `\char`.
- Each figure comes in a light-square and a dark-square version, and the hatching on dark
  squares is real outline geometry. A cell is therefore always exactly one glyph, chosen by
  figure and square shade. An empty light square is a blank glyph.
- Coloured figures come in runs of four codes: **white on light, white on dark, black on
  light, black on dark**. Neutral and colourless figures come in light/dark pairs.
- Rotations are **clockwise**: a queen at 90° points its crown to the right.
- The codes skip 0xAD (soft hyphen). Another code fills that slot, e.g. D 0xCB for the
  90° white knight on a light square, and X 0xFF for the 225° black knight on a light
  square. Code ranges therefore can't be assumed to be contiguous.
- Border glyphs draw their line *outside* the board, in the neighbouring cell. Single
  borders are 100 units thick. Double borders are a 50-unit line next to the board, a
  100-unit gap, and a 200-unit line, 350 units in total. The double-border corners are
  350-unit blocks.
- The edge-square glyphs in GC2004Y draw their lines *inside* the cell and exist only for
  light squares, so they're catalogued but not used for borders around holes.

Quirks, which the catalog builder handles (see §4.1):

- **The GC2004Y TTF is a later revision than the Y page of the PDF.** Its labels run a–z
  and 1–26 at different codes. The TTF is authoritative, and the PDF is only used for
  naming.
- GC2004Y has tiny 15 × 15-unit "anchor" specks in the cell corners, presumably to fix
  bounding boxes in word processors. They would show up as dots in vector output.
- **D 0x37** (black king, 90°, dark square) is drawn 233 units to the right of its cell, a
  defect in the shipped font.
- Duplicates are skipped: D 0xAD/0xCC (copies of 0xCB), X 0xC3/0xC4 (copies of D's neutral
  king), and Y 0x4F/0x50/0x55/0x56 (copies of D's squares and single borders).

> **Licensing:** the reference PDF says the GC fonts are "used exclusively for diagrams on
> www.StrateGems.org". Confirm redistribution rights before publishing the font files with
> the LaTeX package or serving them to browsers. The outlines in `catalog.json` are derived
> from the fonts too.

---

## 2. Overview

```
  tools/catalog_spec.py ─┐
            data/*.TTF  ─┴─►  tools/build_catalog.py  (fontTools, build-time only)
                                     │
                    ┌────────────────┼──────────────────────┐
                    ▼                ▼                      ▼
          catalog.json         catalog.lua           contact-sheet.svg
        (codes + outlines)   (codes for LuaTeX)     (tools/contact_sheet.py,
                                                     manual verification)
                    │                │
                    ▼                ▼
               Python pkg      LuaLaTeX package
               (gcdiagram)     (gcdiagram.sty/.lua)
                    ├─► SVG  (outlines, <symbol>/<use>)
                    ├─► PDF  (outlines, hand-written writer)
                    ├─► TeX snippet (glyph codes, for gcsnippet.sty)
                    └─► gcdiagram.editor ─► web editor
                                            (Pyodide in a Web Worker + TypeScript UI)

  tests/vectors.json ─► shared FEN conformance tests run by Python and Lua
```

Two parts are shared by every implementation:

1. **The glyph catalog**, generated once from the TTFs. It is the only place that knows
   which font and code draw a given figure on a given shade.
2. **The FEN test vectors**, which every parser (Python and Lua) must pass. This keeps
   the two implementations of the grammar in agreement. The browser editor runs the
   Python package itself, so it needs no third implementation (§10).

---

## 3. Repository layout

```
chess-diagram-generator/
├── ARCHITECTURE.md
├── pyproject.toml                  # uv project; runtime deps: none
│                                   # dev deps: fonttools, pytest, ruff, ty
├── data/                           # original TTFs + reference PDF (inputs, never modified)
├── tools/
│   ├── build_catalog.py            # TTF → catalog.json / catalog.lua
│   ├── catalog_spec.py             # hand-written table: semantic key → (font, code)
│   └── contact_sheet.py            # renders every catalog entry for visual checking
├── src/gcdiagram/
│   ├── __init__.py                 # public API: parse(), serialize(), render_svg(), render_pdf()
│   ├── data/catalog.json           # generated, committed
│   ├── catalog.py                  # loads catalog, resolves (Figure, Shade) → Glyph
│   ├── fen.py                      # extended-FEN tokenizer/parser/serializer
│   ├── board.py                    # board model (cells, figures, shades)
│   ├── geometry.py                 # layout: cell rects, border segments, hole outlines, arrows, marks
│   ├── options.py                  # RenderOptions (border style, captions, annotations, scale, …)
│   ├── annotations.py              # annotation kinds, colours and their text form
│   ├── markup.py                   # <b>/<i> caption markup → styled runs
│   ├── svgpath.py                  # outline parsing; compact SVG and cubic PDF encodings
│   ├── textmetrics.py              # Helvetica and Helvetica-Bold widths for caption layout
│   ├── editor.py                   # JSON-friendly operations for the browser editor
│   ├── render/
│   │   ├── svg.py
│   │   ├── pdf.py                  # minimal PDF 1.4 writer (paths + Flate + Helvetica caption)
│   │   └── tex.py                  # LaTeX snippet output (route A)
│   └── cli.py                      # `gcdiagram FEN -o out.svg|pdf|tex [options]`
├── latex/
│   ├── gcsnippet.sty               # shared drawing primitives (\gcbox); LuaLaTeX/XeLaTeX
│   ├── gcdiagram.sty               # route B: \gcdiagram[keys]{fen} (LuaLaTeX)
│   ├── gcdiagram.lua               # route B: Lua port of parser, layout and emitter
│   ├── gcdiagram-catalog.lua       # generated
│   └── examples/booklet.py         # 100-diagram size and speed comparison
├── web/                            # browser editor: Pyodide + TypeScript UI (Vite, Node ≥ 22.12)
│   ├── index.html, src/main.ts     # UI: input handling, palette, options, URL hash, export
│   ├── src/worker.ts, python.ts    # Pyodide worker and its promise-based client
│   ├── vite.config.ts              # serves Pyodide + live Python sources (no CDN)
│   └── e2e/                        # Playwright tests
└── tests/
    ├── vectors.json                # shared FEN conformance cases
    ├── cases.py                    # representative diagrams for renderer tests
    ├── lua/                        # texlua runners for the vectors and Lua/Python parity
    ├── test_*.py
    └── golden/                     # golden SVG outputs
```

---

## 4. Glyph catalog

### 4.1 Building it

`tools/catalog_spec.py` is a hand-written table that maps semantic keys to `(font, code)`.
D and X are transcribed from `GC2004Q.pdf`, and Y from the TTF itself (see §1). The spec
also lists `FIXUPS` (misplaced glyphs) and `IGNORED` (duplicate codes). Run
`uv run python tools/build_catalog.py`, which:

1. Opens each TTF with fontTools and looks up each code through the cmap.
2. Extracts each outline in **cell coordinates**: origin at the cell's top-left, y
   pointing down, and a square spanning 0…2000 on both axes, so `y_cell = 1500 − y_font`.
   Border, corner and label glyphs extend beyond 0…2000 and are placed in the cell next
   to the board.
3. Drops speck contours (no larger than 20 × 20 units) and applies the `FIXUPS` shifts.
4. Removes duplicate outlines, storing identical paths once and referencing them by id.
5. Writes `src/gcdiagram/data/catalog.json` (codes, outlines, bounding boxes) and
   `latex/gcdiagram-catalog.lua` (codes and fix-ups only, because TeX draws the real font).
6. Reports any non-blank code in the fonts that isn't in the catalog and isn't listed in
   `IGNORED`.

`tools/contact_sheet.py` renders every entry with its key and code to
`build/contact-sheet.svg`, for checking against the reference PDF by eye. Phase 1 did this
for every group. `tests/test_catalog.py` checks completeness, the key format, uniqueness of
codes, the cell bounds, that `catalog.json` is up to date with the spec and fonts, and that
the Lua copy matches.

### 4.2 Key scheme

```
piece:<kind>:<color>:<angle>:<variant>:<shade>
    kind ∈ K Q R B N P; color ∈ white black neutral; angle ∈ 0 45 … 315;
    variant ∈ plain chameleon mirror; shade ∈ light dark
special:<name>:<color>:<shade>   color ∈ white black neutral none
square:<shade>                   empty square
border:<style>:<side>            style ∈ single double; side ∈ top bottom left right
corner:double:<pos>              pos ∈ tl tr bl br
edge:<sides>                     e.g. edge:top-left, edge:top-bottom-right (light only)
symbol:<name>                    arrow-both arrow-right check (D); arrow-up arrow-left
                                 arrow-down arrow-turn arrow-uturn arrow-loop (Y)
label:<style>:<axis>:<value>     axis ∈ rank (1–26) file (a–z); includes the border line
```

What the fonts cover (all with light and dark versions):

| Set | Colours | Angles |
|---|---|---|
| plain K Q R B N P | white, black | all 8 |
| plain K Q R B N P | neutral | 0, 90, 180, 270 |
| chameleon K Q R B N P | white, black | 0 |
| mirror N | white, black | 90, 180, 270 (the rotated knight reflected left–right) |

| Special | Colours |
|---|---|
| `flower`, `diamond`, `ring`, `circle`, `star`, `jester` | white, black |
| `equihopper` | white, black, neutral |
| `half-circle` | neutral |
| `box`, `cross` | none |

### 4.3 JSON shape

```json
{
  "version": 1, "unitsPerEm": 2000, "cell": 2000, "baseline": 1500,
  "fonts": {"D": "GC2004D_.TTF", "X": "GC2004X_.TTF", "Y": "GC2004Y_.TTF"},
  "outlines": {"o17": "M1190 554V257L1044 405Z…"},
  "glyphs": {
    "piece:Q:white:90:plain:dark": {"font": "D", "code": 76, "outline": "o17", "bbox": [x0, y0, x1, y1]},
    "piece:K:black:90:plain:dark": {"font": "D", "code": 55, "outline": "o9", "bbox": […], "dx": -233}
  }
}
```

`dx`, where present, is a horizontal correction already applied to the outline. A
typesetter using the real font must kern by `dx` font units before the glyph and by `−dx`
after it.

---

## 5. Extended FEN

### 5.1 Grammar

```
fen      := board (WS rest)?                  rest (side to move, castling, …) is ignored
board    := rank ("/" rank)*                  first rank is the top row
rank     := item+
item     := empty | piece | token | hole | wall
empty    := [1-9][0-9]*                       run of empty squares; multi-digit allowed
piece    := [KQRBNPkqrbnp]                    uppercase = white, lowercase = black
token    := "{" mod? letter angle? "}"
          | "{" "="? "@" name "}"             special figure on a square
mod      := "=" (neutral) | "~" (chameleon) | "!" (mirrored)
letter   := [KQRBNPkqrbnp]
name     := [A-Za-z][a-z-]*                   catalog special name; case of 1st letter = colour
angle    := "0" | "45" | "90" | "135" | "180" | "225" | "270" | "315"   (default 0)
hole     := "."                               no square: nothing drawn, border goes around it
wall     := "*"                               a blocked square: present but unusable, drawn solid
```

Examples:

```
rnb{q180}kbnr/pppp.ppp/8/8/8/8/PPPPPPPP/{R90}NBQKBN{R270}
10/{=Q}9/…                     10-file board with a neutral queen
4{~b}3/8/…/{@Star}7            chameleon black bishop, white star
{!n180}7/…                     mirrored black knight at 180°
```

### 5.2 Rules

- Every rank must be the same width. The board can be any size from 1×1 to 26×26. The
  limit of 26 matches the rank labels in GC2004Y and can be lifted.
- Letter case gives the colour of `{~x}`, `{!x}` and `{@Name}` figures. For neutral
  `{=x}` and `{=@name}` the case is ignored. A special that exists in only one colour
  (`box`, `cross`, `half-circle`) accepts either case.
- Mirroring is applied after rotation: `{!N90}` is the 90° knight reflected left–right.
- A figure/angle combination the font doesn't contain is a **parse error with a clear
  message**. Checking happens against the catalog, so the grammar stays simple.
- Serialising is canonical: standard pieces at 0° are written as bare letters, empty runs
  are merged, and `{Q0}` becomes `Q`. As a result, `serialize(parse(s))` is stable, and
  the web editor shows a clean FEN.

### 5.3 Square names

These are used by arrows and the API. Files are lettered `a`, `b`, …, `z` from the left.
Ranks are numbered `1`, `2`, … from the bottom. For example, `e2` and `j10`.

---

## 6. Board model (`board.py`)

```python
Color        = Literal["white", "black", "neutral"]
SpecialColor = Literal["white", "black", "neutral", "none"]
Variant      = Literal["plain", "chameleon", "mirror"]
Shade        = Literal["light", "dark"]

@dataclass(frozen=True) class Piece:    kind: str; color: Color; angle: int = 0; variant: Variant = "plain"
@dataclass(frozen=True) class Special:  name: str; color: SpecialColor
Figure = Piece | Special

@dataclass(frozen=True) class Square:   figure: Figure | None = None
@dataclass(frozen=True) class Hole:     ...
@dataclass(frozen=True) class Wall:     ...
Cell = Square | Hole | Wall

@dataclass class Board:
    cells: list[list[Cell]]                  # cells[row][col], row 0 = top rank
    width, height                            # properties
    shade(row, col) -> Shade                 # a1 (bottom-left) is dark on every board size
    board["e4"], board[(row, col)]           # get/set by square name or position
    is_board_square(row, col)                # squares and walls; False for holes/off-board
    piece_count() -> (white, black, neutral)
```

The model knows nothing about rendering. The only connection between the model and the
fonts is `Catalog.figure_glyph(figure, shade)` in `catalog.py` (and
`Catalog.cell_glyph(cell, shade, wall)`, which every renderer uses to pick a cell's glyph),
along with `Catalog.supports(figure)`, which the parser uses for validation.

---

## 7. Layout (`geometry.py`)

All renderers share `layout(board, options) -> Layout`. It works in font units (a square
is 2000, y points down) and is scaled at output time. A `Layout` contains:

- **`glyphs`:** `GlyphUse(key, x, y, square)` for every non-blank cell. Empty light squares
  are blank glyphs and are skipped.
- **`rects`:** filled rectangles for borders and solid walls. With `wall="box"`, a wall
  is drawn with the framed `special:box:none` glyph instead.
- **`arrows`:** 7-point polygons from the centre of the start square to the tip at the
  centre of the target square.
- **`marks`:** annotations (`annotations.py`), each a filled path with a fill colour and
  a white halo stroked behind it, so marks stay visible on dark squares and black pieces. Arrows use the
  arrow polygon. Circles (eight quadratic Béziers), squares and triangles are rings: an
  outer contour and an inner one wound the other way, so the nonzero fill rule that
  SVG, PDF and PGF all default to leaves the middle open. A cross is one 12-point
  polygon, and a dot a solid circle a fifth of a square across. The colours are black, gray `#808080`, and the Okabe-Ito vermilion `#D55E00`
  (labelled "Orange" in the editor), blue `#0072B2` and bluish green `#009E73`, which
  colour-blind readers can still tell apart. The text form is
  `kind:square[:colour]` or `arrow:from-to[:colour]`, and black is left out.
- **`texts`:** lines of styled runs. `caption_above` lines go above the board and
  `caption` lines under it, all left-aligned, plus the optional piece count
  right-aligned on the first line below. Captions wrap at spaces to the diagram's
  width, and the first line below stops one caption em (`COUNT_GAP`) short of the
  count, so the two never collide. Only a word too long for any line widens the
  diagram. `<b>` and `<i>` markup (`markup.py`) splits a line into runs. Tags were
  chosen over `*…*` because stipulations use `*` for set play. Widths use Helvetica
  and Helvetica-Bold metrics (`textmetrics.py`); the oblique fonts have the same
  widths as the upright ones.

The border options are:

| `border` | Frame | Lines around holes |
|---|---|---|
| `single` (default) | 100-unit ring around the bounding rectangle | yes, single |
| `double` | 50 thin + 100 gap + 200 thick (GC2004Y proportions) | yes, single |
| `outline` | none: a single line follows the board's shape | yes (part of the outline) |
| `none` | none | no |

Hole lines are drawn outside the squares, in the hole's cell, like the GC border glyphs.
For every exposed edge of a square (or wall), the layout emits a 100-unit rectangle, plus
a corner square wherever two exposed edges meet at a convex corner. Concave corners close
because the two rectangles overlap. Collinear rectangles are then merged, so a plain
board's border is just four rectangles. Borders are filled rectangles rather than stroked
lines, so they can't depend on stroke-join settings.

---

## 8. Output formats

### 8.1 SVG (`render/svg.py`)

- Each glyph outline used is defined once as `<path id>` in `<defs>`, and each cell is a
  `<use href="#…" x y>`. Ids are short (`ga`, `gb`, …) with a configurable prefix, so
  several diagrams can be inlined in one HTML page.
- Path data is re-encoded by `svgpath.py` as relative commands with minimal separators,
  about 21% smaller than the catalog form. The `viewBox` is in font units, so coordinates
  stay integers. Width and height are given in pt.
- All border and wall rectangles form a single `<path>`, and so do all arrows.
- Options: `xlink=True` writes `xlink:href` for SVG 1.1 tools (the Inkscape here needs
  it); `annotate=True` adds `data-square="e4"` to each `<use>` for scripting and the web
  editor.
- Captions use `font-family="Helvetica,Arial,sans-serif"`. A line with bold or italic
  runs puts each in a `<tspan>`, and `xml:space="preserve"` keeps the spaces between them.
- Each annotation is a `<path>`, preceded by the same path stroked in white.
- Size: a full starting position is about 26 KB. Most of that is the dark-square hatching,
  which the font repeats inside every piece-on-dark glyph.

### 8.2 PDF (`render/pdf.py`)

- A minimal PDF 1.4 writer with no dependencies: catalog, one page, and Flate-compressed
  streams. Output is deterministic (no dates or IDs).
- Each distinct glyph becomes a Form XObject reused with `Do`, the PDF equivalent of SVG
  `<use>`. Quadratic TrueType curves are raised to cubics.
- The page content starts with a single `cm` that maps font units (y down) to points
  (y up). It's written at full precision; two-decimal rounding broke non-20 pt sizes,
  and a regression test now covers that.
- Captions use base-14 Helvetica with WinAnsiEncoding, which is never embedded, plus
  Helvetica-Bold, -Oblique and -BoldOblique for styled runs (only the styles used get
  a font resource). A styled line is one `BT … ET` that switches fonts with `Tf`. Arrow
  opacity uses an ExtGState.
- The page is cropped exactly to the diagram plus padding, so it can be included as-is in
  other documents. Colours are `#rgb`, `#rrggbb`, `white` or `black`.

### 8.3 TeX snippet (`render/tex.py`), LaTeX route A

`render_tex` (or `gcdiagram FEN -o d.tex`) writes one call to `\gcbox`, which is defined
in `latex/gcsnippet.sty`:

```latex
\gcbox{6.1}{6.1}{%                                  width, height (in squares)
\gcrank{.05}{5.3}{\gcD{£££¤££}}%                    one glyph run per rank, at its baseline
\gcrank{.05}{4.3}{\gcD{£0¤£¤£}\gcY{0}}%             a run per font
\gcrects{\gcr{1.05}{3.05}{1}{1}\gcr{0}{6.05}{6.1}{.05}…}%   borders and walls
\gcarrows{000000}{0.6}{\gcm{x}{y}\gcl{x}{y}…\gcz}%  arrows (colour, opacity, polygons)
\gcmark{D55E00}{0}{\gcm{x}{y}\gcq{cx}{cy}{x}{y}…\gcz}%  one annotation (colour, halo, path)
}{\#2}{(3+2)}%                                       caption lines (\\-separated), count
```

With a caption above the board, the call starts `\gcbox[{lines}]{…}`. Caption markup
becomes `\textbf` and `\textit`. A `\gcmark` halo above zero strokes the path in white
at that width (in squares) before filling it.

- **Glyphs as text:** every glyph code is a digit, an ASCII letter or a Latin-1 symbol,
  none of which are special to TeX, so a rank is plain UTF-8 text in the right font.
  Holes and solid walls use the blank light-square glyph to keep the advance.
  `\gcfix{dx}{c}` kerns around glyphs with a catalog `dx` (D 0x37).
- **Units:** coordinates are numbers of squares, multiplied by `\gcsquare` (default 20 pt,
  set with `\gcsquaresize`), with y pointing up from the diagram's bottom-left corner.
  The same snippet works at any size. The font is set at size `\gcsquare`, so one em is
  one square.
- **Ranks placed explicitly:** TeX gives each glyph box its ink extent as height and
  depth, not the cell's, so ranks can't be stacked as lines. Each rank is a `\pgftext`
  at its baseline, 1500 font units below the cell top.
- **Drawing:** `gcsnippet.sty` uses only the pgf basic layer: rectangles and polygons
  are filled paths, and arrow opacity uses `\pgfsetfillopacity`. Bounding boxes are set
  explicitly, so the box is exactly `width × height` squares. Captions are set in the
  document font (`\gccaptionfont`, default `\small`), ragged-right across the
  diagram's width, with the count right-aligned on the first line. `\parshape` shortens
  that first line by the count and `\gccountgap` (default 1em), so TeX wraps the caption
  before the count, as the SVG and PDF layout does.
- **Fonts:** loaded once at `\begin{document}` with `fontspec`, from `\gcfontpath{dir/}`
  or the system. Kerning is off, because GC2004Y has a `kern` table. Works with
  LuaLaTeX and XeLaTeX. pdfLaTeX would need a Type 1 conversion, which is out of scope.

---

## 9. LuaLaTeX package, LaTeX route B (`latex/gcdiagram.sty` + `.lua`)

```latex
\usepackage{gcdiagram}
\gcfontpath{path/to/data/}
\gcdiagramsetup{size=18pt}
\gcdiagram[border=double, caption={\#2}, count, arrows={e2-e4, g1-f3}]
          {rnb{q180}kbnr/pppp.ppp/8/8/8/8/PPPPPPPP/{R90}NBQKBN{R270}}
```

- **Keys** (`l3keys`, per diagram or in `\gcdiagramsetup`): `size`, `border`, `wall`,
  `caption` and `caption above` (LaTeX text, with `\\` between lines), `count`,
  `arrows`, `arrow color` (`RRGGBB`) and `arrow opacity`. Annotations (circles,
  crosses and so on) are not ported to Lua yet; route A snippets can carry them.
- **Parsing:** the FEN reaches Lua as a string through `\detokenize`/`\lua_escape:e`.
  `gcdiagram.lua` ports `fen.py`, the layout from `geometry.py` (frame, hole borders
  with merging, arrows) and the emitter from `render/tex.py`. It returns
  `\gcLuaResult{w}{h}{body}{count}`, and `\gcbox` from `gcsnippet.sty` draws that, with
  the caption added on the TeX side. FEN errors become TeX errors with the parser's
  message.
- **Kept identical to Python:** the Lua functions are pure, so `texlua` runs them in
  tests. The Lua parser must pass `tests/vectors.json`, and for every case in
  `tests/cases.py` the Lua `\gcbox` body must equal Python's byte for byte. The arrow
  arithmetic is written the same way in both languages (`sqrt`, no intermediate
  rounding), so the doubles agree. Finally, the same document built with routes A and B
  must rasterise to identical pixels.
- **Installation:** `gcsnippet.sty`, `gcdiagram.sty`, `gcdiagram.lua` and
  `gcdiagram-catalog.lua` must be on both `TEXINPUTS` and `LUAINPUTS` (or in a texmf
  tree), because LuaTeX finds `require`d modules through `LUAINPUTS`.

### Comparing routes A and B

`uv run python latex/examples/booklet.py` builds a reproducible booklet of 100 diagrams
at 16 pt squares (13 pages). About a third of the diagrams have fairy pieces, and every
seventh has holes. Measured with TeX Live 2022 on Debian 12, with a warm cache:

| Variant | Engine | PDF size | Compile time |
|---|---|---:|---:|
| 100 standalone PDFs (`render_pdf`) via `\includegraphics` | LuaLaTeX | 1336 KiB | 0.37 s |
| Route A: Python snippets (49 KiB of `.tex` in total) | LuaLaTeX | 60 KiB | 0.74 s |
| Route A | XeLaTeX | 50 KiB | 0.41 s |
| Route B: `\gcdiagram{fen}` | LuaLaTeX | 60 KiB | 0.75 s |

- **Size:** both LaTeX routes are about **22× smaller** than including standalone PDFs.
  Each GC font is embedded once as a subset, instead of every figure carrying its own
  glyph outlines (about 13 KiB each).
- **Speed:** LuaLaTeX's extra 0.4 s is a fixed cost of loading fonts through luaotfload,
  not a per-diagram cost. Route B's Lua parsing costs nothing measurable.
- **Rendering:** routes A and B are pixel-identical. The standalone PDFs differ only in
  caption font (Helvetica rather than the document font).

Decision: **keep both routes.** They share `gcsnippet.sty`, so the only duplication is the
Lua port, which the parity tests above protect.

- Route B is the authoring route: FENs live in the `.tex` source and no build step is
  needed.
- Route A is for XeLaTeX users, for documents generated by Python, and for build systems
  that would rather not run Lua.

---

## 10. Browser editor (`web/`)

The editor is meant to be run locally (`npm run dev` in `web/`), not hosted on the web.
It runs the **real Python package in Pyodide**, so there is no third implementation of
the parser and renderer to keep in sync, and SVG, PDF and TeX exports come out exactly
as the CLI writes them.

```
 main.ts (UI, DOM events) ──postMessage──► worker.ts (Pyodide 314, Python 3.14)
        ▲                                    └─ import gcdiagram.editor
        └──────── {fen, svg, geometry} ◄─────── render / set_cell / move / rotate / …
```

- **Serving:** a Vite plugin (`vite.config.ts`) serves the Pyodide runtime from
  `node_modules/pyodide`, so it works offline with no CDN. It also serves
  `/gcdiagram-sources.json`, the live `src/gcdiagram` package as `{path: text}`, which the
  worker writes into Pyodide's file system before importing it. Editing a `.py` file
  reloads the page with the new code. `npm run build` copies both into `dist/` (about
  14 MB, mostly the Pyodide runtime).
- **Python side** (`gcdiagram/editor.py`, tested by `tests/test_editor.py`): plain-data
  functions. The board state is a canonical FEN string and the options are a dict of
  `RenderOptions` fields. `render` returns the canonical FEN, an SVG annotated with
  `data-square`, the board origin and size for pointer mapping, and each cell's token.
  The edit functions (`set_cell`, `move`, `rotate`, `recolor`, `resize`) take a FEN and
  return a new one, so every edit is checked by the real parser. `rotate` steps to the
  next angle the fonts support for that piece, and `recolor` to the next colour (white,
  black, neutral) they support for that figure. `export` returns SVG, PDF bytes or a TeX
  snippet.
  `info` and `figure_svg` feed the palette. Errors come back as `{error, code}`.
- **UI** (`main.ts`, no framework): it only handles input and display.
  - The Figure box lists the piece and special icons first, then the colour, variant
    and rotation controls, which disable whatever the fonts don't contain.
    A piece is offered if it exists at any angle in the chosen colour and variant, and
    the angle snaps to the nearest one it has (ties clockwise); if the selected piece
    doesn't exist there at all, the first that does is selected. Without this, choosing
    Mirrored at 0° would leave nothing selectable, since mirrored knights only exist at
    90°, 180° and 270°.
  - Tools: place (clicking the same figure again removes it), erase, hole, wall and
    annotate. Annotate draws an arrow on a drag, and on a click the circle, cross,
    square, triangle or dot chosen in the Annotation section, in its chosen colour. Doing
    it again removes it, or recolours it if another colour is chosen. Choosing a
    shape or colour selects the tool. Old links with `arrow=e2-e4` load as black arrow
    annotations.
  - Drag to move. Right-click or <kbd>Del</kbd> clears; <kbd>R</kbd> and
    <kbd>Shift</kbd>+<kbd>R</kbd> rotate the piece under the pointer.
  - Touch: tap places and dragging moves (pointer events throughout). Touch has no hover,
    keys or right-click, so a long-press on a figure opens a menu with rotate, colour
    (white → black → neutral) and clear buttons. Android reports a long-press as
    `contextmenu`, so right-click only clears for a mouse. A tap on the board while the
    menu is open only closes it.
  - Layout: side by side on wide or landscape screens (the page fills the screen, the
    board is sized to fit with a container query, and only the controls scroll); stacked
    on portrait screens, where the board sticks to the top and the controls scroll under
    it. Either way a figure can be picked and placed without scrolling the board away.
  - Help: a modal dialog from the header link.
  - Dark mode: a switch in the header. Until it is used the page follows the system
    setting; a choice is saved in `localStorage`, and a script in `index.html` applies it
    before the first paint. The board and palette glyphs are dimmed with a CSS
    `brightness()` filter so their white doesn't glare; this is display-only, and exports
    (rendered by Python) are unchanged, which a test checks against the CLI.
  - Board size, border, wall style, captions above and below (B and I buttons, and
    <kbd>Ctrl</kbd>+<kbd>B</kbd>/<kbd>I</kbd>, wrap the selection in `<b>`/`<i>` or
    unwrap it), piece count and square size.
  - FEN field: validated as you type and normalised when you leave it.
  - URL hash state, so a link or a reload restores the diagram.
  - SVG/PDF/TeX download, plus PNG at 150, 300 or 600 dpi. PNG is editor-only: the
    browser draws the SVG export onto a canvas sized from its pt dimensions, because
    Pyodide has no rasteriser. Captions use the viewer's Helvetica or Arial, so PNGs
    aren't byte-identical across machines; the test checks the size and sample pixels.
    Images over 100 million pixels are refused.
- **Pointer mapping:** client coordinates go through the SVG's screen CTM into font units,
  and then into a square using the board origin returned by `render`.
- **Ordering:** UI actions run through one queue, so fast clicks can't race.
  `body[data-busy]` is set while work is pending, and `body[data-ready]` once Python has
  started and the first render is done. The tests wait on both.

Decision record: a TypeScript port of the parser, layout and SVG renderer was written
first. It passed the shared vectors and reproduced the golden SVGs byte for byte. It was
replaced by Pyodide because the editor is only hosted locally, where the roughly 12 MB
runtime and its startup delay don't matter, and one implementation is easier to maintain.
If diagrams ever need to be shown on public web pages, a small TypeScript renderer (or the
pre-rendered SVGs) would be the lighter option.

---

## 11. Testing

- **`tests/vectors.json`** has a `valid` list of
  `{fen, width, height, canonical, cells}`, where `cells` maps every non-empty square name
  to `piece:K:white:0:plain`, `special:star:black`, `hole` or `wall`. It also has an
  `invalid` list of `{fen, error}`, where `error` is a stable code: `empty`, `empty-rank`,
  `uneven-ranks`, `bad-count`, `too-large`, `bad-char`, `unterminated-token`,
  `bad-token`, `bad-angle`, `unsupported` or `unknown-special`. Python (pytest), Lua
  (`texlua`) both run the same file.
- **Catalog tests:** completeness, key format, uniqueness of codes, cell bounds, that
  `catalog.json` is up to date with the spec and fonts, and that the Lua copy matches. The
  contact sheet was reviewed by eye in Phase 1.
- **Layout tests:** border coverage around holes and convex/concave corners, frame
  merging, sizes, captions and arrows.
- **Golden SVGs** (`tests/golden/`, cases in `tests/cases.py`) are compared byte for byte:
  a standard position with caption and count, fairy pieces with a double border and
  arrows, holes and walls with a frame, an outline-style irregular board, and a 12×11
  board at 12 pt. To regenerate them, run `GCDIAGRAM_REGEN=1 uv run pytest tests/test_svg.py`.
- **PDF tests:** xref offsets, determinism, no embedded fonts, and `pdfinfo` page size.
  Each case is also rasterised with `pdftoppm` and compared (RMSE after downsampling)
  against an Inkscape raster of the SVG. Tests that need these tools are skipped when
  they're missing.
- **Editor bridge** (`tests/test_editor.py`): palette info, render geometry, every edit
  operation, error reporting, and exports identical to the renderers.
- **Browser** (`web/e2e/`, Playwright with Chromium; `npm run test:e2e`): Python starts
  without page errors, FEN typing validates and normalises, placing, toggling, clearing,
  rotating (with unsupported angles skipped), dragging, holes, walls, resizing, arrows and
  options all work, the URL hash restores state, and the SVG/PDF/TeX downloads are
  byte-identical to `uv run gcdiagram` with the same arguments. At phone, tablet and
  desktop sizes in both orientations the page never scrolls sideways and the board stays
  in view while the palette and options are on screen. With touch emulation, taps place,
  drags move and the long-press menu rotates, recolours and clears. The suite passed 5
  repeated runs (90 tests) without a failure.
- **LaTeX** (`tests/test_latex.py`): `texlua` runs the shared vectors against the Lua
  parser; the Lua `\gcbox` body must equal Python's for every case; route A must compile
  with LuaLaTeX and XeLaTeX with each GC font embedded once; route B must compile and
  rasterise pixel-identically to route A; and a bad FEN must give a TeX error. These
  tests are skipped if `texlua`, `lualatex` or `xelatex` is missing.

---

## 12. Implementation phases

1. **Catalog** (done): write `catalog_spec.py`, build `catalog.json` and `.lua`, produce
   the contact sheet, confirm the code ordering, and add catalog tests.
2. **Python core** (done): `fen.py`, `board.py`, `geometry.py`, SVG and PDF renderers,
   the CLI, the shared vectors and pytest.
3. **LaTeX** (done): route A (snippets and `gcsnippet.sty`), route B (LuaLaTeX package),
   and the 100-diagram comparison. Both routes are kept (§9).
4. **Browser editor** (done): Pyodide running the Python package, a TypeScript UI, and
   Playwright tests (§10).

## 13. Open questions

- Should a wall be a solid black square, or the framed `special:box:none` glyph?
- The special names (§4.2) are mostly descriptive because the reference PDF doesn't give
  their fairy meanings. Rename them if there are established names. (`equihopper` and
  `jester` are established; the fonts' rotated copies of them, GC2004X 0xEB–0xEE,
  0xF3–0xF4 and GC2004Y 0x47–0x4A, are deliberately left out of the catalog.)
- Coordinates (rank and file labels) are out of scope for v1, but the catalog includes the
  label glyphs so they can be added later.
- Font redistribution rights (see §1).
