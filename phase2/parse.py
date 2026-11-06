"""Parse the Phase 2 MASTER_GAME.md shape into a MasterDoc.

The format follows the demo_corridor master plus a ## Gates section.
Geometry in the room blocks, spawn tables, and frontmatter is what gate-lint
checks. The Status column in ## Gates is not trusted.
"""

from __future__ import annotations

import json
import re

from phase2.model import BuildStep, GateRow, MasterDoc, Room, Spawn
from phase2.schema import SIDE_KINDS, SIDE_NAMES

_ROOM_RE = re.compile(r"^### Room: (\S+)\s*$")
_STEP_RE = re.compile(r"^### (S\d+): (.+?)\s*$")
_FIELD_RE = re.compile(r"^- ([a-z_]+):\s*(.*)$")
_PALETTE_RE = re.compile(r"^- ([A-Za-z0-9_]+):\s*(\[.*\])\s*$")
_SIDES_RE = re.compile(
    r"^\{plus_z:\s*(wall|door|open),\s*minus_z:\s*(wall|door|open),\s*"
    r"plus_x:\s*(wall|door|open),\s*minus_x:\s*(wall|door|open)\}$"
)
_CONN_RE = re.compile(r"^([A-Za-z0-9_]+) via (plus_z|minus_z|plus_x|minus_x)$")


def parse_master(text: str) -> MasterDoc:
    text = text.replace("\r\n", "\n")
    doc = MasterDoc(text=text)
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if not lines or lines[0].strip() != "---":
        doc.errors.append("line 1: MASTER needs frontmatter that opens with ---")
        return doc
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        doc.errors.append("frontmatter has no closing ---")
        return doc
    _read_frontmatter(doc, lines[1:end], start_line=2)

    section = ""
    mode = "prose"
    room: Room | None = None
    step: BuildStep | None = None

    def close_open() -> None:
        nonlocal room, step, mode
        if room is not None:
            doc.rooms.append(room)
            room = None
        if step is not None:
            doc.steps.append(step)
            step = None
        if mode in ("room", "step"):
            mode = "prose"

    for number, line in enumerate(lines[end + 1 :], start=end + 2):
        room_match = _ROOM_RE.match(line)
        step_match = _STEP_RE.match(line)
        if room_match or step_match or line.startswith("## "):
            close_open()

        if room_match:
            room = Room(id=room_match.group(1), line=number)
            mode = "room"
            continue
        if step_match:
            step = BuildStep(id=step_match.group(1), title=step_match.group(2).strip(), line=number)
            mode = "step"
            continue
        if line.startswith("## "):
            section = line[3:].strip()
            if section == "Gates":
                doc.saw_gates = True
                mode = "prose"
            elif section == "Palette":
                mode = "palette"
            elif section == "Enemies & spawns":
                mode = "table-enemies"
            elif section == "Items / pickups":
                mode = "table-items"
            else:
                mode = "prose"
            continue
        if line.startswith("### "):
            subsection = line[4:].strip()
            if section == "Gates" and subsection == "Deterministic":
                doc.saw_deterministic_table = True
                mode = "table-det"
            elif section == "Gates" and subsection == "Generalistic":
                doc.saw_generalistic_table = True
                mode = "table-gen"
            else:
                mode = "prose"
            continue

        if mode == "room" and room is not None:
            _read_room_field(doc, room, line, number)
        elif mode == "step" and step is not None:
            _read_step_line(doc, step, line, number)
        elif mode == "palette":
            _read_palette_line(doc, line, number)
        elif mode == "table-enemies" and line.startswith("|"):
            _read_spawn_row(doc, doc.enemies, line, number)
        elif mode == "table-items" and line.startswith("|"):
            _read_spawn_row(doc, doc.items, line, number)
        elif mode == "table-det" and line.startswith("|"):
            _read_gate_row(doc.deterministic_rows, line, number)
        elif mode == "table-gen" and line.startswith("|"):
            _read_gate_row(doc.generalistic_rows, line, number)

    close_open()
    return doc


def _read_frontmatter(doc: MasterDoc, lines: list[str], start_line: int) -> None:
    for offset, line in enumerate(lines):
        if not line.strip():
            continue
        if ":" not in line:
            doc.errors.append(f"line {start_line + offset}: bad frontmatter line {line!r}")
            continue
        key, raw = line.split(":", 1)
        doc.frontmatter[key.strip()] = _parse_scalar(raw.strip())


def _parse_scalar(raw: str) -> object:
    if raw == "null":
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw.startswith("[") or raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _read_room_field(doc: MasterDoc, room: Room, line: str, number: int) -> None:
    match = _FIELD_RE.match(line)
    if not match:
        return
    key, raw = match.group(1), match.group(2).strip()
    if key == "purpose":
        room.purpose = raw
    elif key == "center":
        room.center = _pair(doc, raw, number, f"room {room.id} center")
    elif key == "size":
        room.size = _pair(doc, raw, number, f"room {room.id} size")
    elif key == "height":
        room.height = _number(doc, raw, number, f"room {room.id} height")
    elif key == "floor_y":
        room.floor_y = _number(doc, raw, number, f"room {room.id} floor_y")
    elif key == "color":
        room.color = raw
    elif key == "look":
        room.look = raw
    elif key == "sides":
        room.sides = _sides(doc, raw, number, room.id)
    elif key == "connections":
        room.connections = _connections(doc, raw, number, room.id)


def _pair(doc: MasterDoc, raw: str, number: int, label: str) -> tuple[float, float] | None:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        doc.errors.append(f"line {number}: {label} is not a JSON pair")
        return None
    if not isinstance(value, list) or len(value) != 2 or not all(_is_num(v) for v in value):
        doc.errors.append(f"line {number}: {label} must be [x, z]")
        return None
    return (float(value[0]), float(value[1]))


def _number(doc: MasterDoc, raw: str, number: int, label: str) -> float | None:
    try:
        return float(raw)
    except ValueError:
        doc.errors.append(f"line {number}: {label} is not a number")
        return None


def _sides(doc: MasterDoc, raw: str, number: int, room_id: str) -> dict[str, str] | None:
    match = _SIDES_RE.match(raw)
    if not match:
        doc.errors.append(
            f"line {number}: room {room_id} sides must be "
            "{{plus_z: wall|door|open, minus_z: ..., plus_x: ..., minus_x: ...}}"
        )
        return None
    sides = dict(zip(SIDE_NAMES, match.groups(), strict=True))
    for kind in sides.values():
        if kind not in SIDE_KINDS:
            doc.errors.append(f"line {number}: room {room_id} has unknown side {kind}")
            return None
    return sides


def _connections(doc: MasterDoc, raw: str, number: int, room_id: str) -> list[tuple[str, str]]:
    body = raw.strip()
    if body.startswith("[") and body.endswith("]"):
        body = body[1:-1].strip()
    if not body:
        return []
    found: list[tuple[str, str]] = []
    for part in body.split(","):
        part = part.strip()
        match = _CONN_RE.match(part)
        if not match:
            doc.errors.append(
                f"line {number}: room {room_id} connection {part!r} "
                "must look like 'goal_fight via minus_z'"
            )
            continue
        found.append((match.group(1), match.group(2)))
    return found


def _read_step_line(doc: MasterDoc, step: BuildStep, line: str, number: int) -> None:
    if line.startswith("  - "):
        step.acceptance.append(line[4:].strip())
        return
    match = _FIELD_RE.match(line)
    if not match:
        return
    key, raw = match.group(1), match.group(2).strip()
    if key == "section_refs":
        step.section_refs = _string_list(doc, raw, number, f"{step.id} section_refs")
    elif key == "action":
        step.action = raw
    elif key == "instruction":
        step.instruction = raw
    elif key == "acceptance":
        if raw:
            step.acceptance.append(raw)
    elif key == "replaces":
        step.replaces = _json_or_null(doc, raw, number, f"{step.id} replaces")
    elif key == "ops_hint":
        step.ops_hint = _json_or_null(doc, raw, number, f"{step.id} ops_hint")


def _string_list(doc: MasterDoc, raw: str, number: int, label: str) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        doc.errors.append(f"line {number}: {label} is not a JSON list")
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        doc.errors.append(f"line {number}: {label} must be a list of strings")
        return []
    return list(value)


def _json_or_null(doc: MasterDoc, raw: str, number: int, label: str) -> object:
    if raw == "null":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        doc.errors.append(f"line {number}: {label} is not JSON or null")
        return None


def _read_palette_line(doc: MasterDoc, line: str, number: int) -> None:
    if not line.startswith("- "):
        return
    match = _PALETTE_RE.match(line)
    if not match:
        doc.errors.append(f"line {number}: palette entry must look like '- name: [r, g, b]'")
        return
    name, raw = match.group(1), match.group(2)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        doc.errors.append(f"line {number}: palette {name} RGB is not JSON")
        return
    if (
        not isinstance(value, list)
        or len(value) != 3
        or not all(_is_num(channel) for channel in value)
    ):
        doc.errors.append(f"line {number}: palette {name} must be [r, g, b]")
        return
    rgb = (float(value[0]), float(value[1]), float(value[2]))
    if name in doc.palette:
        doc.palette_dupes.append(name)
    doc.palette[name] = rgb


def _read_spawn_row(doc: MasterDoc, dest: list[Spawn], line: str, number: int) -> None:
    cells = _cells(line)
    if cells is None or _skip_table_row(cells, "id"):
        return
    if len(cells) < 6:
        doc.errors.append(f"line {number}: spawn table needs id, kind, room, pos, tier, notes")
        return
    pos_raw = cells[3].strip().strip('"')
    pos: tuple[float, float, float] | None = None
    pos_auto = pos_raw == "auto"
    if not pos_auto:
        try:
            value = json.loads(pos_raw)
        except json.JSONDecodeError:
            doc.errors.append(f"line {number}: pos {pos_raw!r} is not [x, y, z] or auto")
            return
        if not isinstance(value, list) or len(value) != 3 or not all(_is_num(v) for v in value):
            doc.errors.append(f"line {number}: pos must be [x, y, z] or auto")
            return
        pos = (float(value[0]), float(value[1]), float(value[2]))
    dest.append(
        Spawn(
            id=cells[0],
            kind=cells[1],
            room=cells[2],
            pos=pos,
            pos_auto=pos_auto,
            tier=cells[4],
            notes=cells[5],
            line=number,
        )
    )


def _read_gate_row(dest: list[GateRow], line: str, number: int) -> None:
    cells = _cells(line)
    if cells is None or _skip_table_row(cells, "Gate ID"):
        return
    gate_id = cells[0].strip().strip("*").strip()
    if not gate_id:
        return
    dest.append(GateRow(gate_id=gate_id, cells=cells, line=number))


def _cells(line: str) -> list[str] | None:
    if not line.startswith("|"):
        return None
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _skip_table_row(cells: list[str], header: str) -> bool:
    if not cells:
        return True
    if cells[0] == header:
        return True
    return all(cell and set(cell) <= set("-: ") for cell in cells)


def _is_num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
