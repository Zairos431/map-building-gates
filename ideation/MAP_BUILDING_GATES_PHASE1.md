# Map-building architecture — Phase 1 Ideation (COMPLETE)

**Phase status:** COMPLETE — 2026-11-05  
**Phase 2:** NOT STARTED — wait for Doug’s go  
**Decision log:** `./DECISION_LOG.md` (append-only)  
**Do not overwrite this file.** Amendments go in a new `## Amendment YYYY-MM-DD` section at the bottom and a matching DECISION_LOG entry.

---

## 1. Purpose

Define the **gate architecture** for AI-assisted map building on top of the existing planner→builder pipeline (`/workspace/game_pipeline/`), so a **beginner path** can be filled with numbers and reach a **playable, coherent end state** without requiring every creative field to be perfect.

---

## 2. Completion definition (beginner path test)

**PASS when all of the following are true:**

1. **Start exists** — a designated start room (and start point) the player can spawn into.
2. **Goal exists** — a designated goal room / win condition the player can reach.
3. **Path connected** — there is at least one door-aligned walkable path from start → goal with **no dead-end trap** that is the only forward route (branches that are dead ends are OK if an alternate path to goal remains).
4. **No nonsense values** — every **deterministic** gate meets its minimum viable (MV) numeric/schema rules (sizes, exits, floors, ids, ≥1 grunt, spawns inside rooms).
5. **Playable end state** — a first-time player can move start → finish and trigger the home_fps win rule (all grunts down), with at least one grunt placed on the beginner path (prefer goal room).
6. **Generalistic gates may be imperfect** — flavor, palette, optional rooms, and “nice” placement do **not** have to be optimal; AI defaults + human-touch flags are enough.

**FAIL examples:** missing start/goal; door that doesn’t meet a neighbor; room smaller than MV; zero grunts; spawn outside room; overlapping rooms; only path is a dead end; values outside WORLD_SCHEMA (e.g. floor_y not 0 or 3.2).

**Not required for PASS:** stairs/elevator/garden; perfect lighting; unique art; every generalistic flag resolved by a human; live bunker apply; Godot playtest by Doug (manual nicety, not gate PASS).

---

## 3. Deterministic gates (hard required numbers)

These **must** be present and valid before APPROVE / before claiming beginner-path completion. AI must not invent below MV. Missing → hole → fail lint.

| Gate ID | Required fields | Type / unit | Minimum viable (MV) | Notes |
| --- | --- | --- | --- | --- |
| **D-MAP-01** Map envelope | `room_count` | int | **≥ 2** | Beginner path: start + goal minimum. |
| **D-MAP-02** Coordinate frame | `units`, growth axis | enum | `meters`; grow toward **−Z**; `x≈0` centerline | Matches WORLD_SCHEMA. |
| **D-MAP-03** Floor policy | `floor_y` per room | number | **0.0** for all rooms on beginner path v1 | 3.2 allowed only if stairs/elevator in scope (out of beginner v1). |
| **D-ROOM-01** Room identity | `id` | snake_case string | non-empty, unique | |
| **D-ROOM-02** Room size | `size` [width, depth] | meters | **width ≥ 4.0**, **depth ≥ 4.0** | Fits door + walk; demo used 6×8 / 8×8. |
| **D-ROOM-03** Room center | `center` [x, z] | meters | set so rooms **do not interior-overlap** | Shared door edge OK. |
| **D-ROOM-04** Room height | `height` | meters | **≥ 2.5** (default 3.0) | Schema default 3.0. |
| **D-EXIT-01** Exit count | per room: count of sides = `door` or `open` on path | int | Start: **≥ 1** forward exit; Goal: **≥ 1** entry; Transit: **≥ 2** if mid-path | |
| **D-EXIT-02** Exit alignment | paired doors between adjacent rooms | geometry | Door sides **meet** on shared edge; same axis; within door-width tolerance of schema (Z doors 3.0 m, X doors 2.2 m) | world_agent rule. |
| **D-EXIT-03** Graph connectivity | undirected graph of rooms via doors | graph | **start reaches goal** | BFS/DFS check. |
| **D-START-01** Start room | `start_room_id` | id ref | must exist | |
| **D-START-02** Start point | `start_pos` [x,y,z] or `auto` | meters | inside start room, **inset ≥ 0.75 m** from walls; y = floor_y + ~0.9 if coded spawn | If code owns spawn, gate records intended room + auto. |
| **D-GOAL-01** Goal room | `goal_room_id` | id ref | must exist; may equal a fight room | |
| **D-GOAL-02** Win rule | `win` | enum/text | **`all_grunts_down`** (home_fps) | |
| **D-ENEMY-01** Grunt count | `grunt_count` | int | **≥ 1** | world_agent rejects empty maps. |
| **D-ENEMY-02** Grunt placement | each grunt: `id`, `room`, `pos` | — | inside that room, inset ≥ 0.75 m; y = floor_y + 0.85 | At least one grunt in goal room **or** on unique path to goal. |
| **D-ITEM-01** Pickup bounds (if any) | each item: `id`, `kind`, `room`, `pos` | — | inside room, inset ≥ 0.5 m; y = floor_y + 0.45 | Zero items allowed for deterministic PASS; if present, must be valid. |
| **D-PAL-01** Color refs | every room `color` | palette key | key **exists** in palette | RGB values themselves are generalistic. |
| **D-ID-01** Uniqueness | all piece/enemy/item ids | set | unique snake_case | |
| **D-SAFE-01** Live map policy | `target_map` | enum | `fresh_demo` default | Must not imply overwrite of live `small_bunker` without Doug apply yes. |

### Deterministic gate pack for “basic beginner path” (Phase 2 fill target)

When Doug says go, AI throws numbers into **exactly this pack** first:

```
room_count = 2
rooms[0]: start_room  size≥6×6  (MV soft target 6×8)  one minus_z door
rooms[1]: goal_room   size≥6×6  (MV soft target 8×8)  one plus_z door aligned
floor_y = 0.0 both
grunt_count = 1 in goal_room
win = all_grunts_down
optional: 1 health_pack in start_room (generalistic-friendly but valid if present)
target_map = fresh_demo
```

Soft targets above MV improve playability; MV is the hard floor.

---

## 4. Generalistic gates (creative / AI defaults + human-touch flags)

AI **may** fill these with safe, flavorful defaults. Each filled field gets a **flag** for humans:

| Flag | Meaning |
| --- | --- |
| `leave` | Default is fine; no need to touch |
| `optional` | Worth a glance if polishing |
| `suggested` | Human taste likely matters — review before ship |
| `blocked` | Needs Doug decision before treat as final (rare in beginner path) |

| Gate ID | Open fields | Default approach (AI) | Typical flag |
| --- | --- | --- | --- |
| **G-VIS-01** Vision / fantasy copy | short prose | 2–3 plain sentences: bunker sweep fantasy | `optional` |
| **G-NAME-01** Game title / game_id | strings | `beginner_path_<YYYYMMDD>` / title “Beginner Path” | `optional` |
| **G-ROOM-01** Room purpose labels | purpose text | start=`spawn`, goal=`fight` | `leave` |
| **G-ROOM-02** Room ids naming | id strings | `start_foyer`, `goal_fight` (or similar) | `optional` |
| **G-LOOK-01** Wall look flavors | `hall\|fight\|bunker\|…` | start=`hall`, goal=`fight` | `leave` |
| **G-PAL-02** Palette RGB | [r,g,b] 0–1 | muted warm foyer + darker fight reds (demo-like) | `suggested` |
| **G-MOOD-01** Mood adjectives | eerie / playful / grim | “tense but readable” | `optional` |
| **G-ITEM-02** Whether to place health | bool + pos | **yes**, one pack in start, off-center | `optional` |
| **G-ITEM-03** Extra pickups | list | **none** for beginner path | `leave` |
| **G-ENEMY-03** Extra grunts | count | **0** extras (exactly 1 total) | `leave` |
| **G-ENEMY-04** Grunt facing / flavor | notes | “faces the entry door” | `leave` |
| **G-PATH-01** Optional third room | branch or linear insert | **omit** for first Phase 2 test | `suggested` if added |
| **G-PATH-02** Dead-end flavor alcove | optional room with no goal route need | **omit** | `optional` |
| **G-DIFF-01** Difficulty tiers table | easy/normal/hard | easy only = ship; others “same as easy / out of scope” | `leave` |
| **G-WEAP-01** Weapons / tools | refs | existing rifle; no new tools | `leave` |
| **G-LIGHT-01** Lighting notes | prose | “use nearby code lights; new rooms dim” | `optional` |
| **G-META-01** Constraints / out-of-scope list | bullets | copy Phase 1 out-of-scope set | `leave` |

**Rule:** Generalistic fill must never violate a deterministic gate. If a creative choice would break D-\*, reject it and pick another default.

---

## 5. How gates sit on the existing pipeline (design only — not implemented)

```
Ideation (this folder) ──guides──▶ Planner interview / AI fill
                                      │ writes
                                      ▼
                              MASTER_GAME.md  (+ gate checklist section)
                                      │ derive
                                      ▼
                              BUILD_QUEUE.json
                                      │ Doug APPROVE
                                      ▼
                              builder_loop.py (re-read sections each step)
                                      │
                                      ▼
                              world.<game_id>.json  (fresh demo) + runs/
```

**Planned Phase 2 touchpoints (do not execute until Doug says go):**

1. Add `## Gates` (deterministic table + generalistic table with flags) to MASTER template / planner prompt.
2. Add `builder` or planner `--gate-lint` that checks D-\* + start→goal connectivity.
3. Add a **beginner path seed** generator that throws MV+soft numbers into D-\* and defaults into G-\*, emits MASTER + queue under `games/beginner_path_<date>/`.
4. Run dry-run builder; optional materialize `world.beginner_path_*.json` in that game dir (same pattern as demo_corridor). **No** live `--allow-apply` unless Doug asks.

---

## 6. Beginner path “most potential to lead to completion” (fill recipe)

When Phase 2 starts, prefer this recipe (maximizes completion odds):

| Choice | Value | Why |
| --- | --- | --- |
| Rooms | 2 only | Fewest doors to mis-align |
| Layout | collinear along −Z, shared edge door | Proven in demo_corridor |
| Sizes | 6×8 then 8×8 | Above MV; room for grunt + player |
| Grunts | 1 in goal | Meets D-ENEMY-01; clear win |
| Health | 1 in start | Forgiving for first-timers; still optional for D-\* |
| Floor | single floor_y=0 | Avoids stairs/elevator |
| Map | fresh_demo | Avoids bunker collision |
| Mode | progression | Matches start→goal story |

---

## 7. Phase 1 completion checklist

- [x] Deterministic gates listed with required fields + MV values  
- [x] Generalistic gates listed with open fields + default approach + human-touch flags  
- [x] Completion definition written (playable coherent end state; not perfect fill)  
- [x] Running decision log captured (`DECISION_LOG.md`)  
- [x] Explicit ban: Phase 2 must not erase/override ideation  
- [x] Phase 2 readiness described; **implementation not started**

**PHASE 1 DONE. PHASE 2 READY WHEN DOUG SAYS GO.**

---

## Amendment log

_(append only)_
