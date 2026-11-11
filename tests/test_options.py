from __future__ import annotations

from typing import Any

import pytest

from gcdiagram.options import RenderOptions


@pytest.mark.parametrize(
    "kwargs",
    [
        {"border": "triple"},
        {"wall": "brick"},
        {"square_size": 0},
        {"square_size": -5},
        {"caption_size": 0},
        {"padding": -1},
        {"arrow_opacity": 1.5},
        {"arrow_opacity": float("nan")},
    ],
)
def test_bad_options_are_rejected(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        RenderOptions(**kwargs)


def test_caption_must_not_be_a_bare_string() -> None:
    with pytest.raises(TypeError):
        RenderOptions(caption="#2")  # a str is a Sequence[str], so only a runtime check helps
