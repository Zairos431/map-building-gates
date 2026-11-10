# Map-building gates — Phase 1 decision log

**Status:** Phase 1 COMPLETE (2026-11-05) · Implementation NOT started  
**Authority:** Doug voice call 2026-11-05 (Anthony - Coordinator II capturing)  
**Constraint:** Append only. Never erase. Phase 2 must not override this file.

---

## 2026-11-05 — Kickoff decisions

1. **Two phases, strict order.** Phase 1 = ideation complete; Phase 2 = implement on `/workspace/game_pipeline/`. No Phase 2 until Doug says go.
2. **Nothing lost.** Every ideation decision is written here + in `MAP_BUILDING_GATES_PHASE1.md`. Implementation must not erase or override the ideation record.
3. **Two gate classes.**
   - **Deterministic gates** — hard required numbers; minimum viable values fixed so a beginner path cannot be nonsense.
   - **Generalistic gates** — open to creative interpretation; AI fills safe but flavorful defaults and **flags** which ones a human may want to touch.
4. **Completion definition (beginner path test).** Success = a playable, coherent end state: a first-time player can move from start to finish without a dead end or nonsense value. **Not** every gate filled perfectly.
5. **Target stack.** Ideation assumes Home FPS `WORLD_SCHEMA` / `world.json` + existing planner→builder pipeline (MASTER_GAME.md → BUILD_QUEUE → builder_loop). Fresh demo maps preferred over mutating live `small_bunker` unless Doug says otherwise.
6. **Win rule stays home_fps.** All grunts down = win; at least one grunt required for a valid map (world_agent).
7. **Beginner path shape.** Linear progression: Start room → optional breather/loot → Goal room. Minimum room count for Phase 2 test: **2** (matches demo_corridor lesson). Optional 3rd room is generalistic, not required for completion.
8. **Coordinate frame locked.** Meters; +Y up; map grows toward −Z; x = 0 center line; `floor_y` ∈ {0.0, 3.2} only for v1 beginner path (single floor = 0.0).
9. **Deterministic fields that must have numeric MV floors.** Map/room size, exit count and alignment, start point, goal definition, grunt count ≥ 1, door sides that form a continuous path, non-overlapping rooms, pickups inside room bounds.
10. **Generalistic fields AI may invent.** Palette colors, look flavors, room names/ids (snake_case), flavor purpose text, enemy/item placement within safe insets, optional extra rooms/branches, mood/vision copy — all flagged `human_touch: suggested|optional|leave`.
11. **Gate validation layers.** (a) Schema valid (WORLD_SCHEMA / world_agent checker), (b) Path coherent (BFS/DFS from start to goal through doors), (c) Playable bounds (sizes ≥ MV, spawns inset from walls), (d) Beginner completion (start→goal reachable; ≥1 grunt on path or in goal room). Perfect aesthetic fill is out of scope for the completion test.
12. **AI fill policy.** Deterministic gates: refuse to invent below MV; if missing, fail ideation/fill with explicit hole. Generalistic gates: fill defaults, write `flags[]` listing human-touch candidates; never silently promote a generalistic field into a hard requirement.
13. **Phase 2 readiness criteria (not started).** When Doug says go: extend planner prompt + MASTER template with gate sections; add a gate-lint (deterministic + path check) before APPROVE; beginner-path generator throws numbers into gates → emits MASTER + queue → dry-run builder. Ideation files stay intact.
14. **Live bunker safety.** Phase 2 beginner test uses a **new** `games/<id>/` dir and `world.<id>.json` (or staged ops), not `--allow-apply` on live bunker unless Doug explicitly approves apply.
15. **Relation to demo_corridor.** demo_corridor already proved store→reopen→edit persistence. Phase 2 beginner path should reuse that pipeline pattern; it is not required to keep demo_corridor’s exact rooms—only the gate rules above.
16. **Out of Phase 1 / Phase 2 beginner path.** Stairs, elevator, garden, new enemy/item kinds, new weapons, multi-floor, FFA mode, World/Game Maker UI merge (A/B/C still Doug’s pick).

## Amendments
_(none yet — append below with date)_

## 2026-11-06 — Phase 2 go (Doug)

**Authority:** Doug (owner), voice, 2026-11-06. Explicit go for Phase 2.
**Capture:** implementation in this repo. Phase 1 decisions above are unchanged. This entry only records the go and the scope that landed here.

1. **Go.** Doug said go. Phase 2 is no longer waiting. Ideation files stay the historical record: this log is append-only, and `MAP_BUILDING_GATES_PHASE1.md` was not rewritten.
2. **Where it lives.** Phase 2 in this repo is `phase2/`, `tools/gate_lint.py`, `tools/beginner_path.py`, `templates/`, and `games/beginner_path_20261106/`. It does not claim the full planner→builder loop from `/workspace/game_pipeline/`. A thin derive step writes `BUILD_QUEUE.json` from the master’s Build Steps.
3. **gate-lint.** Checks the deterministic D-* gates and start→goal connectivity (door or open sides that meet on a shared edge, BFS from start to goal). It recomputes from room numbers, spawns, palette, and frontmatter. The Status column in `## Gates` is not trusted. A broken door or a disconnected goal fails the process with the gate id in the report.
4. **Beginner-path generator.** Emits `games/beginner_path_<YYYYMMDD>/MASTER_GAME.md` plus a derived queue with `approved: false`. Fill recipe, as locked in Phase 1: 2 rooms only; collinear along −Z with a shared-edge door; sizes 6×8 then 8×8; 1 grunt in the goal room; 1 health pack in the start room; single `floor_y` 0; `fresh_demo`; mode progression. Soft and flavor fields get safe defaults and `human_touch` flags (`leave`, `optional`, `suggested`).
5. **Safety.** Fresh demo map only. No `--allow-apply`. No live `small_bunker` / bunker world writes. `target_map` must be `fresh_demo` or D-SAFE-01 fails.
6. **Still out of scope for this go.** Stairs, elevator, garden, new enemy or item kinds, new weapons, multi-floor, FFA, overnight loops, World/Game Maker UI merge, the builder loop, world.json materialize, and Doug’s APPROVE step. `floor_y` 3.2 stays out of the beginner path because it needs stairs or an elevator.

## 2026-11-06 — Phase 3 go (Doug)

**Authority:** Doug (owner), via Anthony - Coordinator II, 2026-11-06. Explicit go for Phase 3.
**Capture:** `phase3/`, `tools/builder_loop.py`, `tests/test_phase3.py`. Ideation files above unchanged; this entry is appended only.

1. **Go.** Doug said go on Phase 3, built on Citadel. Phase 1 and Phase 2 records are unchanged.
2. **Builder loop.** Ported from the proven `/workspace/game_pipeline/builder/builder_loop.py` pattern rather than writing a parallel system, and rewired to this repo's Phase 2 gate-lint. Re-reads MASTER + BUILD_QUEUE every step; queue derives from the master; non-dry runs need an approved queue whose pinned master hash still matches. Doug's APPROVE step needs `CONFIRM_APPROVE=YES`.
3. **world.json materialize.** Rooms, palette, grunts, health packs only (Phase 1 scope). Default output is a staged `runs/world.staged.json`, never the live bunker.
4. **Live bunker apply.** Now in scope but hard-gated: `--apply-world` + `--allow-apply` + `CONFIRM_APPLY=YES` + approved queue pinned to the current master hash + gate-lint PASS + the real live path `home_first_person_shooter\game\world.json`. Backup + receipt before an atomic replace. No live apply was run during the build; each live apply still needs Doug's explicit approval.
5. **Still out of scope.** Stairs, elevator, garden, new enemy or item kinds, new weapons, multi-floor, FFA, overnight loops, World/Game Maker UI merge.
