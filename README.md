# gcdiagram

Chess and fairy-chess diagrams from an extended FEN string, drawn with the Good Companion
(GC2004) diagram fonts by David L. Brown. Output is optimized SVG or standalone PDF, with
vector outlines and no embedded fonts. Diagrams can also be typeset directly in LaTeX
(LuaLaTeX or XeLaTeX) and edited in a local browser editor. The design is described in
[ARCHITECTURE.md](ARCHITECTURE.md).

## Usage

```sh
uv run gcdiagram "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR" -o start.svg
uv run gcdiagram "4k3/8/8/8/8/8/8/4K3" -o mate.pdf -c "#2" -n -b double
uv run gcdiagram "..2../.K3./1*4/6/.4./..2.." -b outline -o irregular.svg
uv run gcdiagram "{Q0}{=q}11" --canonical      # prints Q{=Q}11
uv run gcdiagram --list-specials
```

```python
from gcdiagram import RenderOptions, parse, render_pdf, render_svg

svg = render_svg("{Q90}7/8/8/8/8/8/8/K6k", RenderOptions(caption=["#2"], arrows=["a1-a8"]))
pdf = render_pdf(parse("8/8/8/8/8/8/8/8"), RenderOptions(square_size=18, border="double"))
```

## Extended FEN

Standard FEN board notation (`KQRBNP`/`kqrbnp`, digits for empty squares, `/` between
ranks, top rank first) works unchanged. Fields after the board are ignored. In addition:

| Syntax | Meaning |
|---|---|
| `{Q90}` `{n225}` | piece rotated clockwise by 0–315° in steps of 45 |
| `{=Q}` `{=R180}` | neutral piece (0/90/180/270°) |
| `{~B}` | chameleon (framed) piece |
| `{!N90}` | mirrored knight (90/180/270°) |
| `{@Star}` `{@star}` `{=@equihopper}` | special figure: capital = white, lower = black, `=` = neutral |
| `.` | hole: a missing square |
| `*` | wall: a blocked square |
| `12` | multi-digit empty runs, for boards up to 26×26 |

Every combination is checked against the fonts, and an unsupported one gives a clear
error.

## Options

`RenderOptions` and the CLI flags cover:

- square size in points
- border style: `single`, `double`, `outline` (follows irregular boards) or `none`
- caption lines above and below the board, with `<b>bold</b>` and `<i>italic</i>`, and
  the `(w+b)` piece count (`-C`/`--caption-above`, `-c`/`--caption`, `-n`)
- annotations: arrows, circles, crosses, squares, triangles, dots and corner labels,
  outlined in white, in black, gray, or Okabe-Ito vermilion, blue and bluish green, e.g.
  `-m circle:e4`, `-m arrow:e2-e4:vermilion` or `-m label:e4:tr:A:blue` (`annotations`
  in `RenderOptions`). A label is one printable ASCII character in a corner of a square
  (`tl`, `tr`, `bl` or `br`). The editor labels vermilion "Orange".
- translucent arrows such as `e2-e4` (`-a`; the LaTeX route B `arrows` key)
- wall style: `solid` (40% gray, outlined in black) or `box` (the fonts' framed square)
- padding and a transparent background

## LaTeX

Both routes set diagrams with the real GC fonts, so each font is embedded once per
document. A 100-diagram booklet is 60 KiB, against 1.3 MiB when 100 standalone PDFs are
included (see ARCHITECTURE.md §9). The `latex/` directory must be on both `TEXINPUTS`
and `LUAINPUTS`.

**LuaLaTeX, FEN in the source:**

```latex
\usepackage{gcdiagram}
\gcfontpath{/path/to/data/}        % unless the GC2004*.TTF fonts are installed
\gcdiagramsetup{size=18pt}
...
\gcdiagram[caption={\#2}, count, border=double, arrows={e2-e4}]{4k3/8/8/8/8/8/8/4K3}
```

The other keys are `caption above`, `wall=solid|box`, `arrow color=RRGGBB` and
`arrow opacity=0.6`. Annotations (`-m`) are only written by the Python route so far.

**LuaLaTeX or XeLaTeX, snippets written by Python:**

```sh
uv run gcdiagram "4k3/8/8/8/8/8/8/4K3" -c "#2" -n -o mate.tex
```

```latex
\usepackage{gcsnippet}
\gcfontpath{/path/to/data/}
\gcsquaresize{18pt}
...
\input{mate}
```

## Browser editor

A local editor that runs this Python package in the browser through Pyodide. It needs
Node.js 22.12 or newer; `web/.nvmrc` pins 26.

```sh
cd web
nvm use            # or any Node >= 22.12
npm install
npm run dev        # http://localhost:5173
```

Click to place the selected figure; clicking it again removes it. Drag to move,
right-click or <kbd>Del</kbd> to clear, and <kbd>R</kbd> / <kbd>Shift</kbd>+<kbd>R</kbd> to
rotate the piece under the pointer. There are also tools for holes, walls and
annotations (drag between squares for an arrow, or click for a circle, cross, square,
triangle, dot or label, in the color chosen under Annotation; a label goes in the corner
nearest the click). Captions go above and below the
board; select text and press B or I (or Ctrl+B, Ctrl+I) for bold or italic. The
FEN field and the URL stay in sync with the board, and SVG/PDF/TeX exports are
identical to the CLI's. The editor can also export a PNG at 150, 300 or 600
dpi, which the browser draws from the SVG; its caption uses the system's
Helvetica or Arial, and the CLI has no PNG output. Edits to
`src/gcdiagram/*.py` reload the page. `npm run test:e2e` runs the Playwright
tests; the first time, run `npx playwright install chromium`.

`npm run build` writes a static site to `web/dist/` (about 14 MB, mostly the Pyodide
runtime) that any web server can host. `.github/workflows/pages.yml` builds it and
publishes it on GitHub Pages on every push to `main`; to turn it on, set **Settings →
Pages → Source** to **GitHub Actions**.

## Development

```sh
uv run pytest                          # tests (LaTeX ones need texlua, lualatex, xelatex)
uv run ruff check . && uv run ty check # lint and types
uv run python tools/build_catalog.py   # rebuild the glyph catalog from data/*.TTF
uv run python tools/contact_sheet.py   # build/contact-sheet.svg: every glyph with its key
uv run python latex/examples/booklet.py  # LaTeX size/speed comparison in build/booklet
```

## Credits
Diagrams are drawn with the <b>Good Companion</b> (GC2004) chess diagram fonts
by David L. Brown for the <i>StrateGems</i> Chess problem magazine.
