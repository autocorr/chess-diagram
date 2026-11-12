"""Helpers shared by the tests."""

from __future__ import annotations

import re
import zlib


def pdf_content(pdf: bytes) -> str:
    """A one-page PDF's content stream (the last stream written)."""
    *_, last = re.findall(rb">>stream\n(.*?)\nendstream", pdf, re.S)
    return zlib.decompress(last).decode("latin-1")
