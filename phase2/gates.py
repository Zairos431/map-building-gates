"""Deterministic D-* checks and start-to-goal connectivity.

gate-lint recomputes every result from rooms, spawns, palette, and frontmatter.
A Status cell of "pass" in ## Gates does not count.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import json
import re

from phase2.model import MasterDoc, Room, Spawn
from phase2.parse import parse_master
from phase2.schema import (
    BEGINNER_FLOOR_Y,
    DEFAULT_HEIGHT,
    DETERMINISTIC_GATES,
    DOOR_W_X,
    DOOR_W_Z,
    EDGE_EPS,
    GENERALISTIC_GATES,
    GROWTH_AXIS,
    GRUNT_INSET,
    GRUNT_Y_OFFSET,
    HUMAN_TOUCH,
    ITEM_INSET,
    ITEM_Y_OFFSET,
    MIN_DEPTH,
    MIN_DOOR_OVERLAP,
    MIN_HEIGHT,
    MIN_ROOMS,
    MIN_WIDTH,
    OPPOSITE_SIDE,
    OVERLAP_EPS,
    SCHEMA_FLOOR_YS,
    SNAKE_CASE,
    SPAWN_INSET,
    SPAWN_Y_OFFSET,
    TARGET_MAP,
    UNITS,
    WIN_RULE,
    Y_TOL,
    fmt_num,
)

_SNAKE = re.compile(SNAKE_CASE)


@dataclass
class GateResult:
    gate_id: str
    ok: bool
    detail: str


@dataclass
class LintReport:
    path: str | None
    holes: list[str] = field(default_factory=list)
    results: list[GateResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.holes and all(result.ok for result in self.results)


def lint_text(text: str, path: str | None = None) -> LintReport:
    report = lint_document(parse_master(text))
    report.path = path
    return report


def lint_document(doc: MasterDoc) -> LintReport:
    report = LintReport(path=None, holes=list(doc.errors))
    if not doc.saw_gates:
        report.holes.append("missing ## Gates section")
    if not doc.saw_deterministic_table:
        report.holes.append("missing ### Deterministic table under ## Gates")
    if not doc.saw_generalistic_table:
        report.holes.append("missing ### Generalistic table under ## Gates")

    deterministic_ids = {row.gate_id for row in doc.deterministic_rows}
    checks = _deterministic(doc)
    for gate_id, _label in DETERMINISTIC_GATES:
        ok, detail = checks[gate_id]
        if doc.saw_deterministic_table and gate_id not in deterministic_ids:
            ok = False
            detail = f"{detail}; Gates table is missing {gate_id}"
        report.results.append(GateResult(gate_id, ok, detail))

    if doc.saw_generalistic_table:
        report.results.extend(_generalistic(doc))
    return report


def format_report(report: LintReport) -> str:
    target = report.path or "<memory>"
    lines = [f"gate-lint: {'PASS' if report.ok else 'FAIL'} {target}"]
    for hole in report.holes:
        lines.append(f"  HOLE {hole}")
    for result in report.results:
        flag = "PASS" if result.ok else "FAIL"
        lines.append(f"  {flag} {result.gate_id} {result.detail}")
    if report.ok:
        deterministic = [r for r in report.results if r.gate_id.startswith("D-")]
        lines.append(
            f"all {len(deterministic)} deterministic gates passed; start reaches goal"
        )
    else:
        failed = sum(1 for result in report.results if not result.ok)
        lines.append(f"{failed} gate(s) failed, {len(report.holes)} hole(s)")
    return "\n".join(lines) + "\n"


def _deterministic(doc: MasterDoc) -> dict[str, tuple[bool, str]]:
    rooms = doc.rooms
    start_id = _str_fm(doc, "start_room_id")
    goal_id = _str_fm(doc, "goal_room_id")
    start_room = doc.room(start_id) if start_id else None
    goal_room = doc.room(goal_id) if goal_id else None
    graph, paired, exit_problems, meetings = _door_graph(rooms)
    rooms_by_id = {room.id: room for room in rooms}

    results = {
        "D-MAP-01": _map_count(rooms),
        "D-MAP-02": _frame(doc, start_room, goal_room),
        "D-MAP-03": _floors(rooms),
        "D-ROOM-01": _room_ids(rooms),
        "D-ROOM-02": _room_sizes(rooms),
        "D-ROOM-03": _no_overlap(rooms),
        "D-ROOM-04": _heights(rooms),
        "D-EXIT-01": _exit_counts(start_id, goal_id, start_room, goal_room, graph, paired),
        "D-EXIT-02": _exit_alignment(exit_problems, meetings),
        "D-EXIT-03": _connectivity(start_id, goal_id, graph),
        "D-START-01": _ref_exists("start_room_id", start_id, start_room),
        "D-START-02": _start_point(doc, start_room),
        "D-GOAL-01": _ref_exists("goal_room_id", goal_id, goal_room),
        "D-GOAL-02": _win(doc),
        "D-ENEMY-01": _grunt_count(doc.enemies),
        "D-ENEMY-02": _grunt_placement(doc.enemies, start_id, goal_id, graph, rooms_by_id),
        "D-ITEM-01": _item_bounds(doc.items, rooms),
        "D-PAL-01": _palette(doc, rooms),
        "D-ID-01": _unique_ids(doc),
        "D-SAFE-01": _safe_target(doc),
    }
    missing = [gate_id for gate_id, _label in DETERMINISTIC_GATES if gate_id not in results]
    if missing:
        raise RuntimeError(f"lint is missing results for {missing}")
    return results


def _map_count(rooms: list[Room]) -> tuple[bool, str]:
    count = len(rooms)
    if count >= MIN_ROOMS:
        return True, f"room_count={count} (>= {MIN_ROOMS})"
    return False, f"room_count={count}; need >= {MIN_ROOMS} (start room and goal room)"


def _frame(doc: MasterDoc, start: Room | None, goal: Room | None) -> tuple[bool, str]:
    units = _str_fm(doc, "units")
    growth = _str_fm(doc, "growth_axis")
    problems: list[str] = []
    if units != UNITS:
        problems.append(f"units={units!r}; need {UNITS}")
    if growth != GROWTH_AXIS:
        problems.append(f"growth_axis={growth!r}; need {GROWTH_AXIS} (map grows toward -Z)")
    if start is None or goal is None or start.center is None or goal.center is None:
        problems.append("cannot check -Z growth until start and goal rooms have centers")
    elif not (goal.center[1] < start.center[1]):
        problems.append(
            f"goal z={fmt_num(goal.center[1])} is not toward -Z from "
            f"start z={fmt_num(start.center[1])}"
        )
    if problems:
        return False, "; ".join(problems)
    assert start is not None and start.center is not None
    assert goal is not None and goal.center is not None
    return True, (
        f"units=meters, growth=-Z, start z={fmt_num(start.center[1])} "
        f"to goal z={fmt_num(goal.center[1])}"
    )


def _floors(rooms: list[Room]) -> tuple[bool, str]:
    if not rooms:
        return False, "no rooms to check floor_y"
    problems: list[str] = []
    for room in rooms:
        if room.floor_y is None:
            problems.append(f"{room.id} is missing floor_y")
            continue
        if abs(room.floor_y - BEGINNER_FLOOR_Y) <= 1e-6:
            continue
        if any(abs(room.floor_y - allowed) <= 1e-6 for allowed in SCHEMA_FLOOR_YS):
            problems.append(
                f"{room.id} floor_y={fmt_num(room.floor_y)}; beginner path v1 requires "
                f"{fmt_num(BEGINNER_FLOOR_Y)} (3.2 needs stairs or an elevator, which are out of scope)"
            )
        else:
            problems.append(
                f"{room.id} floor_y={fmt_num(room.floor_y)} is not a WORLD_SCHEMA floor "
                "(0.0 or 3.2), and beginner v1 requires 0.0"
            )
    if problems:
        return False, "; ".join(problems)
    listed = ", ".join(fmt_num(room.floor_y or 0.0) for room in rooms)
    return True, f"floor_y {listed}"


def _room_ids(rooms: list[Room]) -> tuple[bool, str]:
    if not rooms:
        return False, "no rooms"
    problems: list[str] = []
    seen: set[str] = set()
    for room in rooms:
        if not room.id or not _SNAKE.match(room.id):
            problems.append(f"{room.id!r} is not snake_case")
        if room.id in seen:
            problems.append(f"{room.id} is duplicated")
        seen.add(room.id)
    if problems:
        return False, "; ".join(problems)
    return True, "ids " + ", ".join(room.id for room in rooms)


def _room_sizes(rooms: list[Room]) -> tuple[bool, str]:
    if not rooms:
        return False, "no rooms"
    problems: list[str] = []
    for room in rooms:
        if room.size is None:
            problems.append(f"{room.id} is missing size")
            continue
        width, depth = room.size
        if width < MIN_WIDTH or depth < MIN_DEPTH:
            problems.append(
                f"{room.id} size {fmt_num(width)}x{fmt_num(depth)} m; "
                f"need width >= {fmt_num(MIN_WIDTH)} and depth >= {fmt_num(MIN_DEPTH)}"
            )
    if problems:
        return False, "; ".join(problems)
    listed = ", ".join(
        f"{room.id} {fmt_num(room.size[0])}x{fmt_num(room.size[1])}"
        for room in rooms
        if room.size is not None
    )
    return True, listed


def _no_overlap(rooms: list[Room]) -> tuple[bool, str]:
    boxed = [(room, room.bounds()) for room in rooms]
    if sum(1 for _room, box in boxed if box is not None) < 2:
        return False, "need at least two rooms with center and size"
    problems: list[str] = []
    for index, (left, left_box) in enumerate(boxed):
        if left_box is None:
            problems.append(f"{left.id} is missing center or size")
            continue
        for right, right_box in boxed[index + 1 :]:
            if right_box is None:
                continue
            overlap_x = _interval_overlap((left_box[0], left_box[1]), (right_box[0], right_box[1]))
            overlap_z = _interval_overlap((left_box[2], left_box[3]), (right_box[2], right_box[3]))
            if overlap_x > OVERLAP_EPS and overlap_z > OVERLAP_EPS:
                problems.append(
                    f"{left.id} and {right.id} interiors overlap "
                    f"({overlap_x:.2f} m on x, {overlap_z:.2f} m on z); "
                    "a shared door edge may touch, interiors may not"
                )
    if problems:
        return False, "; ".join(problems)
    return True, "no interior overlap"


def _heights(rooms: list[Room]) -> tuple[bool, str]:
    if not rooms:
        return False, "no rooms"
    problems: list[str] = []
    shown: list[str] = []
    for room in rooms:
        height = DEFAULT_HEIGHT if room.height is None else room.height
        if height < MIN_HEIGHT:
            problems.append(
                f"{room.id} height {fmt_num(height)} m; need >= {fmt_num(MIN_HEIGHT)}"
            )
        else:
            label = f"{fmt_num(height)} (default)" if room.height is None else fmt_num(height)
            shown.append(f"{room.id} {label}")
    if problems:
        return False, "; ".join(problems)
    return True, ", ".join(shown)


def _exit_counts(
    start_id: str,
    goal_id: str,
    start: Room | None,
    goal: Room | None,
    graph: dict[str, list[str]],
    paired: dict[str, set[str]],
) -> tuple[bool, str]:
    problems: list[str] = []
    if start is None:
        problems.append(f"start room {start_id or '(missing)'} has no forward exit to count")
    elif len(paired.get(start.id, ())) < 1:
        problems.append(f"{start.id} has no forward exit (need a door or open side that meets a neighbor)")
    if goal is None:
        problems.append(f"goal room {goal_id or '(missing)'} has no entry to count")
    elif len(paired.get(goal.id, ())) < 1:
        problems.append(f"{goal.id} has no entry (need a door or open side that meets a neighbor)")
    if start is not None and goal is not None and start.id != goal.id and start.id in graph:
        for transit_id in sorted(_rooms_on_simple_paths(graph, start.id, goal.id) - {start.id, goal.id}):
            exits = len(paired.get(transit_id, ()))
            if exits < 2:
                problems.append(
                    f"{transit_id} is on the path from start to goal but has {exits} "
                    "connected exit(s); a mid-path room needs >= 2"
                )
    if problems:
        return False, "; ".join(problems)
    if start is not None and goal is not None and start.id == goal.id:
        extra = "start and goal are the same room"
    elif start is not None and goal is not None and start.id in graph:
        transit = _rooms_on_simple_paths(graph, start.id, goal.id) - {start.id, goal.id}
        extra = (
            "no mid-path rooms"
            if not transit
            else "mid-path " + ", ".join(sorted(transit)) + " each have >= 2 exits"
        )
    else:
        extra = "no path rooms"
    start_n = len(paired.get(start.id, ())) if start else 0
    goal_n = len(paired.get(goal.id, ())) if goal else 0
    return True, (
        f"{start.id if start else start_id} has {start_n} forward exit(s); "
        f"{goal.id if goal else goal_id} has {goal_n} entry; {extra}"
    )


def _exit_alignment(problems: list[str], meetings: list[str]) -> tuple[bool, str]:
    if problems:
        return False, "; ".join(problems)
    if not meetings:
        return False, "no door or open side meets a neighbor"
    return True, "; ".join(meetings)


def _connectivity(start_id: str, goal_id: str, graph: dict[str, list[str]]) -> tuple[bool, str]:
    if not start_id or not goal_id:
        return False, "start_room_id and goal_room_id are required before a path can be checked"
    if start_id == goal_id:
        return False, f"start and goal are both {start_id}; that is not a route"
    if start_id not in graph or goal_id not in graph:
        return False, f"no door-aligned path from {start_id} to {goal_id}"
    path = _shortest_path(graph, start_id, goal_id)
    if path is None or len(path) < 2:
        return False, f"no door-aligned path from {start_id} to {goal_id}"
    return True, "path " + " -> ".join(path)


def _ref_exists(field_name: str, room_id: str, room: Room | None) -> tuple[bool, str]:
    if not room_id:
        return False, f"{field_name} is missing"
    if room is None:
        return False, f"{field_name}={room_id} does not match a room"
    return True, room_id


def _start_point(doc: MasterDoc, start: Room | None) -> tuple[bool, str]:
    raw = doc.fm("start_pos")
    if raw == "auto":
        if start is None:
            return False, "start_pos is auto but start_room_id does not match a room"
        return True, f"auto (code owns the spawn) in {start.id}"
    pos = _as_point(raw)
    if pos is None:
        return False, "start_pos must be [x, y, z] or auto"
    if start is None:
        return False, "start_pos is set but start_room_id does not match a room"
    return _point_in_room(
        pos,
        start,
        SPAWN_INSET,
        SPAWN_Y_OFFSET,
        "start_pos",
        y_note="eye height",
    )


def _win(doc: MasterDoc) -> tuple[bool, str]:
    win = _str_fm(doc, "win")
    if win == WIN_RULE:
        return True, WIN_RULE
    return False, f"win={win!r}; home_fps beginner path requires {WIN_RULE}"


def _grunt_count(enemies: list[Spawn]) -> tuple[bool, str]:
    problems = [f"{enemy.id} kind={enemy.kind}; only grunt is allowed" for enemy in enemies if enemy.kind != "grunt"]
    grunts = [enemy for enemy in enemies if enemy.kind == "grunt"]
    if len(grunts) < 1:
        problems.append("grunt_count=0; need >= 1")
    if problems:
        return False, "; ".join(problems)
    return True, f"grunt_count={len(grunts)}"


def _grunt_placement(
    enemies: list[Spawn],
    start_id: str,
    goal_id: str,
    graph: dict[str, list[str]],
    rooms_by_id: dict[str, Room],
) -> tuple[bool, str]:
    grunts = [enemy for enemy in enemies if enemy.kind == "grunt"]
    if not grunts:
        return False, "no grunt to place"
    problems: list[str] = []
    for grunt in grunts:
        if grunt.pos_auto or grunt.pos is None:
            problems.append(f"{grunt.id} pos is auto; need [x, y, z] inside {grunt.room or 'its room'}")
            continue
        room_obj = rooms_by_id.get(grunt.room)
        if room_obj is None:
            problems.append(f"{grunt.id} room={grunt.room or '(missing)'} does not exist")
            continue
        ok, detail = _point_in_room(
            grunt.pos, room_obj, GRUNT_INSET, GRUNT_Y_OFFSET, grunt.id, y_note="floor_y + 0.85"
        )
        if not ok:
            problems.append(detail)
    on_path: set[str] = set()
    if start_id and goal_id and start_id in graph and goal_id in graph and start_id != goal_id:
        on_path = _rooms_on_simple_paths(graph, start_id, goal_id)
    # A grunt standing in the goal room counts even when the door graph is broken.
    # Connectivity is D-EXIT-03. "On the path" covers a grunt in the start or a transit room.
    if not any(_grunt_covers_path(grunt, goal_id, on_path) for grunt in grunts):
        where = ", ".join(f"{grunt.id} in {grunt.room}" for grunt in grunts)
        problems.append(
            f"no grunt is in the goal or on a start->goal path ({where or 'none placed'})"
        )
    if problems:
        return False, "; ".join(problems)
    where = ", ".join(f"{grunt.id} in {grunt.room}" for grunt in grunts)
    return True, where


def _grunt_covers_path(grunt: Spawn, goal_id: str, on_path: set[str]) -> bool:
    if goal_id and grunt.room == goal_id:
        return True
    return bool(grunt.room) and grunt.room in on_path


def _item_bounds(items: list[Spawn], rooms: list[Room]) -> tuple[bool, str]:
    if not items:
        return True, "no pickups (allowed)"
    by_id = {room.id: room for room in rooms}
    problems: list[str] = []
    for item in items:
        if item.kind != "health_pack":
            problems.append(f"{item.id} kind={item.kind}; only health_pack is allowed")
            continue
        if item.pos_auto or item.pos is None:
            problems.append(f"{item.id} pos is auto; need [x, y, z] inside {item.room or 'its room'}")
            continue
        room = by_id.get(item.room)
        if room is None:
            problems.append(f"{item.id} room={item.room or '(missing)'} does not exist")
            continue
        ok, detail = _point_in_room(item.pos, room, ITEM_INSET, ITEM_Y_OFFSET, item.id, y_note="floor_y + 0.45")
        if not ok:
            problems.append(detail)
    if problems:
        return False, "; ".join(problems)
    where = ", ".join(f"{item.id} in {item.room}" for item in items)
    return True, where


def _palette(doc: MasterDoc, rooms: list[Room]) -> tuple[bool, str]:
    problems: list[str] = []
    for name in doc.palette_dupes:
        problems.append(f"palette key {name} is listed more than once")
    for name, rgb in doc.palette.items():
        if not _SNAKE.match(name):
            problems.append(f"palette key {name!r} is not snake_case")
        for channel in rgb:
            if channel < -1e-6 or channel > 1.0 + 1e-6:
                problems.append(f"palette {name} channel {channel} is outside 0..1")
                break
    for room in rooms:
        if not room.color:
            problems.append(f"{room.id} is missing color")
        elif room.color not in doc.palette:
            problems.append(f"{room.id} color {room.color} is not in the palette")
    if problems:
        return False, "; ".join(problems)
    if not doc.palette:
        return False, "palette is empty"
    return True, "colors " + ", ".join(doc.palette)


def _unique_ids(doc: MasterDoc) -> tuple[bool, str]:
    problems: list[str] = []
    seen: dict[str, str] = {}
    rows: list[tuple[str, str]] = [("room", room.id) for room in doc.rooms]
    rows.extend(("enemy", enemy.id) for enemy in doc.enemies)
    rows.extend(("item", item.id) for item in doc.items)
    for kind, ident in rows:
        if not ident or not _SNAKE.match(ident):
            problems.append(f"{kind} id {ident!r} is not snake_case")
            continue
        if ident in seen:
            problems.append(f"{ident} is used as both {seen[ident]} and {kind}")
        else:
            seen[ident] = kind
    if problems:
        return False, "; ".join(problems)
    return True, f"{len(seen)} unique ids"


def _safe_target(doc: MasterDoc) -> tuple[bool, str]:
    target = _str_fm(doc, "target_map")
    problems: list[str] = []
    if target != TARGET_MAP:
        shown = target or "(missing)"
        problems.append(
            f"target_map={shown}; beginner path requires {TARGET_MAP} "
            "and must not write the live small_bunker"
        )
    ops_blob = json.dumps([step.ops_hint for step in doc.steps])
    if "small_bunker" in ops_blob or "allow-apply" in ops_blob or "allow_apply" in ops_blob:
        problems.append("a build step ops_hint names small_bunker or allow-apply")
    if problems:
        return False, "; ".join(problems)
    return True, TARGET_MAP


def _generalistic(doc: MasterDoc) -> list[GateResult]:
    rows = {row.gate_id: row for row in doc.generalistic_rows}
    results: list[GateResult] = []
    for gate_id, field_name in GENERALISTIC_GATES:
        row = rows.get(gate_id)
        if row is None:
            results.append(GateResult(gate_id, False, f"Gates table is missing {gate_id}"))
            continue
        flag = row.cells[-1].strip().strip("`").lower() if row.cells else ""
        if flag not in HUMAN_TOUCH:
            results.append(
                GateResult(
                    gate_id,
                    False,
                    f"human_touch={flag!r}; need one of {', '.join(HUMAN_TOUCH)}",
                )
            )
        else:
            results.append(GateResult(gate_id, True, f"{field_name} human_touch={flag}"))
    return results


def _door_graph(
    rooms: list[Room],
) -> tuple[dict[str, list[str]], dict[str, set[str]], list[str], list[str]]:
    """Return adjacency, paired sides, unpaired-door problems, and meeting notes."""
    graph: dict[str, list[str]] = {room.id: [] for room in rooms}
    paired: dict[str, set[str]] = {room.id: set() for room in rooms}
    problems: list[str] = []
    meetings: list[str] = []

    for room in rooms:
        if room.sides is None or room.bounds() is None:
            if room.sides is None:
                problems.append(f"{room.id} sides are missing or unreadable")
            else:
                problems.append(f"{room.id} needs center and size before its doors can be checked")
            continue
        for side, kind in room.sides.items():
            if kind not in ("door", "open"):
                continue
            if side in paired[room.id]:
                continue
            match = _find_neighbor(room, side, rooms)
            if match is None:
                edge = _edge_coord(room, side)
                axis = "z" if side.endswith("z") else "x"
                problems.append(
                    f"{room.id} {side} {kind} at {axis}={fmt_num(edge)} "
                    "does not meet a neighbor door or open side"
                )
                continue
            other, other_side, _overlap = match
            paired[room.id].add(side)
            paired[other.id].add(other_side)
            if other.id not in graph[room.id]:
                graph[room.id].append(other.id)
            if room.id not in graph[other.id]:
                graph[other.id].append(room.id)
            meetings.append(f"{room.id}.{side} meets {other.id}.{other_side}")
    return graph, paired, problems, meetings


def _find_neighbor(
    room: Room, side: str, rooms: list[Room]
) -> tuple[Room, str, float] | None:
    best: tuple[Room, str, float] | None = None
    opening = _clipped_opening(room, side)
    edge = _edge_coord(room, side)
    opposite = OPPOSITE_SIDE[side]
    for other in rooms:
        if other.id == room.id or other.sides is None or other.bounds() is None:
            continue
        if other.sides.get(opposite) not in ("door", "open"):
            continue
        if abs(_edge_coord(other, opposite) - edge) > EDGE_EPS:
            continue
        overlap = _interval_overlap(opening, _clipped_opening(other, opposite))
        if best is None or overlap > best[2]:
            best = (other, opposite, overlap)
    if best is None or best[2] < MIN_DOOR_OVERLAP:
        return None
    return best


def _clipped_opening(room: Room, side: str) -> tuple[float, float]:
    assert room.sides is not None and room.center is not None
    box = room.bounds()
    assert box is not None
    x0, x1, z0, z1 = box
    kind = room.sides[side]
    if side in ("plus_z", "minus_z"):
        span = (x0, x1)
        if kind == "open":
            opening = span
        else:
            half = DOOR_W_Z / 2.0
            opening = (room.center[0] - half, room.center[0] + half)
    else:
        span = (z0, z1)
        if kind == "open":
            opening = span
        else:
            half = DOOR_W_X / 2.0
            opening = (room.center[1] - half, room.center[1] + half)
    return (max(opening[0], span[0]), min(opening[1], span[1]))


def _edge_coord(room: Room, side: str) -> float:
    box = room.bounds()
    assert box is not None
    x0, x1, z0, z1 = box
    return {"plus_z": z1, "minus_z": z0, "plus_x": x1, "minus_x": x0}[side]


def _interval_overlap(left: tuple[float, float], right: tuple[float, float]) -> float:
    return min(left[1], right[1]) - max(left[0], right[0])


def _shortest_path(graph: dict[str, list[str]], start: str, goal: str) -> list[str] | None:
    previous: dict[str, str | None] = {start: None}
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        if current == goal:
            break
        for nxt in graph.get(current, []):
            if nxt not in previous:
                previous[nxt] = current
                queue.append(nxt)
    if goal not in previous:
        return None
    path: list[str] = []
    cursor: str | None = goal
    while cursor is not None:
        path.append(cursor)
        cursor = previous[cursor]
    path.reverse()
    return path


def _rooms_on_simple_paths(graph: dict[str, list[str]], start: str, goal: str) -> set[str]:
    found: set[str] = set()

    def walk(node: str, seen: set[str]) -> None:
        if node == goal:
            found.update(seen)
            return
        for nxt in graph.get(node, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            walk(nxt, seen)
            seen.remove(nxt)

    if start not in graph or goal not in graph:
        return set()
    walk(start, {start})
    return found


def _point_in_room(
    pos: tuple[float, float, float],
    room: Room,
    inset: float,
    y_offset: float,
    label: str,
    y_note: str,
) -> tuple[bool, str]:
    box = room.bounds()
    if box is None or room.floor_y is None:
        return False, f"{label} cannot be checked because {room.id} is missing bounds or floor_y"
    x0, x1, z0, z1 = box
    x, y, z = pos
    problems: list[str] = []
    if x < x0 - 1e-6 or x > x1 + 1e-6 or z < z0 - 1e-6 or z > z1 + 1e-6:
        problems.append(
            f"{label} ({fmt_num(x)}, {fmt_num(z)}) is outside {room.id} "
            f"(x {fmt_num(x0)}..{fmt_num(x1)}, z {fmt_num(z0)}..{fmt_num(z1)})"
        )
    else:
        inset_x = min(x - x0, x1 - x)
        inset_z = min(z - z0, z1 - z)
        if inset_x + 1e-6 < inset or inset_z + 1e-6 < inset:
            problems.append(
                f"{label} ({fmt_num(x)}, {fmt_num(z)}) in {room.id} is closer than "
                f"{fmt_num(inset)} m to a wall"
            )
    expected_y = room.floor_y + y_offset
    if abs(y - expected_y) > Y_TOL:
        problems.append(
            f"{label} y={fmt_num(y)}; {y_note} wants {fmt_num(expected_y)} "
            f"(floor_y + {fmt_num(y_offset)})"
        )
    if problems:
        return False, "; ".join(problems)
    return True, f"{label} inside {room.id}"


def _as_point(raw: object) -> tuple[float, float, float] | None:
    if not isinstance(raw, list) or len(raw) != 3:
        return None
    if not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in raw):
        return None
    return (float(raw[0]), float(raw[1]), float(raw[2]))


def _str_fm(doc: MasterDoc, key: str) -> str:
    value = doc.fm(key)
    if value is None:
        return ""
    return str(value)
