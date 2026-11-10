"""Phase 3: builder loop, world.json materialize, gated live bunker apply.

All tests use temp dirs. No test touches the live Citadel bunker.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from phase2.derive import derive_queue  # noqa: E402
from phase2.parse import parse_master  # noqa: E402
from phase3 import builder  # noqa: E402
from phase3.world_io import apply_live, materialize, resolve_bunker, write_world  # noqa: E402

EXAMPLE = ROOT / "games" / "beginner_path_20261106"
MASTER_TEXT = (EXAMPLE / "MASTER_GAME.md").read_text(encoding="utf-8")
PYTHON = sys.executable
CLI = ROOT / "tools" / "builder_loop.py"


def approved_game(tmp: Path, **overrides):
    """Copy the known-good game into tmp, mark it approved with a real pinned hash."""
    game = tmp / "game"
    game.mkdir()
    (game / "MASTER_GAME.md").write_text(MASTER_TEXT, encoding="utf-8")
    queue = derive_queue(parse_master(MASTER_TEXT))
    queue["approved"] = True
    queue["approved_master_sha256"] = builder.master_hash(MASTER_TEXT)
    queue.update(overrides)
    (game / "BUILD_QUEUE.json").write_text(json.dumps(queue, indent=2), encoding="utf-8")
    return game, queue


class MaterializeTests(unittest.TestCase):
    def test_materialize_matches_master(self):
        world = materialize(MASTER_TEXT)
        self.assertEqual(world["schema_version"], 1)
        self.assertEqual(world["name"], "fresh_demo")
        self.assertEqual([p["id"] for p in world["pieces"]], ["start_foyer", "goal_fight"])
        self.assertTrue(all(p["kind"] == "room" for p in world["pieces"]))
        self.assertEqual(world["pieces"][0]["center"], [0.0, -4.0])
        self.assertEqual(world["pieces"][0]["sides"]["minus_z"], "door")
        self.assertEqual(world["pieces"][1]["floor_y"], 0.0)
        self.assertEqual(world["enemies"][0]["id"], "grunt_goal")
        self.assertEqual(world["enemies"][0]["pos"], [0.0, 0.85, -12.5])
        self.assertEqual(world["items"][0]["id"], "health_start")
        self.assertEqual(world["palette"]["foyer_warm"], [0.55, 0.52, 0.45])
        for surface in ("floor", "ceil", "wall", "trim"):
            self.assertIn(surface, world["palette"])
        self.assertEqual(world["map_building_gates"]["start_room_id"], "start_foyer")

    def test_materialize_is_enclosed_and_checker_compatible(self):
        world = materialize(MASTER_TEXT)
        self.assertEqual(world["code_constants"]["DOOR_W"], 3.0)
        self.assertEqual(world["code_constants"]["STEP_COUNT"], 16)
        self.assertEqual(
            world["pieces"][0]["sides"],
            {"plus_z": "wall", "minus_z": "door", "plus_x": "wall", "minus_x": "wall"},
        )
        self.assertEqual(
            world["pieces"][1]["sides"],
            {"plus_z": "door", "minus_z": "wall", "plus_x": "wall", "minus_x": "wall"},
        )
        self.assertFalse(any(p["kind"] in ("stairs", "elevator", "garden") for p in world["pieces"]))

    def test_materialize_refuses_auto_pos(self):
        broken = MASTER_TEXT.replace("[0.0, 0.85, -12.5]", "auto")
        with self.assertRaises(ValueError):
            materialize(broken)


class BuilderLoopTests(unittest.TestCase):
    def test_lint_ok_on_known_good(self):
        with tempfile.TemporaryDirectory() as d:
            game, _ = approved_game(Path(d))
            self.assertEqual(builder.lint(game), [])

    def test_derive_and_dry_run_all(self):
        with tempfile.TemporaryDirectory() as d:
            game, _ = approved_game(Path(d), approved=False, approved_master_sha256=None)
            result = subprocess.run(
                [PYTHON, str(CLI), "--game-dir", str(game), "--dry-run", "--all"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Dry run: no pending steps left.", result.stdout)
            # dry-run never writes the live world or a staged apply
            self.assertFalse((game / "runs" / "world.staged.json").exists())

    def test_materialize_cli_writes_staged_only(self):
        with tempfile.TemporaryDirectory() as d:
            game, _ = approved_game(Path(d))
            result = subprocess.run(
                [PYTHON, str(CLI), "--game-dir", str(game), "--materialize"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            staged = game / "runs" / "world.staged.json"
            self.assertTrue(staged.is_file())
            world = json.loads(staged.read_text())
            self.assertEqual(len(world["pieces"]), 2)


class ApplyGateTests(unittest.TestCase):
    def _cli(self, game, bunker, env=None):
        environ = dict(os.environ)
        environ.pop("CONFIRM_APPLY", None)
        if env:
            environ.update(env)
        return subprocess.run(
            [PYTHON, str(CLI), "--game-dir", str(game), "--apply-world",
             "--allow-apply", "--bunker-path", str(bunker)],
            capture_output=True, text=True, env=environ,
        )

    def _bunker(self, tmp: Path) -> Path:
        bunker = tmp / "home_first_person_shooter" / "game" / "world.json"
        bunker.parent.mkdir(parents=True)
        bunker.write_text('{"schema_version": 1, "name": "small_bunker", "pieces": []}\n')
        return bunker

    def test_apply_requires_flag(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            game, _ = approved_game(tmp)
            bunker = self._bunker(tmp)
            result = subprocess.run(
                [PYTHON, str(CLI), "--game-dir", str(game), "--apply-world",
                 "--bunker-path", str(bunker)],
                capture_output=True, text=True,
                env={k: v for k, v in os.environ.items() if k != "CONFIRM_APPLY"},
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("pass --allow-apply explicitly", result.stderr)
            self.assertEqual(json.loads(bunker.read_text())["name"], "small_bunker")

    def test_apply_requires_confirm_env(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            game, _ = approved_game(tmp)
            bunker = self._bunker(tmp)
            result = self._cli(game, bunker)
            self.assertEqual(result.returncode, 2)
            self.assertIn("CONFIRM_APPLY=YES", result.stderr)
            self.assertEqual(json.loads(bunker.read_text())["name"], "small_bunker")

    def test_apply_requires_approved_queue(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            game, _ = approved_game(tmp, approved=False, approved_master_sha256=None)
            bunker = self._bunker(tmp)
            result = self._cli(game, bunker, {"CONFIRM_APPLY": "YES"})
            self.assertEqual(result.returncode, 2)
            self.assertIn("queue is not approved", result.stderr)
            self.assertEqual(json.loads(bunker.read_text())["name"], "small_bunker")

    def test_apply_requires_matching_master_hash(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            game, _ = approved_game(tmp, approved_master_sha256="0" * 64)
            bunker = self._bunker(tmp)
            result = self._cli(game, bunker, {"CONFIRM_APPLY": "YES"})
            self.assertEqual(result.returncode, 2)
            self.assertIn("changed after approval", result.stderr)
            self.assertEqual(json.loads(bunker.read_text())["name"], "small_bunker")

    def test_apply_requires_existing_bunker(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            game, _ = approved_game(tmp)
            result = self._cli(game, tmp / "nowhere" / "world.json", {"CONFIRM_APPLY": "YES"})
            self.assertEqual(result.returncode, 2)
            self.assertIn("not found", result.stderr)

    def test_full_apply_makes_backup_receipt_and_replaces(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            game, _ = approved_game(tmp)
            bunker = self._bunker(tmp)
            result = self._cli(game, bunker, {"CONFIRM_APPLY": "YES"})
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            world = json.loads(bunker.read_text())
            self.assertEqual(world["name"], "fresh_demo")
            self.assertEqual([p["id"] for p in world["pieces"]], ["start_foyer", "goal_fight"])
            backups = list((bunker.parent.parent / "backups").glob("map_gates_apply_*"))
            self.assertEqual(len(backups), 1)
            old = json.loads((backups[0] / "world.json").read_text())
            self.assertEqual(old["name"], "small_bunker")
            receipt = json.loads((backups[0] / "receipt.json").read_text())
            self.assertEqual(receipt["live_world"], str(bunker.resolve()))
            self.assertEqual(receipt["approved_master_sha256"], builder.master_hash(MASTER_TEXT))
            self.assertEqual(receipt["confirm_apply_env"], "YES")
            self.assertFalse(bunker.with_suffix(".json.map_gates_tmp").exists())

    def test_resolve_bunker_default_is_citadel_path(self):
        with mock.patch("phase3.world_io.LIVE_BUNKER", Path("/nonexistent/world.json")):
            with self.assertRaises(ValueError):
                resolve_bunker(None)


class RoundTripTests(unittest.TestCase):
    def test_roundtrip_on_temp_copy(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            bunker = tmp / "home_first_person_shooter" / "game" / "world.json"
            bunker.parent.mkdir(parents=True)
            bunker.write_text('{"schema_version": 1, "name": "small_bunker", "pieces": []}\n')
            work = tmp / "work"
            result = subprocess.run(
                [PYTHON, str(ROOT / "tools" / "roundtrip.py"), "--bunker-path", str(bunker),
                 "--work-dir", str(work), "--stamp", "t1"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ROUNDTRIP PASS", result.stdout)
            res = json.loads((work / "roundtrip_result.json").read_text())
            self.assertTrue(res["ok"])
            self.assertNotEqual(res["sha_before"], res["sha_after_apply_1"])
            self.assertNotEqual(res["sha_after_apply_1"], res["sha_after_add"])
            world = json.loads(bunker.read_text())
            self.assertEqual([i["id"] for i in world["items"]], ["health_start", "health_roundtrip"])
            pre = bunker.parent.parent / "backups" / "map_gates_roundtrip_pre_t1" / "world.json"
            self.assertEqual(json.loads(pre.read_text())["name"], "small_bunker")
            self.assertEqual(len(list((bunker.parent.parent / "backups").glob("map_gates_apply_*"))), 2)


if __name__ == "__main__":
    unittest.main()
