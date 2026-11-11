"""LaTeX integration: the Lua port (route B) against Python, and compiling both routes.

Needs texlua, lualatex and xelatex; tests are skipped without them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from cases import CASES

from gcdiagram.options import RenderOptions
from gcdiagram.render.tex import num, render_tex, tex_escape, tex_parts

ROOT = Path(__file__).resolve().parent.parent
LATEX = ROOT / "latex"
FONTS = ROOT / "data"


def tool(name: str) -> pytest.MarkDecorator:
    return pytest.mark.skipif(shutil.which(name) is None, reason=f"needs {name}")


def tex_env() -> dict[str, str]:
    env = dict(os.environ)
    env["TEXINPUTS"] = f"{LATEX}//:"
    env["LUAINPUTS"] = f"{LATEX}//:"
    return env


def to_lua(value: object) -> str:
    """Serialize JSON-like data as a Lua table constructor."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)  # JSON string escapes are valid Lua for this data
    if isinstance(value, (list, tuple)):
        return "{" + ",".join(to_lua(v) for v in value) + "}"
    if isinstance(value, dict):
        return "{" + ",".join(f"[{to_lua(k)}]={to_lua(v)}" for k, v in value.items()) + "}"
    raise TypeError(value)


def texlua(script: str, data: object, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    data_file = tmp_path / "data.lua"
    data_file.write_text("return " + to_lua(data))
    return subprocess.run(
        ["texlua", str(ROOT / "tests" / "lua" / script), str(data_file)],
        capture_output=True,
        text=True,
        env={**tex_env(), "LUA_PATH": f"{LATEX}/?.lua;;"},
    )


# --- Pure Python ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("units", "text"),
    [(0, "0"), (100, ".05"), (-233, "-.1165"), (2000, "1"), (16200, "8.1"), (0.004, "0")],
)
def test_num(units: float, text: str) -> None:
    assert num(units) == text


def test_escape() -> None:
    assert tex_escape("#2 & 50% {x}_y ~^\\") == (
        r"\#2 \& 50\% \{x\}\_y \textasciitilde{}\textasciicircum{}\textbackslash{}"
    )


def test_snippet_shape() -> None:
    out = render_tex("K", RenderOptions(caption=["#2", "line two"], piece_count=True))
    assert out.startswith(r"\gcbox{1.1}{1.1}{%" + "\n")
    assert out.endswith(r"}{\#2\\line two}{(1+0)}%" + "\n")
    assert r"\gcrank{.05}{.3}{\gcD{1}}%" in out  # white king on dark a1 is 0x31


def test_font_fixup_is_kerned() -> None:
    # D 0x37 (black king, 90 degrees, dark square) is drawn 233 units right of its cell.
    assert r"\gcfix{-.1165}{7}" in tex_parts("2/{k90}1")[2]  # a1 is dark
    assert r"\gcfix" not in tex_parts("{k90}1/2")[2]  # a2 is light: glyph 0x36 is fine


# --- Lua port ---------------------------------------------------------------------------


@tool("texlua")
def test_lua_parser_passes_shared_vectors(tmp_path: Path) -> None:
    vectors = json.loads((ROOT / "tests" / "vectors.json").read_text())
    result = texlua("check_vectors.lua", vectors, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def lua_opts(opts: RenderOptions) -> dict:
    return {
        "border": opts.border,
        "wall": opts.wall,
        "count": opts.piece_count,
        "arrows": [a if isinstance(a, str) else "-".join(a) for a in opts.arrows],
    }


@tool("texlua")
def test_lua_emits_same_tex_as_python(tmp_path: Path) -> None:
    cases = [{"name": n, "fen": fen, "opts": lua_opts(o)} for n, (fen, o) in CASES.items()]
    result = texlua("emit.lua", cases, tmp_path)
    assert result.returncode == 0, result.stderr
    lua = {}
    for chunk in result.stdout.split("==")[1:]:
        name, w, h, count, *lines = chunk.rstrip("\n").split("\n")
        lua[name] = (w, h, "\n".join(lines), count)
    for name, (fen, opts) in CASES.items():
        w, h, body, count = tex_parts(fen, opts)
        python = (w, h, body.replace("%\n", "\n").removesuffix("%"), count)
        assert lua[name] == python, name


# --- Compiling --------------------------------------------------------------------------

PREAMBLE = rf"""\documentclass{{article}}
\usepackage{{%s}}
\gcfontpath{{{FONTS}/}}
\pagestyle{{empty}}
\begin{{document}}
"""


def compile_tex(engine: str, source: str, tmp_path: Path, name: str = "doc") -> Path:
    (tmp_path / f"{name}.tex").write_text(source)
    result = subprocess.run(
        [engine, "-interaction=nonstopmode", "-halt-on-error", f"{name}.tex"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=tex_env(),
    )
    log = (tmp_path / f"{name}.log").read_text(errors="replace")
    errors = re.findall(r"^!.*$", log, re.M)
    assert result.returncode == 0 and not errors, "\n".join(errors) or result.stdout[-2000:]
    assert "Missing character" not in log
    return tmp_path / f"{name}.pdf"


def route_a_source() -> str:
    body = "\n\n".join(
        rf"{{\gcsquaresize{{{opts.square_size}pt}}" + render_tex(fen, opts) + "}"
        for fen, opts in CASES.values()
    )
    return PREAMBLE % "gcsnippet" + body + "\n\\end{document}\n"


def route_b_source() -> str:
    def keys(opts: RenderOptions) -> str:
        parts = [f"border={opts.border}", f"wall={opts.wall}"]
        if opts.caption:
            parts.append("caption={" + r"\\".join(tex_escape(c) for c in opts.caption) + "}")
        if opts.piece_count:
            parts.append("count")
        if opts.arrows:
            parts.append("arrows={" + ",".join(str(a) for a in opts.arrows) + "}")
        return ",".join(parts)

    body = "\n\n".join(
        rf"{{\gcsquaresize{{{opts.square_size}pt}}\gcdiagram[{keys(opts)}]{{{fen}}}}}%"
        for fen, opts in CASES.values()
    )
    return PREAMBLE % "gcdiagram" + body + "\n\\end{document}\n"


@tool("lualatex")
def test_route_a_compiles_with_lualatex(tmp_path: Path) -> None:
    pdf = compile_tex("lualatex", route_a_source(), tmp_path)
    fonts = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True).stdout
    assert fonts.count("GC2004") == 3, "each GC font embedded exactly once"


@tool("xelatex")
def test_route_a_compiles_with_xelatex(tmp_path: Path) -> None:
    compile_tex("xelatex", route_a_source(), tmp_path)


@tool("lualatex")
@tool("pdftoppm")
@tool("compare")
def test_route_b_draws_the_same_as_route_a(tmp_path: Path) -> None:
    pdf_a = compile_tex("lualatex", route_a_source(), tmp_path, "a")
    pdf_b = compile_tex("lualatex", route_b_source(), tmp_path, "b")
    for pdf in (pdf_a, pdf_b):
        subprocess.run(
            ["pdftoppm", "-png", "-r", "100", "-singlefile", pdf.name, pdf.stem],
            cwd=tmp_path,
            check=True,
        )
    result = subprocess.run(
        ["compare", "-metric", "AE", "a.png", "b.png", "null:"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.stderr.strip() == "0", f"{result.stderr} pixels differ"


@tool("lualatex")
def test_captions_above_markup_and_annotations_compile(tmp_path: Path) -> None:
    opts = RenderOptions(
        caption_above=["<i>J. Smith</i>", "The Problemist 2024"],
        caption=["<b>#2</b> [set play]"],
        piece_count=True,
        annotations=[
            "arrow:e2-e4",
            "circle:d1:vermilion",
            "cross:c8:blue",
            "square:a1:gray",
            "triangle:h8",
            "circle:e8:green",
        ],
    )
    route_a = render_tex("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR", opts)
    compile_tex("lualatex", PREAMBLE % "gcsnippet" + route_a + "\n\\end{document}\n", tmp_path, "a")
    route_b = r"\gcdiagram[caption above={\textit{J. Smith}}, caption={\#2}, count]{8/8}"
    compile_tex("lualatex", PREAMBLE % "gcdiagram" + route_b + "\n\\end{document}\n", tmp_path, "b")


@tool("lualatex")
def test_route_b_reports_fen_errors(tmp_path: Path) -> None:
    source = PREAMBLE % "gcdiagram" + "\\gcdiagram{8/7}\n\\end{document}\n"
    with pytest.raises(AssertionError, match="rank 2 from the top has 7 squares"):
        compile_tex("lualatex", source, tmp_path)
