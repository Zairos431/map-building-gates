"""Phase 2 map-building gates: lint a MASTER and emit a beginner path.

The Phase 1 ideation under ``ideation/`` stays the historical record.
This package does not apply a world and does not approve a queue.
"""

from phase2.beginner import beginner_spec, render_master, write_game
from phase2.derive import derive_queue
from phase2.gates import LintReport, format_report, lint_document, lint_text
from phase2.parse import parse_master

__all__ = [
    "LintReport",
    "beginner_spec",
    "derive_queue",
    "format_report",
    "lint_document",
    "lint_text",
    "parse_master",
    "render_master",
    "write_game",
]
