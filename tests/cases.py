"""Representative diagrams used by the renderer tests (golden files are named after keys)."""

from __future__ import annotations

from gcdiagram.options import RenderOptions

CASES: dict[str, tuple[str, RenderOptions]] = {
    "standard": (
        "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR",
        RenderOptions(caption=["#1"], piece_count=True),
    ),
    "fairy": (
        "{Q90}{q135}{=R}{~b}{!N90}{@Star}{@ring}{=@hourglass}/"
        "{K45}{k225}{=N180}{~P}{!n270}{@box}{@cross}{@half-circle}/8/8",
        RenderOptions(border="double", arrows=["a1-h4", "c2-f4"]),
    ),
    "holes": ("..2../.K3./1*4/6/.4./..2..", RenderOptions(caption=["Irregular board"])),
    "outline": ("..2../.K3./1*4/6/.4./..2..", RenderOptions(border="outline", wall="box")),
    "large": ("10k1/12/12/12/12/12/12/12/12/12/1K10", RenderOptions(square_size=12)),
}
