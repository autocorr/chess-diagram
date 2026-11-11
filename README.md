# gcdiagram

Chess and fairy-chess diagrams from an extended FEN string, drawn with the Good Companion
(GC2004) diagram fonts by David L. Brown. Output is optimised SVG or standalone PDF, with
vector outlines and no embedded fonts. LaTeX and browser-editor integrations are planned
(see [ARCHITECTURE.md](ARCHITECTURE.md)).

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
| `{@Star}` `{@star}` `{=@hourglass}` | special figure: capital = white, lower = black, `=` = neutral |
| `.` | hole: a missing square |
| `*` | wall: a blocked square |
| `12` | multi-digit empty runs, for boards up to 26×26 |

Every combination is checked against the fonts, and an unsupported one gives a clear
error.

## Options

`RenderOptions` and the CLI flags cover:

- square size in points
- border style: `single`, `double`, `outline` (follows irregular boards) or `none`
- caption lines and the `(w+b)` piece count
- arrows such as `e2-e4`
- wall style: `solid` or `box`
- padding and a transparent background

## Development

```sh
uv run pytest                          # tests
uv run ruff check . && uv run ty check # lint and types
uv run python tools/build_catalog.py   # rebuild the glyph catalog from data/*.TTF
uv run python tools/contact_sheet.py   # build/contact-sheet.svg: every glyph with its key
```

The GC fonts are described as "used exclusively for diagrams on www.StrateGems.org".
Check redistribution rights before publishing the fonts or outlines derived from them.
