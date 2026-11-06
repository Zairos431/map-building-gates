#!/usr/bin/env python3
"""Check deterministic D-* gates and start-to-goal connectivity on a MASTER.

Exit 0 when every deterministic gate passes and the start room reaches the goal.
Exit 1 when a gate fails or the master has a hole. Exit 2 when the path is missing
or the arguments are wrong.

Does not approve a queue and does not write a world.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase2.gates import format_report, lint_text  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint deterministic map gates and start-to-goal door connectivity."
    )
    parser.add_argument(
        "master",
        help="Path to MASTER_GAME.md, or a game directory that contains one",
    )
    args = parser.parse_args(argv)
    path = Path(args.master)
    if path.is_dir():
        path = path / "MASTER_GAME.md"
    if not path.is_file():
        sys.stdout.write(f"gate-lint: FAIL {path}\n  HOLE file not found\n")
        return 2
    text = path.read_text(encoding="utf-8")
    report = lint_text(text, path=str(path))
    sys.stdout.write(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
