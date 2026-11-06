"""Parsed MASTER_GAME.md, plus the spec the beginner-path generator fills."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Room:
    id: str
    purpose: str | None = None
    center: tuple[float, float] | None = None
    size: tuple[float, float] | None = None
    height: float | None = None
    floor_y: float | None = None
    color: str | None = None
    look: str | None = None
    sides: dict[str, str] | None = None
    connections: list[tuple[str, str]] = field(default_factory=list)
    line: int = 0

    def bounds(self) -> tuple[float, float, float, float] | None:
        """Return x_min, x_max, z_min, z_max. None when center or size is missing."""
        if self.center is None or self.size is None:
            return None
        cx, cz = self.center
        width, depth = self.size
        return (cx - width / 2.0, cx + width / 2.0, cz - depth / 2.0, cz + depth / 2.0)


@dataclass
class Spawn:
    id: str
    kind: str
    room: str
    pos: tuple[float, float, float] | None
    pos_auto: bool
    tier: str
    notes: str
    line: int = 0


@dataclass
class BuildStep:
    id: str
    title: str
    section_refs: list[str] = field(default_factory=list)
    action: str = ""
    instruction: str = ""
    acceptance: list[str] = field(default_factory=list)
    replaces: object = None
    ops_hint: object = None
    line: int = 0


@dataclass
class GateRow:
    gate_id: str
    cells: list[str]
    line: int = 0


@dataclass
class MasterDoc:
    text: str
    frontmatter: dict[str, object] = field(default_factory=dict)
    rooms: list[Room] = field(default_factory=list)
    enemies: list[Spawn] = field(default_factory=list)
    items: list[Spawn] = field(default_factory=list)
    palette: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    palette_dupes: list[str] = field(default_factory=list)
    deterministic_rows: list[GateRow] = field(default_factory=list)
    generalistic_rows: list[GateRow] = field(default_factory=list)
    steps: list[BuildStep] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    saw_gates: bool = False
    saw_deterministic_table: bool = False
    saw_generalistic_table: bool = False

    def fm(self, key: str, default: object = None) -> object:
        return self.frontmatter.get(key, default)

    def room(self, room_id: str) -> Room | None:
        for room in self.rooms:
            if room.id == room_id:
                return room
        return None


@dataclass
class GeneralisticFill:
    gate_id: str
    field: str
    default: str
    human_touch: str


@dataclass
class GameSpec:
    """In-memory beginner path. ``render_master`` turns this into MASTER_GAME.md."""

    game_id: str
    title: str
    created: str
    mode: str
    target: str
    target_map: str
    win: str
    start_room_id: str
    goal_room_id: str
    start_pos: tuple[float, float, float]
    units: str
    growth_axis: str
    vision: str
    fantasy: str
    lose: str
    mood: str
    rooms: list[Room]
    enemies: list[Spawn]
    items: list[Spawn]
    palette: list[tuple[str, tuple[float, float, float]]]
    tiers: list[tuple[str, str, str, str, str]]
    progression: list[str]
    constraints: list[str]
    generalistic: list[GeneralisticFill]

    def room(self, room_id: str) -> Room:
        for room in self.rooms:
            if room.id == room_id:
                return room
        raise KeyError(room_id)
