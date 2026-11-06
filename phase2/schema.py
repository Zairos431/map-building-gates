"""Minimum viable numbers shared by the beginner-path generator and gate-lint.

Values follow ideation/MAP_BUILDING_GATES_PHASE1.md and Home FPS WORLD_SCHEMA:
meters, +Y up, map grows toward -Z, Z doors 3.0 m, X doors 2.2 m.
"""

from __future__ import annotations

MIN_ROOMS = 2
MIN_WIDTH = 4.0
MIN_DEPTH = 4.0
MIN_HEIGHT = 2.5
DEFAULT_HEIGHT = 3.0
BEGINNER_FLOOR_Y = 0.0
SCHEMA_FLOOR_YS = (0.0, 3.2)
SPAWN_INSET = 0.75
GRUNT_INSET = 0.75
ITEM_INSET = 0.5
SPAWN_Y_OFFSET = 0.9
GRUNT_Y_OFFSET = 0.85
ITEM_Y_OFFSET = 0.45
Y_TOL = 0.05
DOOR_W_Z = 3.0
DOOR_W_X = 2.2
MIN_DOOR_OVERLAP = 0.5
EDGE_EPS = 0.02
OVERLAP_EPS = 1e-4
WIN_RULE = "all_grunts_down"
TARGET_MAP = "fresh_demo"
UNITS = "meters"
GROWTH_AXIS = "minus_z"
SNAKE_CASE = r"^[a-z][a-z0-9_]*$"
SIDE_NAMES = ("plus_z", "minus_z", "plus_x", "minus_x")
SIDE_KINDS = ("wall", "door", "open")
HUMAN_TOUCH = ("leave", "optional", "suggested", "blocked")
ACTIONS = ("world_ops", "schema_note", "code_note", "verify", "docs")

# Check column text for the ## Gates deterministic table. Order is the report order.
DETERMINISTIC_GATES: tuple[tuple[str, str], ...] = (
    ("D-MAP-01", "room_count >= 2"),
    ("D-MAP-02", "meters; grow toward -Z; x = 0 is the center line"),
    ("D-MAP-03", "beginner floor_y is 0.0"),
    ("D-ROOM-01", "snake_case room id, unique"),
    ("D-ROOM-02", "width >= 4 m and depth >= 4 m"),
    ("D-ROOM-03", "room interiors do not overlap"),
    ("D-ROOM-04", "height >= 2.5 m (default 3.0)"),
    ("D-EXIT-01", "start has a forward exit; goal has an entry; transit has two"),
    ("D-EXIT-02", "door or open sides meet on a shared edge"),
    ("D-EXIT-03", "start reaches goal through those doors"),
    ("D-START-01", "start_room_id names a room"),
    ("D-START-02", "start point inside the start room, inset >= 0.75 m"),
    ("D-GOAL-01", "goal_room_id names a room"),
    ("D-GOAL-02", "win is all_grunts_down"),
    ("D-ENEMY-01", "at least one grunt"),
    ("D-ENEMY-02", "grunt inside its room; one grunt in the goal or on the path"),
    ("D-ITEM-01", "pickups, if any, sit inside their room"),
    ("D-PAL-01", "every room color names a palette entry"),
    ("D-ID-01", "piece, enemy, and item ids are unique snake_case"),
    ("D-SAFE-01", "target_map is fresh_demo"),
)

GENERALISTIC_GATES: tuple[tuple[str, str], ...] = (
    ("G-VIS-01", "vision"),
    ("G-NAME-01", "game_id and title"),
    ("G-ROOM-01", "room purpose"),
    ("G-ROOM-02", "room ids"),
    ("G-LOOK-01", "wall look"),
    ("G-PAL-02", "palette RGB"),
    ("G-MOOD-01", "mood"),
    ("G-ITEM-02", "health pack"),
    ("G-ITEM-03", "extra pickups"),
    ("G-ENEMY-03", "extra grunts"),
    ("G-ENEMY-04", "grunt facing"),
    ("G-PATH-01", "third room"),
    ("G-PATH-02", "dead-end alcove"),
    ("G-DIFF-01", "difficulty tiers"),
    ("G-WEAP-01", "weapons"),
    ("G-LIGHT-01", "lighting"),
    ("G-META-01", "out of scope"),
)

OPPOSITE_SIDE = {
    "plus_z": "minus_z",
    "minus_z": "plus_z",
    "plus_x": "minus_x",
    "minus_x": "plus_x",
}


def fmt_num(n: float) -> str:
    """Stable short decimal: 0 -> 0.0, -4 -> -4.0, 0.85 -> 0.85."""
    text = f"{n:.4f}".rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    return text


def fmt_list(values: list[float] | tuple[float, ...]) -> str:
    return "[" + ", ".join(fmt_num(v) for v in values) + "]"
