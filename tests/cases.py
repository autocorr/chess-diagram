"""Representative diagrams for the renderer tests, loaded from cases.json.

cases.json is shared with the TypeScript tests (web/), which must reproduce the golden
SVG files in tests/golden/ exactly.
"""

from __future__ import annotations

import json
from pathlib import Path

from gcdiagram.options import RenderOptions

_DATA = json.loads((Path(__file__).parent / "cases.json").read_text())

CASES: dict[str, tuple[str, RenderOptions]] = {
    name: (case["fen"], RenderOptions(**case["options"])) for name, case in _DATA.items()
}
