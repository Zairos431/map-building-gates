---
schema_version: 1
game_id: beginner_path_20261106
title: Beginner Path
mode: progression
status: draft
target: home_fps
target_map: fresh_demo
win: all_grunts_down
start_room_id: start_foyer
goal_room_id: goal_fight
start_pos: [0.0, 0.9, -4.0]
units: meters
growth_axis: minus_z
created: 2026-11-06
updated: 2026-11-06
---

# Beginner Path — Master Game Document

> Beginner path generated for map-building gates Phase 2. Two rooms, one door, one grunt.
> Fresh demo only: this file does not target the live bunker, and nothing here is approved.
> gate-lint recomputes deterministic gates from the numbers below. The builder loop is not in this repo.

## Vision
A lone operator sweeps the first two rooms of a bunker: a quiet foyer, then one fight room. The player can grab a health pack before walking through the only door. Dropping the single grunt ends the slice.

## Player fantasy / win condition
- Fantasy: a lone operator clearing a two-room bunker slice
- Win: all grunts down (home_fps rule: every grunt counts toward the win) — here, `grunt_goal`.
- Lose: player health reaches 0 (existing code behavior, unchanged)

## Mode & difficulty tiers
- Mode: progression — one fixed path, start_foyer to goal_fight.
- Tiers:
  | tier | enemy count mult | enemy notes | pickups | notes |
  | --- | --- | --- | --- | --- |
  | easy | 1 | grunt_goal only | health_start | v1 ships this tier |
  | normal | 1 | same layout | health_start | same as easy in v1 |
  | hard | 1 | same layout | health_start | out of scope for v1 |
- Where tiers live: out of scope for v1 (one world.json); tiers become world.json variants later.

## Map layout
Fresh demo map. WORLD_SCHEMA coordinates: meters, +Y up, z runs from 0 toward -Z, x = 0 is the center line, floor_y 0.

start_foyer spans x [-3.0, 3.0] and z [-8.0, 0.0]. goal_fight spans x [-4.0, 4.0] and z [-16.0, -8.0]. The shared edge is z = -8.0 when the foyer minus_z door meets the fight room plus_z door. Z-side doors are 3.0 m wide, centered at x = 0.

### Room: start_foyer
- purpose: spawn
- center: [0.0, -4.0]
- size: [6.0, 8.0]
- height: 3.0
- floor_y: 0.0
- color: foyer_warm
- look: hall
- sides: {plus_z: wall, minus_z: door, plus_x: wall, minus_x: wall}
- connections: [goal_fight via minus_z]

### Room: goal_fight
- purpose: fight
- center: [0.0, -12.0]
- size: [8.0, 8.0]
- height: 3.0
- floor_y: 0.0
- color: fight_red
- look: fight
- sides: {plus_z: door, minus_z: wall, plus_x: wall, minus_x: wall}
- connections: [start_foyer via plus_z]

## Palette
- foyer_warm: [0.55, 0.52, 0.45]
- fight_red: [0.45, 0.2, 0.18]

## Weapons & tools
### Weapon: rifle
- role: primary (the existing home_fps player weapon)
- stats: existing code weapon, unchanged
- lives in: code

### Tool: none
- use: no tools in v1
- lives in: n/a

## Enemies & spawns
| id | kind | room | pos [x,y,z] or "auto" | tier | notes |
| --- | --- | --- | --- | --- | --- |
| grunt_goal | grunt | goal_fight | [0.0, 0.85, -12.5] | all | y = floor_y + 0.85; faces the entry door |

## Items / pickups
| id | kind | room | pos [x,y,z] or "auto" | tier | notes |
| --- | --- | --- | --- | --- | --- |
| health_start | health_pack | start_foyer | [-1.5, 0.45, -5.0] | all | +25 health; off-center, inset from the walls |

## Progression
1. Spawn in start_foyer at [0.0, 0.9, -4.0].
2. Optional: pick up health_start.
3. Go through the start_foyer minus_z door into goal_fight.
4. Down grunt_goal and the home_fps rule shows "You win".

## Constraints / out-of-scope
- In world.json (data): start_foyer, goal_fight, colors foyer_warm and fight_red, the shared door, grunt_goal, health_start.
- In code: lights, player spawn, the rifle, HUD. New rooms get no light of their own (known world_agent limit).
- world_agent rule: a valid map needs at least one grunt and every door must meet a neighbor, so rooms and grunt_goal go in one batch (S02).
- Target map: fresh_demo. This master does not write the live small_bunker.
- Out of scope for v1: difficulty variants, stairs, elevator, garden, new enemy or item kinds, new weapons, multi-floor, FFA, World/Game Maker UI merge.
- New palette colors: foyer_warm: [0.55, 0.52, 0.45], fight_red: [0.45, 0.2, 0.18]
- Intended start_pos is [0.0, 0.9, -4.0] inside start_foyer. Home FPS code still owns the live player spawn; this point is what gate-lint checks.

## Gates

Authoritative check: `python3 tools/gate_lint.py MASTER_GAME.md`.
The Status column is the generator's claim. gate-lint recomputes every D-* gate
from the rooms, spawns, and palette above and does not trust this column.
Generalistic rows are flavor. human_touch is leave, optional, suggested, or blocked.
Creative fill must not break a D-* gate.

### Deterministic
| Gate ID | Check | Value | Status |
| --- | --- | --- | --- |
| D-MAP-01 | room_count >= 2 | 2 | pass |
| D-MAP-02 | meters; grow toward -Z; x = 0 is the center line | meters, minus_z, start x=0.0 | pass |
| D-MAP-03 | beginner floor_y is 0.0 | 0.0, 0.0 | pass |
| D-ROOM-01 | snake_case room id, unique | start_foyer, goal_fight | pass |
| D-ROOM-02 | width >= 4 m and depth >= 4 m | start_foyer 6.0x8.0, goal_fight 8.0x8.0 | pass |
| D-ROOM-03 | room interiors do not overlap | centers start_foyer [0.0, -4.0], goal_fight [0.0, -12.0] | pass |
| D-ROOM-04 | height >= 2.5 m (default 3.0) | 3.0, 3.0 | pass |
| D-EXIT-01 | start has a forward exit; goal has an entry; transit has two | start_foyer one minus_z door; goal_fight one plus_z door | pass |
| D-EXIT-02 | door or open sides meet on a shared edge | start_foyer.minus_z meets goal_fight.plus_z at z=-8.0 | pass |
| D-EXIT-03 | start reaches goal through those doors | start_foyer reaches goal_fight | pass |
| D-START-01 | start_room_id names a room | start_foyer | pass |
| D-START-02 | start point inside the start room, inset >= 0.75 m | [0.0, 0.9, -4.0] | pass |
| D-GOAL-01 | goal_room_id names a room | goal_fight | pass |
| D-GOAL-02 | win is all_grunts_down | all_grunts_down | pass |
| D-ENEMY-01 | at least one grunt | 1 | pass |
| D-ENEMY-02 | grunt inside its room; one grunt in the goal or on the path | grunt_goal in goal_fight | pass |
| D-ITEM-01 | pickups, if any, sit inside their room | health_start in start_foyer | pass |
| D-PAL-01 | every room color names a palette entry | foyer_warm, fight_red | pass |
| D-ID-01 | piece, enemy, and item ids are unique snake_case | ids unique | pass |
| D-SAFE-01 | target_map is fresh_demo | fresh_demo | pass |

### Generalistic
| Gate ID | Field | Default | human_touch |
| --- | --- | --- | --- |
| G-VIS-01 | vision | Lone operator sweeps two bunker rooms, then drops one grunt. | optional |
| G-NAME-01 | game_id and title | beginner_path_20261106 / Beginner Path | optional |
| G-ROOM-01 | room purpose | start spawn, goal fight | leave |
| G-ROOM-02 | room ids | start_foyer, goal_fight | optional |
| G-LOOK-01 | wall look | start hall, goal fight | leave |
| G-PAL-02 | palette RGB | muted warm foyer and darker fight red | suggested |
| G-MOOD-01 | mood | tense but readable | optional |
| G-ITEM-02 | health pack | one pack in the start room, off-center | optional |
| G-ITEM-03 | extra pickups | none | leave |
| G-ENEMY-03 | extra grunts | none (exactly one grunt) | leave |
| G-ENEMY-04 | grunt facing | faces the entry door | leave |
| G-PATH-01 | third room | omitted | leave |
| G-PATH-02 | dead-end alcove | omitted | optional |
| G-DIFF-01 | difficulty tiers | easy ships; normal and hard same as easy, out of scope | leave |
| G-WEAP-01 | weapons | existing rifle; no new tools | leave |
| G-LIGHT-01 | lighting | use nearby code lights; new rooms dim | optional |
| G-META-01 | out of scope | stairs, elevator, garden, new kinds, live bunker apply | leave |

## Build Steps
Each step is one builder action. The derived queue stays unapproved (`approved: false`) until Doug says APPROVE. This repo does not run the builder.

### S01: Lock ids, colors and coordinates
- section_refs: ["## Map layout", "## Palette", "## Constraints / out-of-scope"]
- action: schema_note
- instruction: Write a schema note listing rooms start_foyer, goal_fight, their centers and sizes, and palette colors foyer_warm, fight_red.
- acceptance:
  - check: master_contains foyer_warm
  - check: master_contains fight_red
  - Room rectangles share one door edge and their interiors do not overlap.
- replaces: null
- ops_hint: null

### S02: Build start_foyer, goal_fight and grunt_goal
- section_refs: ["### Room: start_foyer", "### Room: goal_fight", "## Enemies & spawns", "## Constraints / out-of-scope"]
- action: world_ops
- instruction: Add palette colors, add rooms start_foyer, goal_fight joined by the shared door, and add grunt_goal in the same batch because a map with no grunt is rejected.
- acceptance:
  - check: file runs/step_S02_ops_request.json
  - check: master_contains start_foyer
  - check: master_contains goal_fight
  - check: master_contains grunt_goal
  - The start minus_z door lines up with the goal plus_z door.
- replaces: null
- ops_hint: [{"op": "add_color", "id": "foyer_warm", "rgb": [0.55, 0.52, 0.45]}, {"op": "add_color", "id": "fight_red", "rgb": [0.45, 0.2, 0.18]}, {"op": "add_room", "id": "start_foyer", "center": [0.0, -4.0], "size": [6.0, 8.0], "floor_y": 0.0, "color": "foyer_warm", "look": "hall", "sides": {"plus_z": "wall", "minus_z": "door", "plus_x": "wall", "minus_x": "wall"}}, {"op": "add_room", "id": "goal_fight", "center": [0.0, -12.0], "size": [8.0, 8.0], "floor_y": 0.0, "color": "fight_red", "look": "fight", "sides": {"plus_z": "door", "minus_z": "wall", "plus_x": "wall", "minus_x": "wall"}}, {"op": "add_grunt", "id": "grunt_goal", "room": "goal_fight", "pos": [0.0, -12.5]}]

### S03: Place the start-room health pack
- section_refs: ["### Room: start_foyer", "## Items / pickups"]
- action: world_ops
- instruction: Add health_start in start_foyer so the player can heal before the fight.
- acceptance:
  - check: file runs/step_S03_ops_request.json
  - check: master_contains health_start
  - Health pack sits inside the start room, inset from the walls.
- replaces: null
- ops_hint: [{"op": "add_health_pack", "id": "health_start", "room": "start_foyer", "pos": [-1.5, -5.0]}]

### S04: Verify the slice is complete
- section_refs: ["## Player fantasy / win condition", "## Progression", "## Gates"]
- action: verify
- instruction: Confirm S01 to S03 are covered and the door-aligned path from start_foyer to goal_fight still passes gate-lint.
- acceptance:
  - check: receipts S01,S02,S03
  - check: file runs/step_S01_schema_note.md
  - Walk start to goal, down the grunt, and see You win. A Godot playtest is manual.
- replaces: null
- ops_hint: null
