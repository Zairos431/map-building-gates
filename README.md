# Map Building Gates

**Early / exploratory.** This repo is the home for a small design idea: building game maps with **gates** so an AI (or a person) can fill in a beginner path that actually reaches a playable ending—without requiring every creative detail to be perfect first.

Phase 1 ideation lives in [`ideation/`](ideation/MAP_BUILDING_GATES_PHASE1.md) and is left as the historical record. Phase 2, started after Doug’s go on 2026-11-06, adds a **gate-lint** and a **beginner-path generator** in this repo. The full planner→builder loop that proved `demo_corridor` still lives on the pipeline box. Phase 3 adds the builder loop, world.json materialize, Doug's APPROVE step and a hard-gated live bunker apply. Live writes stay dry-run by default and need Doug's explicit approval each time.

## The idea in plain language

When you ask an AI to “make a map,” it can invent numbers that break the game: rooms that don’t connect, doors that don’t line up, a start with nowhere to go, or a “win” that can never happen.

So we split map decisions into two kinds of **gates**:

### Deterministic gates (hard numbers)

These are **required**. They have minimum viable values—size, exits, start point, goal, connectivity, at least one enemy for the current Home FPS rules, and so on. If any of these are missing or nonsense, the map fails the beginner test. The AI is not allowed to “get creative” below those floors.

### Generalistic gates (open / flavorful)

These are **open to interpretation**: mood, color palette, room names, optional side rooms, whether to drop a health pack, and similar. The AI fills them with **safe but flavorful defaults** and **flags** which ones a human might want to tweak (`leave`, `optional`, `suggested`, or `blocked`).

Creative fill must never break a deterministic gate.

## What “done” means for a beginner path

**Completion** is not “every gate filled perfectly.”

A beginner path **passes** when a first-time player can move from **start to finish** in a coherent world: no dead-end-only route, no nonsense required values, and a real end state (for our Home FPS target: reach the goal and clear the required grunts). Flavor can still be rough.

The shipped check for that is `tools/gate_lint.py`. It recomputes the D-* gates from the master’s numbers. The Status column in `## Gates` is only a claim.

## What’s in this repo

| Path | What |
| --- | --- |
| [`ideation/MAP_BUILDING_GATES_PHASE1.md`](ideation/MAP_BUILDING_GATES_PHASE1.md) | Phase 1 gate lists, MV numbers, completion definition (historical; do not rewrite) |
| [`ideation/DECISION_LOG.md`](ideation/DECISION_LOG.md) | Append-only log. Phase 2 go is at the bottom. |
| [`ideation/README.md`](ideation/README.md) | Rules for keeping ideation append-only |
| [`phase2/`](phase2/) | Parser, deterministic lint, queue derive, beginner-path fill |
| [`tools/gate_lint.py`](tools/gate_lint.py) | CLI: pass/fail the D-* gates and start→goal connectivity |
| [`tools/beginner_path.py`](tools/beginner_path.py) | CLI: write a fresh 2-room beginner path |
| [`tools/beginner_path_pipeline.py`](tools/beginner_path_pipeline.py) | CLI: generate a beginner path, then gate-lint that directory |
| [`templates/MASTER_GAME.md.template`](templates/MASTER_GAME.md.template) | MASTER shape, including `## Gates` |
| [`templates/BUILD_QUEUE.json.template`](templates/BUILD_QUEUE.json.template) | Queue shape. New queues stay `approved: false`. |
| [`games/beginner_path_20261106/`](games/beginner_path_20261106/) | Known-good fresh demo emitted by the generator |
| [`phase3/`](phase3/) | Builder loop + world.json materialize + gated live apply |
| [`tools/builder_loop.py`](tools/builder_loop.py) | CLI: lint, dry-run, approve, build steps, materialize, apply-world |

Python 3 and the standard library only. No install step.

## Run Phase 2

From the repo root, generate a beginner path and gate-lint it in one command:

```bash
python3 tools/beginner_path_pipeline.py --date 20261106 --out /tmp/beginner_path_20261106
```

`beginner_path_pipeline.py` runs `beginner_path.py` into `--out`, then runs `gate_lint.py` on that directory. The generator prints its own gate-lint report; the pipeline runs gate-lint again on the written files. The process ends with `beginner-path: PASS` or `FAIL`, `gate-lint: PASS` or `FAIL`, and `pipeline: PASS` or `FAIL`. Exit 0 only when both steps pass. If generation fails, gate-lint is not run and the process still exits non-zero. Omit `--out` to write `games/beginner_path_<today>/`. Pass `--force` to overwrite an existing master. The pipeline does not approve the queue, write `world.json`, or apply a live bunker.

The same two steps by hand:

```bash
python3 tools/beginner_path.py --date 20261106 --out games/beginner_path_20261106
python3 tools/gate_lint.py games/beginner_path_20261106
```

`beginner_path.py` writes `MASTER_GAME.md` and a derived `BUILD_QUEUE.json` with `approved: false`. It refuses to overwrite an existing master unless you pass `--force`. Omit `--out` to write `games/beginner_path_<today>/`.

`gate_lint.py` takes a master file or a game directory. Exit 0 is PASS. Exit 1 is a failed gate or a hole in the master (missing `## Gates`, a door that does not meet its neighbor, no path from start to goal, a room that is too small, a grunt outside its room, and the other D-* rules). Exit 2 means the file was not found.

The generator fills the Phase 1 beginner recipe:

| Choice | Value |
| --- | --- |
| Rooms | 2, collinear along −Z, shared edge at z = −8 |
| Sizes | start 6×8, goal 8×8, height 3, `floor_y` 0 |
| Fight | 1 grunt in the goal room |
| Pickup | 1 health pack in the start room |
| Map | `fresh_demo`, mode `progression`, win `all_grunts_down` |
| Flavor | safe defaults with `human_touch` flags |

Coordinates match Home FPS: meters, +Y up, the map grows toward −Z, x = 0 is the center line. Z doors are 3.0 m wide. X doors are 2.2 m wide. A shared edge may touch. Room interiors may not overlap.

The known-good master is already in `games/beginner_path_20261106/`. Lint it directly if you do not want to regenerate.

Tests:

```bash
python3 -m unittest discover -s tests -v
```

## Run Phase 3

```bash
python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --lint
python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --dry-run --all
python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --materialize
```

The builder re-reads `MASTER_GAME.md` and `BUILD_QUEUE.json` every step, derives
the queue from the master, and refuses non-dry runs until the queue is approved
with a pinned master hash (`--approve` needs `CONFIRM_APPROVE=YES`, only after
Doug says APPROVE). `--materialize` writes a staged `runs/world.staged.json`;
nothing touches the live bunker by default. Live apply requires `--apply-world`
+ `--allow-apply` + `CONFIRM_APPLY=YES` + approved pinned queue + gate-lint PASS
+ the real live world.json path, and leaves a timestamped backup and receipt
before the atomic replace. See `phase3/README.md`.

## Status

- **Phase 1 (ideation):** complete. Files under `ideation/` stay as written, except the append-only decision log.
- **Phase 2 (this repo):** complete. Shipped: gate-lint, beginner-path generator, the generate-then-lint pipeline, MASTER/queue templates, one fresh demo game.
- **Phase 3 (this repo):** shipped 2026-11-06. Builder loop, world.json materialize (staged), Doug’s APPROVE step, and a live bunker apply gated behind `--allow-apply` + `CONFIRM_APPLY=YES` + approved pinned master hash + gate-lint PASS. Dry-run by default; no live apply has been run. Not shipped: anything still out of scope below.
- **Queue:** every generated queue is `approved: false`. gate-lint does not approve it.

## Out of scope

Stairs, elevator, garden, new enemy or item kinds, new weapons, multi-floor, FFA, overnight loops, and the World/Game Maker UI merge. Live bunker writes exist as of Phase 3 but are gated: no `--allow-apply` means no apply path runs at all, and even with it a live write additionally needs `CONFIRM_APPLY=YES` and an approved queue pinned to the current master hash. Every other command is dry-run/staged only. A `floor_y` of 3.2 is a schema floor in the full game and fails the beginner-path lint, because that floor needs stairs or an elevator.

## License / credit

Darkwaters Studio / Doug — exploratory design notes, 2026.
