#!/usr/bin/env python3
"""Generate a beginner path, then gate-lint that directory.

One command for the Phase 2 check. It runs tools/beginner_path.py, then
tools/gate_lint.py on the directory that was just written. Exit 0 only when
both steps pass. The queue stays unapproved. Nothing is applied to a live world.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEGINNER_PATH = ROOT / "tools" / "beginner_path.py"
GATE_LINT = ROOT / "tools" / "gate_lint.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a beginner path, then gate-lint that directory. "
            "Exits non-zero if either step fails."
        )
    )
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
    out = _out_dir(args.date, args.out)

    gen_cmd = [
        sys.executable,
        str(BEGINNER_PATH),
        "--date",
        args.date,
        "--out",
        str(out),
    ]
    if args.force:
        gen_cmd.append("--force")
    gen = subprocess.run(gen_cmd)
    master = out / "MASTER_GAME.md"
    queue = out / "BUILD_QUEUE.json"
    if gen.returncode != 0 or not master.is_file() or not queue.is_file():
        _summary(beginner_ok=False, lint_ok=False, lint_ran=False)
        return gen.returncode if gen.returncode else 1

    lint = subprocess.run([sys.executable, str(GATE_LINT), str(out)])
    lint_ok = lint.returncode == 0
    _summary(beginner_ok=True, lint_ok=lint_ok, lint_ran=True)
    if not lint_ok:
        return lint.returncode if lint.returncode else 1
    return 0


def _out_dir(day: str, out: str | None) -> Path:
    path = Path(out) if out else ROOT / "games" / f"beginner_path_{day}"
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _summary(*, beginner_ok: bool, lint_ok: bool, lint_ran: bool) -> None:
    sys.stdout.write(f"beginner-path: {'PASS' if beginner_ok else 'FAIL'}\n")
    if not lint_ran:
        sys.stdout.write("gate-lint: FAIL (not run)\n")
    else:
        sys.stdout.write(f"gate-lint: {'PASS' if lint_ok else 'FAIL'}\n")
    sys.stdout.write(f"pipeline: {'PASS' if beginner_ok and lint_ok else 'FAIL'}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
