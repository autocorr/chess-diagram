from __future__ import annotations

from pathlib import Path

import pytest

from gcdiagram.cli import main


def test_svg_to_stdout(capsysbinary: pytest.CaptureFixture[bytes]) -> None:
    assert main(["K"]) == 0
    assert capsysbinary.readouterr().out.startswith(b"<svg ")


def test_pdf_file_with_options(tmp_path: Path) -> None:
    out = tmp_path / "d.pdf"
    args = ["4k3/8/8/8/8/8/8/4K3", "-o", str(out), "-c", "#2", "-n", "-a", "e1-e8", "-b", "double"]
    assert main(args) == 0
    assert out.read_bytes().startswith(b"%PDF-1.4")


def test_format_flag_overrides_suffix(tmp_path: Path) -> None:
    out = tmp_path / "d.bin"
    assert main(["K", "-o", str(out), "-f", "svg"]) == 0
    assert out.read_text().startswith("<svg ")


def test_canonical(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["{Q0}{=q}11 w - -", "--canonical"]) == 0
    assert capsys.readouterr().out == "Q{=Q}11\n"


def test_list_specials(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--list-specials"]) == 0
    assert "equihopper   black, neutral, white" in capsys.readouterr().out


def test_bad_fen_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["{Q30}"]) == 2
    assert "angle" in capsys.readouterr().err


def test_bad_arrow_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["8/8", "-a", "a1-a5"]) == 2
    assert "off the board" in capsys.readouterr().err


def test_unknown_suffix(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["K", "-o", str(tmp_path / "d.png")])


def test_api_accepts_fen_strings() -> None:
    from gcdiagram import RenderOptions, render_pdf, render_svg

    assert render_svg("K").startswith("<svg ")
    assert render_pdf("K", RenderOptions(square_size=10)).startswith(b"%PDF")


def test_tex_output(tmp_path: Path) -> None:
    out = tmp_path / "d.tex"
    assert main(["K", "-o", str(out), "-c", "#2"]) == 0
    assert out.read_text().startswith(r"\gcbox{")


def test_bad_square_size_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["K", "-s", "0"]) == 2
    assert "square_size must be positive" in capsys.readouterr().err
