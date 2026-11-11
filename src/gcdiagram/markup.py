"""Inline caption markup: <b>bold</b> and <i>italic</i>.

Tags rather than Markdown-style asterisks, because problem stipulations use '*' for set
play ("h#2*"). Only these four tags are recognised (case-insensitive) and everything
else, including a stray '<', is literal text. Styles don't carry over from one caption
line to the next, and a tag left open runs to the end of its line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TAG = re.compile(r"<(/?)([bi])>", re.IGNORECASE)


@dataclass(frozen=True)
class Run:
    """A stretch of caption text in one style."""

    text: str
    bold: bool = False
    italic: bool = False


def parse_markup(line: str) -> list[Run]:
    """Split one caption line into styled runs, merging neighbours with the same style."""
    runs: list[Run] = []
    bold = italic = False
    pos = 0
    for m in _TAG.finditer(line):
        _append(runs, Run(line[pos : m.start()], bold, italic))
        on = m.group(1) == ""
        if m.group(2).lower() == "b":
            bold = on
        else:
            italic = on
        pos = m.end()
    _append(runs, Run(line[pos:], bold, italic))
    return runs


def plain(line: str) -> str:
    """A caption line without its markup."""
    return "".join(r.text for r in parse_markup(line))


def _append(runs: list[Run], run: Run) -> None:
    if not run.text:
        return
    if runs and (runs[-1].bold, runs[-1].italic) == (run.bold, run.italic):
        runs[-1] = Run(runs[-1].text + run.text, run.bold, run.italic)
    else:
        runs.append(run)
