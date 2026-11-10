"""Materialize a parsed MASTER into Home FPS world.json, and the gated live apply.

Phase 3 reuses phase2.parse/phase2.gates for the deterministic contract. The
materialized world is a data-only map: rooms, palette colors, grunts and health
packs. Stairs, elevator and garden stay out of scope (Phase 1 decision 16).

Dry-run writes a staged world under the game dir, never the live bunker. A live
write needs --allow-apply + CONFIRM_APPLY=YES + approved queue pinned to the
current master hash + gate-lint PASS + the real live world.json path, and leaves
a timestamped backup and receipt before the atomic replace.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path

from phase2.model import MasterDoc
from phase2.parse import parse_master

LIVE_BUNKER = Path(
    r"C:\Users\manfr\citadel\project_files\creative_projects\home_first_person_shooter\game\world.json"
)

# WORLD_SCHEMA v1 read-only mirror. main.gd owns these values; this keeps the
# materialized file readable by the existing world_agent checker, not tunable.
CODE_CONSTANTS = {
    "_note": "Read-only mirror of main.gd constants; code wins.",
    "WALL_T": 0.3,
    "HALL_W": 3.0,
    "HALL_H": 3.0,
    "HALL_L": 14.0,
    "ROOM": 8.0,
    "DOOR_W": 3.0,
    "STAIR_W": 3.0,
    "STEP_RISE": 0.2,
    "STEP_TREAD": 0.45,
    "STEP_COUNT": 16,
    "STAIR_PAD": 1.2,
    "LANDING_D": 5.0,
    "ELEV_DOOR_W": 2.2,
    "ELEV_INNER": 2.0,
}


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def stamp() -> str:
    return dt.datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def materialize(master_text: str) -> dict:
    """Build a world.json document from a MASTER. Raises ValueError on holes."""
    doc: MasterDoc = parse_master(master_text)
    problems = list(doc.errors)
    rooms = []
    for room in doc.rooms:
        if room.center is None or room.size is None or room.color is None:
            problems.append(f"room {room.id}: center/size/color must all be set to materialize")
    for spawn in list(doc.enemies) + list(doc.items):
        if spawn.pos is None:
            problems.append(f"spawn {spawn.id}: pos must be explicit [x, y, z], not auto")
    if not doc.palette:
        problems.append("palette is empty")
    if problems:
        raise ValueError("materialize refused:\n  " + "\n  ".join(problems))
    name = str(doc.fm("target_map") or doc.fm("game_id") or "map_gates")
    palette: dict[str, list[float]] = {
        key: [round(c, 4) for c in rgb] for key, rgb in doc.palette.items()
    }
    # Home FPS helpers always read these surface colors; keep safe defaults.
    for key, rgb in (
        ("floor", [0.16, 0.17, 0.18]),
        ("ceil", [0.12, 0.13, 0.14]),
        ("wall", [0.3, 0.32, 0.34]),
        ("trim", [0.42, 0.36, 0.28]),
    ):
        palette.setdefault(key, rgb)
    for room in doc.rooms:
        rooms.append(
            {
                "id": room.id,
                "kind": "room",
                "center": list(room.center),
                "size": list(room.size),
                "height": room.height if room.height is not None else 3.0,
                "floor_y": room.floor_y if room.floor_y is not None else 0.0,
                "color": room.color,
                "look": room.look or "hall",
                "sides": dict(room.sides or {}),
                "draw": True,
            }
        )
    enemies = [
        {"id": s.id, "kind": s.kind, "pos": list(s.pos)} for s in doc.enemies
    ]
    items = [{"id": s.id, "kind": s.kind, "pos": list(s.pos)} for s in doc.items]
    return {
        "schema_version": 1,
        "name": name,
        "units": "meters; +Y up; the map runs from z=0 (spawn) toward -Z",
        "code_constants": dict(CODE_CONSTANTS),
        "palette": palette,
        "pieces": rooms,
        "enemies": enemies,
        "items": items,
        "map_building_gates": {
            "phase": 3,
            "game_id": doc.fm("game_id"),
            "mode": doc.fm("mode"),
            "win": doc.fm("win"),
            "start_room_id": doc.fm("start_room_id"),
            "goal_room_id": doc.fm("goal_room_id"),
            "start_pos": doc.fm("start_pos"),
        },
    }


def write_world(path: Path, world: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(world, indent=2) + "\n", encoding="utf-8")


def resolve_bunker(explicit: str | None) -> Path:
    """The one real Citadel bunker. No second path is invented."""
    path = Path(explicit) if explicit else LIVE_BUNKER
    if not path.is_file():
        raise ValueError(f"live bunker world.json not found: {path}")
    return path.resolve()


def apply_live(world: dict, *, bunker: Path, master_sha256: str, game_id: str) -> dict:
    """Backup -> receipt -> atomic replace of the live world.json."""
    base = bunker.parent.parent / "backups" / f"map_gates_apply_{stamp()}"
    backup_dir, n = base, 1
    while True:  # two applies in the same second must not collide or overwrite a backup
        try:
            backup_dir.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            n += 1
            backup_dir = base.with_name(f"{base.name}_{n:02d}")
    backup = backup_dir / "world.json"
    old = bunker.read_bytes()
    backup.write_bytes(old)
    payload = json.dumps(world, indent=2) + "\n"
    receipt = {
        "schema_version": 1,
        "tool": "map_building_gates_phase3_apply",
        "ts": now(),
        "game_id": game_id,
        "approved_master_sha256": master_sha256,
        "live_world": str(bunker),
        "backup_world": str(backup),
        "before_sha256": hashlib.sha256(old).hexdigest(),
        "after_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "confirm_apply_env": os.environ.get("CONFIRM_APPLY"),
    }
    (backup_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    tmp = bunker.with_suffix(".json.map_gates_tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, bunker)
    return receipt
