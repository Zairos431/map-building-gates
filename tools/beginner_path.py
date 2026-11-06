#!/usr/bin/env python3
"""Write a fresh 2-room beginner path: MASTER_GAME.md and an unapproved queue.

The fill is the Phase 1 recipe (6x8 then 8x8, collinear on -Z, one grunt in the
goal, one health pack in the start, floor_y 0, fresh_demo, progression).
The queue is derived with approved=false. Nothing is applied to a live world.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase2.beginner import write_game  # noqa: E402
from phase2.gates import format_report, lint_text  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a fresh-demo beginner path.")
    parser.add_argument(
        "--date",
        default=date.today().strftime("%Y%m%d"),
        help="YYYYMMDD used in beginner_path_<date> (default: today)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Game directory to write (default: games/beginner_path_<date> under this repo)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite MASTER_GAME.md and BUILD_QUEUE.json if they already exist",
    )
    args = parser.parse_args(argv)
    if len(args.date) != 8 or not args.date.isdigit():
        sys.stdout.write(f"beginner-path: date must be YYYYMMDD, got {args.date!r}\n")
        return 2
    out = Path(args.out) if args.out else ROOT / "games" / f"beginner_path_{args.date}"
    if not out.is_absolute():
        out = Path.cwd() / out
    try:
        master_path, queue_path = write_game(out, args.date, force=args.force)
    except FileExistsError as exc:
        sys.stdout.write(f"beginner-path: {exc}\n")
        return 2
    except (RuntimeError, ValueError) as exc:
        sys.stdout.write(str(exc))
        if not str(exc).endswith("\n"):
            sys.stdout.write("\n")
        return 1
    sys.stdout.write(f"wrote {master_path}\n")
    sys.stdout.write(f"wrote {queue_path}\n")
    sys.stdout.write("approved: false\n")
    report = lint_text(master_path.read_text(encoding="utf-8"), path=str(master_path))
    sys.stdout.write(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
