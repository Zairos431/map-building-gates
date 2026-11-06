"""Gate-lint and the beginner-path generator.

The known-good game under games/beginner_path_20261106 is produced by the
generator. A second copy with a broken door must fail connectivity.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from phase2.beginner import beginner_spec, render_master, write_game  # noqa: E402
from phase2.derive import derive_queue  # noqa: E402
from phase2.gates import format_report, lint_text  # noqa: E402
from phase2.model import Room  # noqa: E402
from phase2.parse import parse_master  # noqa: E402
from phase2.schema import DETERMINISTIC_GATES, GENERALISTIC_GATES, HUMAN_TOUCH  # noqa: E402

EXAMPLE = ROOT / "games" / "beginner_path_20261106"
PYTHON = sys.executable


def gate(report, gate_id):
    for result in report.results:
        if result.gate_id == gate_id:
            return result
    raise AssertionError(f"{gate_id} missing from\n{format_report(report)}")


class BeginnerPathTests(unittest.TestCase):
    def test_recipe_and_lint_pass(self) -> None:
        spec = beginner_spec("20261106")
        text = render_master(spec)
        doc = parse_master(text)
        self.assertEqual(doc.errors, [], msg="\n".join(doc.errors))
        report = lint_text(text)
        self.assertTrue(report.ok, format_report(report))
        self.assertEqual(spec.mode, "progression")
        self.assertEqual(spec.target_map, "fresh_demo")
        self.assertEqual(spec.win, "all_grunts_down")
        self.assertEqual(spec.rooms[0].size, (6.0, 8.0))
        self.assertEqual(spec.rooms[1].size, (8.0, 8.0))
        self.assertEqual(spec.rooms[0].floor_y, 0.0)
        self.assertEqual(spec.rooms[1].floor_y, 0.0)
        self.assertEqual(spec.rooms[0].center, (0.0, -4.0))
        self.assertEqual(spec.rooms[1].center, (0.0, -12.0))
        self.assertEqual(spec.enemies[0].room, "goal_fight")
        self.assertEqual(spec.items[0].room, "start_foyer")
        self.assertIn("start_foyer.minus_z meets goal_fight.plus_z", gate(report, "D-EXIT-02").detail)
        self.assertIn("start_foyer -> goal_fight", gate(report, "D-EXIT-03").detail)
        for gate_id, _label in DETERMINISTIC_GATES:
            self.assertTrue(gate(report, gate_id).ok, format_report(report))
        for gate_id, _label in GENERALISTIC_GATES:
            result = gate(report, gate_id)
            self.assertTrue(result.ok, result.detail)
            flag = result.detail.rsplit("=", 1)[-1]
            self.assertIn(flag, HUMAN_TOUCH)

    def test_queue_is_unapproved_and_derived(self) -> None:
        text = render_master(beginner_spec("20261106"))
        doc = parse_master(text)
        queue = derive_queue(doc)
        self.assertFalse(queue["approved"])
        self.assertIsNone(queue["approved_at"])
        self.assertIsNone(queue["approved_master_sha256"])
        self.assertEqual(queue["status"], "planning")
        self.assertEqual(queue["game_id"], "beginner_path_20261106")
        self.assertEqual([step["id"] for step in queue["steps"]], ["S01", "S02", "S03", "S04"])
        for step in queue["steps"]:
            self.assertEqual(step["status"], "pending")
            self.assertIsNone(step["receipt_path"])
        blob = json.dumps(queue)
        self.assertNotIn("small_bunker", blob)
        self.assertNotIn("allow-apply", blob)
        self.assertNotIn("allow_apply", blob)
        ops = queue["steps"][1]["ops_hint"]
        ops_ids = [item["id"] for item in ops]
        self.assertEqual(ops_ids, ["foyer_warm", "fight_red", "start_foyer", "goal_fight", "grunt_goal"])

    def test_committed_example_matches_generator(self) -> None:
        expected_master = render_master(beginner_spec("20261106"))
        expected_queue = derive_queue(parse_master(expected_master))
        got_master = (EXAMPLE / "MASTER_GAME.md").read_text(encoding="utf-8")
        got_queue = json.loads((EXAMPLE / "BUILD_QUEUE.json").read_text(encoding="utf-8"))
        self.assertEqual(got_master, expected_master)
        self.assertEqual(got_queue, expected_queue)
        report = lint_text(got_master, path=str(EXAMPLE / "MASTER_GAME.md"))
        self.assertTrue(report.ok, format_report(report))

    def test_break_door_fails_connectivity(self) -> None:
        spec = beginner_spec("20261106")
        spec.rooms[0].sides = dict(spec.rooms[0].sides)
        spec.rooms[0].sides["minus_z"] = "wall"
        report = lint_text(render_master(spec))
        self.assertFalse(report.ok, format_report(report))
        self.assertFalse(gate(report, "D-EXIT-01").ok)
        self.assertFalse(gate(report, "D-EXIT-02").ok)
        self.assertIn("does not meet", gate(report, "D-EXIT-02").detail)
        self.assertFalse(gate(report, "D-EXIT-03").ok)
        self.assertIn("no door-aligned path", gate(report, "D-EXIT-03").detail)
        self.assertIn("| pass |", render_master(spec))

    def test_shifted_goal_misses_the_shared_edge(self) -> None:
        spec = beginner_spec("20261106")
        spec.rooms[1].center = (0.0, -13.0)
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-EXIT-02").ok, format_report(report))
        self.assertFalse(gate(report, "D-EXIT-03").ok)
        self.assertTrue(gate(report, "D-ROOM-03").ok, gate(report, "D-ROOM-03").detail)

    def test_overlap_fails(self) -> None:
        spec = beginner_spec("20261106")
        spec.rooms[1].center = (0.0, -10.0)
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-ROOM-03").ok, format_report(report))
        self.assertIn("interiors overlap", gate(report, "D-ROOM-03").detail)

    def test_room_below_minimum_fails(self) -> None:
        spec = beginner_spec("20261106")
        spec.rooms[0].size = (3.0, 8.0)
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-ROOM-02").ok, format_report(report))
        self.assertIn("3.0", gate(report, "D-ROOM-02").detail)

    def test_short_room_fails(self) -> None:
        spec = beginner_spec("20261106")
        spec.rooms[0].height = 2.0
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-ROOM-04").ok, format_report(report))

    def test_no_grunt_fails(self) -> None:
        spec = beginner_spec("20261106")
        spec.enemies = []
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-ENEMY-01").ok, format_report(report))
        self.assertFalse(gate(report, "D-ENEMY-02").ok)

    def test_grunt_outside_room_fails(self) -> None:
        spec = beginner_spec("20261106")
        spec.enemies[0].pos = (0.0, 0.85, 0.0)
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-ENEMY-02").ok, format_report(report))
        self.assertIn("outside", gate(report, "D-ENEMY-02").detail)

    def test_grunt_only_in_dead_end_fails(self) -> None:
        spec = _with_alcove(beginner_spec("20261106"))
        spec.enemies[0].room = "side_alcove"
        spec.enemies[0].pos = (5.0, 0.85, -4.0)
        report = lint_text(render_master(spec))
        self.assertTrue(gate(report, "D-EXIT-03").ok, format_report(report))
        self.assertFalse(gate(report, "D-ENEMY-02").ok, format_report(report))
        self.assertIn("start->goal path", gate(report, "D-ENEMY-02").detail)

    def test_dead_end_alcove_still_reaches_goal(self) -> None:
        report = lint_text(render_master(_with_alcove(beginner_spec("20261106"))))
        self.assertTrue(report.ok, format_report(report))
        self.assertIn("no mid-path rooms", gate(report, "D-EXIT-01").detail)

    def test_open_sides_still_connect(self) -> None:
        spec = beginner_spec("20261106")
        spec.rooms[0].sides = dict(spec.rooms[0].sides)
        spec.rooms[1].sides = dict(spec.rooms[1].sides)
        spec.rooms[0].sides["minus_z"] = "open"
        spec.rooms[1].sides["plus_z"] = "open"
        report = lint_text(render_master(spec))
        self.assertTrue(gate(report, "D-EXIT-03").ok, format_report(report))
        self.assertTrue(report.ok, format_report(report))

    def test_health_too_close_to_wall(self) -> None:
        spec = beginner_spec("20261106")
        spec.items[0].pos = (-2.8, 0.45, -4.0)
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-ITEM-01").ok, format_report(report))
        self.assertIn("closer than", gate(report, "D-ITEM-01").detail)

    def test_start_too_close_to_wall(self) -> None:
        spec = beginner_spec("20261106")
        spec.start_pos = (0.0, 0.9, -0.2)
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-START-02").ok, format_report(report))

    def test_start_y_must_be_eye_height(self) -> None:
        spec = beginner_spec("20261106")
        spec.start_pos = (0.0, 0.0, -4.0)
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-START-02").ok, format_report(report))

    def test_upper_floor_is_out_of_beginner_scope(self) -> None:
        spec = beginner_spec("20261106")
        for room in spec.rooms:
            room.floor_y = 3.2
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-MAP-03").ok, format_report(report))
        self.assertIn("out of scope", gate(report, "D-MAP-03").detail)

    def test_live_bunker_target_fails(self) -> None:
        spec = beginner_spec("20261106")
        spec.target_map = "small_bunker"
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-SAFE-01").ok, format_report(report))
        self.assertIn("small_bunker", gate(report, "D-SAFE-01").detail)

    def test_duplicate_id_fails(self) -> None:
        spec = beginner_spec("20261106")
        spec.enemies[0].id = "start_foyer"
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-ID-01").ok, format_report(report))

    def test_room_id_must_be_snake_case(self) -> None:
        spec = beginner_spec("20261106")
        spec.rooms[0].id = "StartFoyer"
        spec.start_room_id = "StartFoyer"
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-ROOM-01").ok, format_report(report))

    def test_missing_palette_key_fails(self) -> None:
        spec = beginner_spec("20261106")
        spec.rooms[0].color = "missing_color"
        report = lint_text(render_master(spec))
        self.assertFalse(gate(report, "D-PAL-01").ok, format_report(report))

    def test_bad_human_touch_flag_fails(self) -> None:
        text = render_master(beginner_spec("20261106")).replace("| leave |", "| yolo |", 1)
        report = lint_text(text)
        self.assertFalse(report.ok, format_report(report))
        self.assertTrue(any("yolo" in result.detail for result in report.results if not result.ok))

    def test_missing_gates_section_is_a_hole(self) -> None:
        text = render_master(beginner_spec("20261106"))
        head, tail = text.split("## Gates", 1)
        _dropped, steps = tail.split("## Build Steps", 1)
        report = lint_text(head + "## Build Steps" + steps)
        self.assertFalse(report.ok)
        self.assertTrue(any("## Gates" in hole for hole in report.holes))

    def test_missing_gate_row_fails_that_gate(self) -> None:
        text = render_master(beginner_spec("20261106")).replace("| D-SAFE-01 |", "| D-SAFE-99 |", 1)
        report = lint_text(text)
        self.assertFalse(gate(report, "D-SAFE-01").ok, format_report(report))
        self.assertIn("missing D-SAFE-01", gate(report, "D-SAFE-01").detail)

    def test_zero_items_still_pass(self) -> None:
        spec = beginner_spec("20261106")
        spec.items = []
        report = lint_text(render_master(spec))
        self.assertTrue(gate(report, "D-ITEM-01").ok, format_report(report))
        self.assertTrue(report.ok, format_report(report))

    def test_templates_document_the_format(self) -> None:
        master = (ROOT / "templates" / "MASTER_GAME.md.template").read_text(encoding="utf-8")
        queue = json.loads((ROOT / "templates" / "BUILD_QUEUE.json.template").read_text(encoding="utf-8"))
        self.assertIn("## Gates", master)
        self.assertIn("### Deterministic", master)
        self.assertIn("### Generalistic", master)
        for gate_id, _label in DETERMINISTIC_GATES:
            self.assertIn(gate_id, master)
        for gate_id, _label in GENERALISTIC_GATES:
            self.assertIn(gate_id, master)
        self.assertFalse(queue["approved"])
        self.assertEqual(queue["status"], "planning")

    def test_cli_pass_and_broken_copy_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "beginner_path_20261106"
            generated = subprocess.run(
                [PYTHON, str(ROOT / "tools" / "beginner_path.py"), "--date", "20261106", "--out", str(out)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            self.assertIn("approved: false", generated.stdout)
            self.assertIn("gate-lint: PASS", generated.stdout)
            queue = json.loads((out / "BUILD_QUEUE.json").read_text(encoding="utf-8"))
            self.assertFalse(queue["approved"])

            lint = subprocess.run(
                [PYTHON, str(ROOT / "tools" / "gate_lint.py"), str(out)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)
            self.assertIn("gate-lint: PASS", lint.stdout)

            broken_path = Path(tmp) / "broken.md"
            broken = (out / "MASTER_GAME.md").read_text(encoding="utf-8").replace(
                "minus_z: door", "minus_z: wall", 1
            )
            broken_path.write_text(broken, encoding="utf-8")
            failed = subprocess.run(
                [PYTHON, str(ROOT / "tools" / "gate_lint.py"), str(broken_path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
            self.assertIn("gate-lint: FAIL", failed.stdout)
            self.assertIn("D-EXIT-03", failed.stdout)
            self.assertIn("no door-aligned path", failed.stdout)

            missing = subprocess.run(
                [PYTHON, str(ROOT / "tools" / "gate_lint.py"), str(Path(tmp) / "nope.md")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(missing.returncode, 2)

            again = subprocess.run(
                [PYTHON, str(ROOT / "tools" / "beginner_path.py"), "--date", "20261106", "--out", str(out)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(again.returncode, 2, again.stdout + again.stderr)

    def test_write_game_force_matches_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "game"
            write_game(out, "20261106")
            write_game(out, "20261106", force=True)
            self.assertEqual(
                (out / "MASTER_GAME.md").read_text(encoding="utf-8"),
                render_master(beginner_spec("20261106")),
            )


def _with_alcove(spec):
    start = spec.rooms[0]
    start.sides = dict(start.sides)
    start.sides["plus_x"] = "door"
    start.connections = [("goal_fight", "minus_z"), ("side_alcove", "plus_x")]
    spec.rooms.append(
        Room(
            id="side_alcove",
            purpose="optional breather",
            center=(5.0, -4.0),
            size=(4.0, 4.0),
            height=3.0,
            floor_y=0.0,
            color="alcove_dim",
            look="hall",
            sides={"plus_z": "wall", "minus_z": "wall", "plus_x": "wall", "minus_x": "door"},
            connections=[("start_foyer", "minus_x")],
        )
    )
    spec.palette.append(("alcove_dim", (0.35, 0.34, 0.32)))
    return spec


if __name__ == "__main__":
    unittest.main()
