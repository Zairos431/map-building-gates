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
