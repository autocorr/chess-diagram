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
| `data/GC2004X_.TTF` | Pieces at 45/135/225/315°, neutral pieces at 90/180/270°, special markers (hourglass vertical and horizontal, circle, star) |
| `data/GC2004Y_.TTF` | Double border and corners, 2- and 3-sided edge squares, arrows, mirrored knights at 90/180/270°, chameleon king, jester and moustache figures, rank labels 1–26 and file labels a–z in single and double styles |
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
     ┌──────────────┼───────────┐    │
     ▼              ▼           ▼    ▼
  Python pkg     Web editor    LuaLaTeX package
  (gcdiagram)   (TypeScript)   (gcdiagram.sty/.lua)
     │
     ├─► SVG  (outlines, <symbol>/<use>)
     ├─► PDF  (outlines, hand-written writer)
     └─► TeX snippet (glyph codes, for the thin .sty)

  tests/vectors.json ─► shared FEN conformance tests run by Python, Lua and JS
```

Two parts are shared by every implementation:

1. **The glyph catalog**, generated once from the TTFs. It is the only place that knows
   which font and code draw a given figure on a given shade.
2. **The FEN test vectors**, which every parser (Python, Lua and TypeScript) must pass. This
   keeps the three implementations of the grammar in agreement.

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
│   ├── __init__.py                 # public API: parse(), render_svg(), render_pdf(), render_tex()
│   ├── data/catalog.json           # generated, committed
│   ├── catalog.py                  # loads catalog, resolves (Figure, Shade) → Glyph
│   ├── fen.py                      # extended-FEN tokenizer/parser/serializer
│   ├── board.py                    # board model (cells, figures, shades)
│   ├── geometry.py                 # layout: cell rects, border segments, hole outlines, arrows
│   ├── options.py                  # RenderOptions (border style, caption, arrows, scale, …)
│   ├── render/
│   │   ├── svg.py
│   │   ├── pdf.py                  # minimal PDF 1.4 writer (paths + Flate + Helvetica caption)
│   │   └── tex.py                  # LaTeX snippet output
│   └── cli.py                      # `gcdiagram FEN -o out.svg|pdf|tex [options]`
├── latex/
│   ├── gcdiagram.sty               # LuaLaTeX package (parsing in Lua)
│   ├── gcdiagram.lua
│   ├── gcdiagram-catalog.lua       # generated
│   ├── gcsnippet.sty               # thin package for Python-generated snippets
│   └── examples/                   # test documents, 100-diagram size benchmark
├── web/                            # browser editor (TypeScript + Vite)
│   ├── src/{fen.ts, board.ts, catalog.ts, render.ts, editor/…}
│   └── public/catalog.json         # copied from src/gcdiagram/data at build
└── tests/
    ├── vectors.json                # shared FEN conformance cases
    ├── test_fen.py, test_render.py, …
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
| `flower`, `diamond`, `ring`, `circle`, `star`, `jester`, `moustache` | white, black |
| `hourglass`, `hourglass-h` (horizontal) | white, black, neutral |
| `half-circle` | neutral |
| `box`, `cross` | none |

### 4.3 JSON shape

```json
{
  "version": 1, "unitsPerEm": 2000, "cell": 2000, "baseline": 1500,
  "fonts": {"D": "GC2004D_.TTF", "X": "GC2004X_.TTF", "Y": "GC2004Y_.TTF"},
  "outlines": {"o17": "M1190 554V257L1044 405Z…"},
  "glyphs": {
    "piece:Q:white:90:plain:dark": {"font": "D", "code": 78, "outline": "o17", "bbox": [x0, y0, x1, y1]},
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
Color  = Literal["white", "black", "neutral"]
Shade  = Literal["light", "dark"]

@dataclass(frozen=True) class Piece:     kind: str; color: Color; angle: int = 0; chameleon: bool = False
@dataclass(frozen=True) class Special:   name: str; color: Color | None
Figure = Piece | Special

@dataclass(frozen=True) class Square:    figure: Figure | None = None
@dataclass(frozen=True) class Hole:      pass
@dataclass(frozen=True) class Wall:      pass
Cell   = Square | Hole | Wall

@dataclass class Board:
    width: int; height: int
    cells: list[list[Cell]]          # cells[row][col], row 0 = top
    def shade(self, row, col) -> Shade   # a1 (bottom-left) is dark; holes do not affect parity
```

The model knows nothing about rendering. `catalog.resolve(figure, shade) -> Glyph` is the
only connection between the model and the fonts.

---

## 7. Layout (`geometry.py`)

All renderers share one layout step. It works in font units (cell = 2000) and is scaled
at output time.

- **Cells:** a rectangle per `(row, col)` plus the glyph id for the figure or empty square.
- **Border:**
  - *Single style:* a line wherever a square cell meets a hole or the outside. The board
    edge and the edges of holes are handled the same way, so irregular boards come out
    right without extra code.
  - *Double style:* the outer border uses the GC2004Y double-border and corner geometry.
    Hole edges use single lines.
- **Walls:** a solid filled cell, with a configurable fill.
- **Arrows:** a list of `from-to` square pairs. Each is drawn as a vector shaft and
  arrowhead between square centres, with configurable width and opacity. Glyph markers
  from the catalog (`symbol:*`) can also be placed on squares as overlays.
- **Caption:** zero or more text lines under the board (stipulation, author, piece count).
  The piece count `(w+b)` can be computed from the board automatically.

Vector borders are drawn as filled rectangles rather than stroked lines, so they match the
glyph borders pixel for pixel and don't depend on stroke-join settings.

---

## 8. Output formats

### 8.1 SVG (`render/svg.py`)

- Each distinct glyph is drawn once in a `<symbol>` (or `<path>`) inside `<defs>`, and each
  cell is a `<use href="#gN" x y>`.
- `viewBox` is in font units with `width`/`height` in pt or px, so outline coordinates stay
  integers and nothing needs rounding.
- Optimisations: integer coordinates, relative path commands with redundant segments
  dropped, minimal whitespace, and no unused defs.
- Optional `data-square="e4"` attributes on cells, used by the web editor and handy for
  scripting.

### 8.2 PDF (`render/pdf.py`)

- A minimal PDF 1.4 writer with no dependencies: a catalog, one page, and a content stream
  compressed with Flate.
- Each distinct glyph becomes a Form XObject that is reused with `Do`, the PDF equivalent
  of SVG `<use>`.
- Captions use standard Helvetica (one of the 14 base fonts, never embedded) by default. An
  embedded text font is optional.
- The page is cropped exactly to the diagram plus margins, so the PDF can be included
  as-is in other documents.

### 8.3 TeX snippet (`render/tex.py`), LaTeX route A

- Outputs `\gcboard{…}`: one row of glyph codes per rank, each tagged with its font, e.g.
  `\gcD{\char"4E}`. Glyphs with a catalog `dx` are wrapped in compensating kerns. Walls
  are drawn as `\rule`. Hole borders and arrows are drawn with a TikZ overlay that uses
  coordinates computed in Python.
- `latex/gcsnippet.sty` loads the three fonts, sets cell width and line spacing to exactly
  one cell, and provides the caption macro.
- Works with LuaLaTeX and XeLaTeX through `fontspec`. pdfLaTeX would need Type 1
  conversion, which is out of scope.

---

## 9. LuaLaTeX package, LaTeX route B (`latex/gcdiagram.sty` + `.lua`)

```latex
\usepackage{gcdiagram}
\gcdiagram[border=double, caption={\#2 \quad (8+6)}, arrows={e2-e4, g1-f3}]
          {rnb{q180}kbnr/pppp.ppp/8/8/8/8/PPPPPPPP/{R90}NBQKBN{R270}}
```

- `gcdiagram.lua` contains the FEN parser, a port of `fen.py` that must pass
  `tests/vectors.json`, plus shade logic and glyph lookup through
  `gcdiagram-catalog.lua`.
- Lua builds the grid by printing glyph characters (`tex.sprint`) in the right font, and
  computes the border, hole and arrow segments. Those are emitted as TikZ (or `pgf` for
  speed) on top of the grid.
- Fonts are loaded with `\newfontfamily` and `Path=` pointing at the TTF directory,
  configurable with `\gcdiagramsetup{fontpath=…}`.
- Key-value options: `border`, `caption`, `arrows`, `markers`, `size` (cell size), `walls`.

### Comparing routes A and B

`latex/examples/booklet-100.tex` will be built both ways. The comparison covers final PDF
size, compile time, how easy each is to use, and whether the rendering matches. In both
routes the font subsets are embedded once per document, so most of the size saving comes
from that. The comparison also has a baseline: 100 standalone PDFs included with
`\includegraphics`.

---

## 10. Browser editor (`web/`)

- TypeScript, built with Vite, with no UI framework. It uses `catalog.json` (outlines) and a
  TypeScript port of the parser and serialiser that runs against `tests/vectors.json`.
- **Rendering:** SVG built in the DOM, with the same `<symbol>`/`<use>` layout as §8.1.
  Because geometry comes from the catalog, the editor draws exactly what the SVG export
  produces.
- **Editing:**
  - A palette of pieces and colours with a rotation selector (only angles that exist for
    that piece can be picked), plus neutral and chameleon toggles and specials.
  - Click a square to place the selected figure. Drag to move. Right-click or Delete to
    clear. Mouse wheel or R to rotate the piece under the cursor.
  - Hole and wall tools, an arrow tool (drag from one square to another), and controls to
    resize the board (add or remove ranks and files).
  - Border style and caption fields.
- **FEN field:** editing the board updates the FEN, and editing the FEN redraws the board.
  Parse errors are shown inline.
- **Export:** SVG export works in the browser. PDF export can come later, either by porting
  `pdf.py` or by calling the Python CLI.
- **State:** the URL hash stores the FEN and options, so a link reproduces a diagram.

---

## 11. Testing

- **`tests/vectors.json`** cases have the form `{fen, ok, width, height, cells}` or
  `{fen, ok: false, error}`, where `error` is a stable error code. Python (pytest), Lua
  (`texlua`) and the web build (vitest) all run the same file.
- **Catalog tests:** every key resolves, every outline exists, codes match the cmap, and
  the contact sheet is reviewed by eye once.
- **Golden SVGs:** a few representative diagrams are rendered and compared byte for byte.
  These cover a standard position, rotations, neutral and chameleon pieces, specials, an
  irregular board with holes and walls, double borders, and arrows.
- **PDF tests:** the output is checked with `qpdf --check` or `pdfinfo`, and rasterised
  with `pdftoppm` to compare against the SVG rendering.
- **LaTeX:** example documents compile in CI with `lualatex`.

---

## 12. Implementation phases

1. **Catalog** (done): write `catalog_spec.py`, build `catalog.json` and `.lua`, produce
   the contact sheet, confirm the code ordering, and add catalog tests.
2. **Python core:** `fen.py`, `board.py`, `geometry.py`, SVG and PDF renderers, the CLI,
   the shared vectors and pytest.
3. **LaTeX:** route A (snippets and `gcsnippet.sty`), route B (LuaLaTeX package), and the
   100-diagram comparison. Then decide whether to keep one route or both.
4. **Browser editor:** TypeScript parser port, renderer, editing tools and SVG export.

## 13. Open questions

- Should a wall be a solid black square, or the framed `special:box:none` glyph?
- The special names (§4.2) are descriptive because the reference PDF doesn't give their
  fairy meanings, e.g. `jester` and `moustache` for GC2004Y 0x43–0x4A. Rename them if
  there are established names.
- Coordinates (rank and file labels) are out of scope for v1, but the catalog includes the
  label glyphs so they can be added later.
- Font redistribution rights (see §1).
