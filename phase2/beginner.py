"""Fill the Phase 1 beginner-path recipe and write MASTER + queue.

Recipe (ideation section 6): two rooms, collinear along -Z, shared-edge door,
sizes 6x8 then 8x8, one grunt in the goal, one health pack in the start,
floor_y 0, fresh_demo, mode progression.

Geometry matches the demo_corridor lesson. The foyer spans z [-8, 0] and the
fight room spans z [-16, -8], so the doors meet at z = -8. Z doors are 3 m
wide and centered on x = 0.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from phase2.derive import derive_queue
from phase2.gates import format_report, lint_text
from phase2.model import GameSpec, GeneralisticFill, Room, Spawn
from phase2.parse import parse_master
from phase2.schema import (
    BEGINNER_FLOOR_Y,
    DEFAULT_HEIGHT,
    DETERMINISTIC_GATES,
    GENERALISTIC_GATES,
    GROWTH_AXIS,
    GRUNT_Y_OFFSET,
    ITEM_Y_OFFSET,
    SPAWN_Y_OFFSET,
    TARGET_MAP,
    UNITS,
    WIN_RULE,
    fmt_list,
    fmt_num,
)

# Soft targets above the 4 m minimum. Centers put the shared edge at z = -8.
START_CENTER = (0.0, -4.0)
START_SIZE = (6.0, 8.0)
GOAL_CENTER = (0.0, -12.0)
GOAL_SIZE = (8.0, 8.0)
START_POS = (0.0, BEGINNER_FLOOR_Y + SPAWN_Y_OFFSET, -4.0)
GRUNT_POS = (0.0, BEGINNER_FLOOR_Y + GRUNT_Y_OFFSET, -12.5)
HEALTH_POS = (-1.5, BEGINNER_FLOOR_Y + ITEM_Y_OFFSET, -5.0)
FOYER_RGB = (0.55, 0.52, 0.45)
FIGHT_RGB = (0.45, 0.2, 0.18)


def beginner_spec(date: str) -> GameSpec:
    """Build the fresh-demo 2-room path for a YYYYMMDD id."""
    if len(date) != 8 or not date.isdigit():
        raise ValueError(f"date must be YYYYMMDD, got {date!r}")
    created = f"{date[0:4]}-{date[4:6]}-{date[6:8]}"
    datetime.strptime(created, "%Y-%m-%d")
    game_id = f"beginner_path_{date}"
    start = Room(
        id="start_foyer",
        purpose="spawn",
        center=START_CENTER,
        size=START_SIZE,
        height=DEFAULT_HEIGHT,
        floor_y=BEGINNER_FLOOR_Y,
        color="foyer_warm",
        look="hall",
        sides={"plus_z": "wall", "minus_z": "door", "plus_x": "wall", "minus_x": "wall"},
        connections=[("goal_fight", "minus_z")],
    )
    goal = Room(
        id="goal_fight",
        purpose="fight",
        center=GOAL_CENTER,
        size=GOAL_SIZE,
        height=DEFAULT_HEIGHT,
        floor_y=BEGINNER_FLOOR_Y,
        color="fight_red",
        look="fight",
        sides={"plus_z": "door", "minus_z": "wall", "plus_x": "wall", "minus_x": "wall"},
        connections=[("start_foyer", "plus_z")],
    )
    return GameSpec(
        game_id=game_id,
        title="Beginner Path",
        created=created,
        mode="progression",
        target="home_fps",
        target_map=TARGET_MAP,
        win=WIN_RULE,
        start_room_id=start.id,
        goal_room_id=goal.id,
        start_pos=START_POS,
        units=UNITS,
        growth_axis=GROWTH_AXIS,
        vision=(
            "A lone operator sweeps the first two rooms of a bunker: a quiet foyer, "
            "then one fight room. The player can grab a health pack before walking "
            "through the only door. Dropping the single grunt ends the slice."
        ),
        fantasy="a lone operator clearing a two-room bunker slice",
        lose="player health reaches 0 (existing code behavior, unchanged)",
        mood="tense but readable",
        rooms=[start, goal],
        enemies=[
            Spawn(
                id="grunt_goal",
                kind="grunt",
                room=goal.id,
                pos=GRUNT_POS,
                pos_auto=False,
                tier="all",
                notes="y = floor_y + 0.85; faces the entry door",
            )
        ],
        items=[
            Spawn(
                id="health_start",
                kind="health_pack",
                room=start.id,
                pos=HEALTH_POS,
                pos_auto=False,
                tier="all",
                notes="+25 health; off-center, inset from the walls",
            )
        ],
        palette=[("foyer_warm", FOYER_RGB), ("fight_red", FIGHT_RGB)],
        tiers=[
            ("easy", "1", "grunt_goal only", "health_start", "v1 ships this tier"),
            ("normal", "1", "same layout", "health_start", "same as easy in v1"),
            ("hard", "1", "same layout", "health_start", "out of scope for v1"),
        ],
        progression=[
            f"Spawn in {start.id} at {fmt_list(START_POS)}.",
            "Optional: pick up health_start.",
            f"Go through the {start.id} minus_z door into {goal.id}.",
            'Down grunt_goal and the home_fps rule shows "You win".',
        ],
        constraints=[
            "In world.json (data): start_foyer, goal_fight, colors foyer_warm and fight_red, "
            "the shared door, grunt_goal, health_start.",
            "In code: lights, player spawn, the rifle, HUD. New rooms get no light of their own "
            "(known world_agent limit).",
            "world_agent rule: a valid map needs at least one grunt and every door must meet a "
            "neighbor, so rooms and grunt_goal go in one batch (S02).",
            "Target map: fresh_demo. This master does not write the live small_bunker.",
            "Out of scope for v1: difficulty variants, stairs, elevator, garden, new enemy or "
            "item kinds, new weapons, multi-floor, FFA, World/Game Maker UI merge.",
            f"New palette colors: foyer_warm: {fmt_list(FOYER_RGB)}, fight_red: {fmt_list(FIGHT_RGB)}",
            f"Intended start_pos is {fmt_list(START_POS)} inside start_foyer. "
            "Home FPS code still owns the live player spawn; this point is what gate-lint checks.",
        ],
        generalistic=_generalistic(game_id),
    )


def render_master(spec: GameSpec) -> str:
    """Render MASTER_GAME.md. The Status column is a claim; gate-lint recomputes it."""
    start = spec.room(spec.start_room_id)
    goal = spec.room(spec.goal_room_id)
    start_box = _required_bounds(start)
    goal_box = _required_bounds(goal)
    lines: list[str] = [
        "---",
        "schema_version: 1",
        f"game_id: {spec.game_id}",
        f"title: {spec.title}",
        f"mode: {spec.mode}",
        "status: draft",
        f"target: {spec.target}",
        f"target_map: {spec.target_map}",
        f"win: {spec.win}",
        f"start_room_id: {spec.start_room_id}",
        f"goal_room_id: {spec.goal_room_id}",
        f"start_pos: {fmt_list(spec.start_pos)}",
        f"units: {spec.units}",
        f"growth_axis: {spec.growth_axis}",
        f"created: {spec.created}",
        f"updated: {spec.created}",
        "---",
        "",
        f"# {spec.title} — Master Game Document",
        "",
        "> Beginner path generated for map-building gates Phase 2. Two rooms, one door, one grunt.",
        "> Fresh demo only: this file does not target the live bunker, and nothing here is approved.",
        "> gate-lint recomputes deterministic gates from the numbers below. The builder loop is not in this repo.",
        "",
        "## Vision",
        spec.vision,
        "",
        "## Player fantasy / win condition",
        f"- Fantasy: {spec.fantasy}",
        f"- Win: all grunts down (home_fps rule: every grunt counts toward the win) — here, `{spec.enemies[0].id if spec.enemies else 'none'}`.",
        f"- Lose: {spec.lose}",
        "",
        "## Mode & difficulty tiers",
        f"- Mode: {spec.mode} — one fixed path, {spec.start_room_id} to {spec.goal_room_id}.",
        "- Tiers:",
        "  | tier | enemy count mult | enemy notes | pickups | notes |",
        "  | --- | --- | --- | --- | --- |",
    ]
    for tier in spec.tiers:
        lines.append("  | " + " | ".join(tier) + " |")
    lines.extend(
        [
            "- Where tiers live: out of scope for v1 (one world.json); tiers become world.json variants later.",
            "",
            "## Map layout",
            "Fresh demo map. WORLD_SCHEMA coordinates: meters, +Y up, z runs from 0 toward -Z, "
            "x = 0 is the center line, floor_y 0.",
            "",
            (
                f"{start.id} spans x [{fmt_num(start_box[0])}, {fmt_num(start_box[1])}] and "
                f"z [{fmt_num(start_box[2])}, {fmt_num(start_box[3])}]. "
                f"{goal.id} spans x [{fmt_num(goal_box[0])}, {fmt_num(goal_box[1])}] and "
                f"z [{fmt_num(goal_box[2])}, {fmt_num(goal_box[3])}]. "
                f"The shared edge is z = {fmt_num(start_box[2])} when the foyer minus_z door "
                "meets the fight room plus_z door. Z-side doors are 3.0 m wide, centered at x = 0."
            ),
            "",
        ]
    )
    for room in spec.rooms:
        lines.extend(_room_block(room))
    lines.extend(["## Palette"])
    for name, rgb in spec.palette:
        lines.append(f"- {name}: {fmt_list(rgb)}")
    lines.extend(
        [
            "",
            "## Weapons & tools",
            "### Weapon: rifle",
            "- role: primary (the existing home_fps player weapon)",
            "- stats: existing code weapon, unchanged",
            "- lives in: code",
            "",
            "### Tool: none",
            "- use: no tools in v1",
            "- lives in: n/a",
            "",
            "## Enemies & spawns",
            "| id | kind | room | pos [x,y,z] or \"auto\" | tier | notes |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for enemy in spec.enemies:
        lines.append(_spawn_row(enemy))
    lines.extend(
        [
            "",
            "## Items / pickups",
            "| id | kind | room | pos [x,y,z] or \"auto\" | tier | notes |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in spec.items:
        lines.append(_spawn_row(item))
    lines.extend(["", "## Progression"])
    for index, beat in enumerate(spec.progression, start=1):
        lines.append(f"{index}. {beat}")
    lines.extend(["", "## Constraints / out-of-scope"])
    for bullet in spec.constraints:
        lines.append(f"- {bullet}")
    lines.extend(
        [
            "",
            "## Gates",
            "",
            "Authoritative check: `python3 tools/gate_lint.py MASTER_GAME.md`.",
            "The Status column is the generator's claim. gate-lint recomputes every D-* gate",
            "from the rooms, spawns, and palette above and does not trust this column.",
            "Generalistic rows are flavor. human_touch is leave, optional, suggested, or blocked.",
            "Creative fill must not break a D-* gate.",
            "",
            "### Deterministic",
            "| Gate ID | Check | Value | Status |",
            "| --- | --- | --- | --- |",
        ]
    )
    values = _deterministic_values(spec)
    known = {gate_id for gate_id, _label in DETERMINISTIC_GATES}
    for gate_id, label in DETERMINISTIC_GATES:
        lines.append(f"| {gate_id} | {label} | {values.get(gate_id, 'n/a')} | pass |")
    lines.extend(
        [
            "",
            "### Generalistic",
            "| Gate ID | Field | Default | human_touch |",
            "| --- | --- | --- | --- |",
        ]
    )
    fills = {row.gate_id: row for row in spec.generalistic}
    for gate_id, field_name in GENERALISTIC_GATES:
        row = fills.get(gate_id)
        if row is None:
            lines.append(f"| {gate_id} | {field_name} | (unset) | blocked |")
        else:
            lines.append(f"| {row.gate_id} | {row.field} | {row.default} | {row.human_touch} |")
    lines.extend(["", "## Build Steps"])
    lines.append(
        "Each step is one builder action. The derived queue stays unapproved "
        "(`approved: false`) until Doug says APPROVE. This repo does not run the builder."
    )
    lines.append("")
    for step in _build_steps(spec):
        lines.extend(step)
    unused = known - set(values)
    if unused:
        raise RuntimeError(f"deterministic value table is missing {sorted(unused)}")
    text = "\n".join(lines).rstrip() + "\n"
    return text


def write_game(out_dir: Path, date: str, force: bool = False) -> tuple[Path, Path]:
    """Write MASTER_GAME.md and an unapproved BUILD_QUEUE.json. Refuses a failing lint."""
    spec = beginner_spec(date)
    master = render_master(spec)
    report = lint_text(master, path=str(out_dir / "MASTER_GAME.md"))
    if not report.ok:
        raise RuntimeError(format_report(report))
    doc = parse_master(master)
    if doc.errors:
        raise SystemExit("generator MASTER did not parse:\n" + "\n".join(doc.errors))
    queue = derive_queue(doc)
    if queue["approved"] is not False:
        raise SystemExit("derived queue must stay unapproved")
    master_path = out_dir / "MASTER_GAME.md"
    queue_path = out_dir / "BUILD_QUEUE.json"
    if master_path.exists() and not force:
        raise FileExistsError(f"{master_path} already exists; pass --force to overwrite")
    out_dir.mkdir(parents=True, exist_ok=True)
    master_path.write_text(master, encoding="utf-8")
    queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return master_path, queue_path


def _generalistic(game_id: str) -> list[GeneralisticFill]:
    rows = {
        "G-VIS-01": ("vision", "Lone operator sweeps two bunker rooms, then drops one grunt.", "optional"),
        "G-NAME-01": ("game_id and title", f"{game_id} / Beginner Path", "optional"),
        "G-ROOM-01": ("room purpose", "start spawn, goal fight", "leave"),
        "G-ROOM-02": ("room ids", "start_foyer, goal_fight", "optional"),
        "G-LOOK-01": ("wall look", "start hall, goal fight", "leave"),
        "G-PAL-02": ("palette RGB", "muted warm foyer and darker fight red", "suggested"),
        "G-MOOD-01": ("mood", "tense but readable", "optional"),
        "G-ITEM-02": ("health pack", "one pack in the start room, off-center", "optional"),
        "G-ITEM-03": ("extra pickups", "none", "leave"),
        "G-ENEMY-03": ("extra grunts", "none (exactly one grunt)", "leave"),
        "G-ENEMY-04": ("grunt facing", "faces the entry door", "leave"),
        "G-PATH-01": ("third room", "omitted", "leave"),
        "G-PATH-02": ("dead-end alcove", "omitted", "optional"),
        "G-DIFF-01": (
            "difficulty tiers",
            "easy ships; normal and hard same as easy, out of scope",
            "leave",
        ),
        "G-WEAP-01": ("weapons", "existing rifle; no new tools", "leave"),
        "G-LIGHT-01": ("lighting", "use nearby code lights; new rooms dim", "optional"),
        "G-META-01": (
            "out of scope",
            "stairs, elevator, garden, new kinds, live bunker apply",
            "leave",
        ),
    }
    fills: list[GeneralisticFill] = []
    for gate_id, field_name in GENERALISTIC_GATES:
        default_field, default, flag = rows[gate_id]
        if default_field != field_name:
            raise RuntimeError(f"{gate_id} field drifted: {default_field} vs {field_name}")
        fills.append(GeneralisticFill(gate_id, field_name, default, flag))
    return fills


def _deterministic_values(spec: GameSpec) -> dict[str, str]:
    start = spec.room(spec.start_room_id)
    goal = spec.room(spec.goal_room_id)
    start_box = _required_bounds(start)
    sizes = ", ".join(
        f"{room.id} {fmt_num(room.size[0])}x{fmt_num(room.size[1])}"
        for room in spec.rooms
        if room.size is not None
    )
    centers = ", ".join(
        f"{room.id} {fmt_list(room.center)}" for room in spec.rooms if room.center is not None
    )
    floors = ", ".join(
        fmt_num(room.floor_y) for room in spec.rooms if room.floor_y is not None
    )
    heights = ", ".join(
        fmt_num(DEFAULT_HEIGHT if room.height is None else room.height) for room in spec.rooms
    )
    grunt_where = ", ".join(f"{enemy.id} in {enemy.room}" for enemy in spec.enemies) or "none"
    item_where = ", ".join(f"{item.id} in {item.room}" for item in spec.items) or "none"
    colors = ", ".join(name for name, _rgb in spec.palette)
    return {
        "D-MAP-01": str(len(spec.rooms)),
        "D-MAP-02": f"{spec.units}, {spec.growth_axis}, start x={fmt_num(start.center[0]) if start.center else 'n/a'}",
        "D-MAP-03": floors,
        "D-ROOM-01": ", ".join(room.id for room in spec.rooms),
        "D-ROOM-02": sizes,
        "D-ROOM-03": f"centers {centers}",
        "D-ROOM-04": heights,
        "D-EXIT-01": f"{start.id} one minus_z door; {goal.id} one plus_z door",
        "D-EXIT-02": f"{start.id}.minus_z meets {goal.id}.plus_z at z={fmt_num(start_box[2])}",
        "D-EXIT-03": f"{start.id} reaches {goal.id}",
        "D-START-01": spec.start_room_id,
        "D-START-02": fmt_list(spec.start_pos),
        "D-GOAL-01": spec.goal_room_id,
        "D-GOAL-02": spec.win,
        "D-ENEMY-01": str(sum(1 for enemy in spec.enemies if enemy.kind == "grunt")),
        "D-ENEMY-02": grunt_where,
        "D-ITEM-01": item_where,
        "D-PAL-01": colors,
        "D-ID-01": "ids unique",
        "D-SAFE-01": spec.target_map,
    }


def _room_block(room: Room) -> list[str]:
    assert room.center is not None and room.size is not None and room.floor_y is not None
    assert room.height is not None and room.sides is not None
    sides = ", ".join(f"{name}: {room.sides[name]}" for name in ("plus_z", "minus_z", "plus_x", "minus_x"))
    if room.connections:
        connections = "[" + ", ".join(f"{other} via {side}" for other, side in room.connections) + "]"
    else:
        connections = "[]"
    return [
        f"### Room: {room.id}",
        f"- purpose: {room.purpose}",
        f"- center: {fmt_list(room.center)}",
        f"- size: {fmt_list(room.size)}",
        f"- height: {fmt_num(room.height)}",
        f"- floor_y: {fmt_num(room.floor_y)}",
        f"- color: {room.color}",
        f"- look: {room.look}",
        f"- sides: {{{sides}}}",
        f"- connections: {connections}",
        "",
    ]


def _spawn_row(spawn: Spawn) -> str:
    pos = "auto" if spawn.pos_auto or spawn.pos is None else fmt_list(spawn.pos)
    cells = [spawn.id, spawn.kind, spawn.room, pos, spawn.tier, spawn.notes]
    return "| " + " | ".join(cells) + " |"


def _build_steps(spec: GameSpec) -> list[list[str]]:
    room_heads = [f"### Room: {room.id}" for room in spec.rooms]
    color_ids = [name for name, _rgb in spec.palette]
    room_ids = ", ".join(room.id for room in spec.rooms)
    grunt_ids = ", ".join(enemy.id for enemy in spec.enemies) or "none"
    contains = [f"check: master_contains {name}" for name in color_ids]
    contains += [f"check: master_contains {room.id}" for room in spec.rooms]
    contains += [f"check: master_contains {enemy.id}" for enemy in spec.enemies]
    s02_refs = room_heads + ["## Enemies & spawns", "## Constraints / out-of-scope"]
    s03_refs = [f"### Room: {spec.start_room_id}", "## Items / pickups"]
    if spec.items:
        s03_instruction = (
            f"Add {', '.join(item.id for item in spec.items)} in {spec.start_room_id} "
            "so the player can heal before the fight."
        )
        s03_accept = [
            "check: file runs/step_S03_ops_request.json",
            *[f"check: master_contains {item.id}" for item in spec.items],
            "Health pack sits inside the start room, inset from the walls.",
        ]
        s03_ops: object = [
            {
                "op": "add_health_pack",
                "id": item.id,
                "room": item.room,
                "pos": [item.pos[0], item.pos[2]] if item.pos is not None else None,
            }
            for item in spec.items
        ]
    else:
        s03_instruction = "Record that this beginner path places no pickups."
        s03_accept = ["check: master_contains Items / pickups", "No pickup rows were required."]
        s03_ops = None
    ops: list[object] = [{"op": "add_color", "id": name, "rgb": list(rgb)} for name, rgb in spec.palette]
    for room in spec.rooms:
        assert room.center is not None and room.size is not None and room.sides is not None
        ops.append(
            {
                "op": "add_room",
                "id": room.id,
                "center": list(room.center),
                "size": list(room.size),
                "floor_y": room.floor_y,
                "color": room.color,
                "look": room.look,
                "sides": {
                    "plus_z": room.sides["plus_z"],
                    "minus_z": room.sides["minus_z"],
                    "plus_x": room.sides["plus_x"],
                    "minus_x": room.sides["minus_x"],
                },
            }
        )
    for enemy in spec.enemies:
        assert enemy.pos is not None
        ops.append(
            {
                "op": "add_grunt",
                "id": enemy.id,
                "room": enemy.room,
                "pos": [enemy.pos[0], enemy.pos[2]],
            }
        )
    steps = [
        _step(
            "S01",
            "Lock ids, colors and coordinates",
            ["## Map layout", "## Palette", "## Constraints / out-of-scope"],
            "schema_note",
            f"Write a schema note listing rooms {room_ids}, their centers and sizes, and palette colors {', '.join(color_ids)}.",
            [
                *contains[: len(color_ids)],
                "Room rectangles share one door edge and their interiors do not overlap.",
            ],
            None,
        ),
        _step(
            "S02",
            f"Build {room_ids} and {grunt_ids}",
            s02_refs,
            "world_ops",
            f"Add palette colors, add rooms {room_ids} joined by the shared door, and add {grunt_ids} in the same batch because a map with no grunt is rejected.",
            [
                "check: file runs/step_S02_ops_request.json",
                *[f"check: master_contains {room.id}" for room in spec.rooms],
                *[f"check: master_contains {enemy.id}" for enemy in spec.enemies],
                "The start minus_z door lines up with the goal plus_z door.",
            ],
            ops,
        ),
        _step(
            "S03",
            "Place the start-room health pack" if spec.items else "Record that there are no pickups",
            s03_refs,
            "world_ops" if spec.items else "schema_note",
            s03_instruction,
            s03_accept,
            s03_ops,
        ),
        _step(
            "S04",
            "Verify the slice is complete",
            ["## Player fantasy / win condition", "## Progression", "## Gates"],
            "verify",
            f"Confirm S01 to S03 are covered and the door-aligned path from {spec.start_room_id} to {spec.goal_room_id} still passes gate-lint.",
            [
                "check: receipts S01,S02,S03",
                "check: file runs/step_S01_schema_note.md",
                "Walk start to goal, down the grunt, and see You win. A Godot playtest is manual.",
            ],
            None,
        ),
    ]
    return steps


def _step(
    step_id: str,
    title: str,
    refs: list[str],
    action: str,
    instruction: str,
    acceptance: list[str],
    ops_hint: object,
) -> list[str]:
    lines = [
        f"### {step_id}: {title}",
        f"- section_refs: {json.dumps(refs)}",
        f"- action: {action}",
        f"- instruction: {instruction}",
        "- acceptance:",
    ]
    for item in acceptance:
        lines.append(f"  - {item}")
    lines.append("- replaces: null")
    if ops_hint is None:
        lines.append("- ops_hint: null")
    else:
        lines.append(f"- ops_hint: {json.dumps(ops_hint)}")
    lines.append("")
    return lines


def _required_bounds(room: Room) -> tuple[float, float, float, float]:
    box = room.bounds()
    if box is None:
        raise ValueError(f"{room.id} is missing center or size")
    return box
