#!/usr/bin/env python3
"""Round-trip a generated enclosed map through the Phase 3 gates onto ONE bunker world.json.

Same procedure for a rehearsal COPY and for the live bunker; only --bunker-path differs.

  1. generate the beginner path (existing beginner_path_pipeline) into --work-dir
  2. gate-lint, CONFIRM_APPROVE=YES approve, stage materialize
  3. record SHA256, plain pre-test backup, apply (every gate), reopen + check
  4. add one health pack to the master, prove the old approval is refused,
     re-approve, apply again, reopen, prove ONLY that pack was added
Stops at the first failure and exits 1. It never restores a file: the caller does that
from the plain pre-test backup it prints.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
PACK_ID = "health_roundtrip"
PACK_ROW = f"| {PACK_ID} | health_pack | start_foyer | [1.5, 0.45, -3.0] | all | +25 health; added by the round-trip add step |"
ANCHOR_ROW = "| health_start | health_pack | start_foyer |"


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def run(args, env_extra=None, expect_ok=True):
    env = {k: v for k, v in os.environ.items() if k not in ("CONFIRM_APPROVE", "CONFIRM_APPLY")}
    env.update(env_extra or {})
    p = subprocess.run([PY, *map(str, args)], capture_output=True, text=True, env=env)
    if expect_ok and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(map(str, args))}\n{p.stdout}\n{p.stderr}")
    return p


class Rt:
    def __init__(self, a):
        self.a = a
        self.bunker = Path(a.bunker_path).resolve()
        self.work = Path(a.work_dir).resolve()
        self.game = self.work / "game"
        self.stamp = a.stamp or dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.res = {"stamp": self.stamp, "bunker": str(self.bunker), "work_dir": str(self.work), "checks": []}
        self.wa = None

    def check(self, name, ok, detail=""):
        self.res["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}".rstrip())
        if not ok:
            raise RuntimeError(f"check failed: {name} {detail}")

    def load_world_agent(self):
        if not self.a.world_agent_dir:
            self.res["world_agent"] = "skipped (no --world-agent-dir)"
            return
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(self.a.world_agent_dir)))
        import world_agent  # noqa: E402  (read-only import; only validate() is called)
        self.wa = world_agent
        self.res["world_agent"] = str(Path(self.a.world_agent_dir) / "world_agent.py")

    def reopen_and_check(self, label, expected_world):
        fresh = json.loads(self.bunker.read_text(encoding="utf-8"))  # fresh read from disk
        self.check(f"{label}: reopen equals staged world", fresh == expected_world)
        if self.wa:
            errs = self.wa.validate(fresh)
            self.check(f"{label}: world_agent validate", not errs, "; ".join(errs[:5]) or "no errors")
        godot = None
        if self.wa and self.a.godot:
            g = subprocess.run([str(self.wa.GODOT), "--headless", "--path", str(self.bunker.parent), "--quit"],
                               capture_output=True, text=True, timeout=300)
            out = g.stdout + g.stderr
            errors = [l for l in out.splitlines() if "ERROR" in l][:5]
            godot = {"exit": g.returncode, "map_ready": "MAP_READY" in out, "errors": errors}
            self.check(f"{label}: headless Godot load", g.returncode == 0 and "MAP_READY" in out and not errors, json.dumps(godot))
        self.res.setdefault("godot", {})[label] = godot if godot else "skipped"
        return fresh

    def apply(self, label):
        p = run([ROOT / "tools" / "builder_loop.py", "--game-dir", self.game, "--apply-world", "--allow-apply",
                 "--bunker-path", self.bunker], {"CONFIRM_APPLY": "YES"}, expect_ok=False)
        self.check(f"{label}: apply-world exit 0", p.returncode == 0, (p.stdout + p.stderr).strip().splitlines()[-1] if (p.stdout + p.stderr).strip() else "")
        backups = sorted((self.bunker.parent.parent / "backups").glob("map_gates_apply_*"))
        self.res.setdefault("tool_backups", []).append(str(backups[-1]))
        return backups[-1]

    def go(self):
        a = self.a
        self.check("bunker exists", self.bunker.is_file(), str(self.bunker))
        if self.work.exists():
            raise RuntimeError(f"work dir already exists, refusing to reuse: {self.work}")
        self.work.mkdir(parents=True)
        self.load_world_agent()
        if self.wa:
            base = json.loads(self.bunker.read_text(encoding="utf-8"))
            errs = self.wa.validate(base)
            self.check("bunker valid before test (world_agent)", not errs, "; ".join(errs[:5]) or "no errors")
        # 1-2 generate, lint, approve, stage
        pipe = run([ROOT / "tools" / "beginner_path_pipeline.py", "--date", "20261110", "--out", self.game])
        self.check("generate + gate-lint pipeline", "pipeline: PASS" in pipe.stdout)
        bl = [ROOT / "tools" / "builder_loop.py", "--game-dir", self.game]
        self.check("builder lint", "LINT OK" in run([*bl, "--lint"]).stdout)
        run([*bl, "--approve"], {"CONFIRM_APPROVE": "YES"})
        q = json.loads((self.game / "BUILD_QUEUE.json").read_text())
        self.check("queue approved with pinned hash", q["approved"] is True and bool(q["approved_master_sha256"]))
        run([*bl, "--materialize"])
        staged1 = json.loads((self.game / "runs" / "world.staged.json").read_text())
        self.res["staged_world_1"] = str(self.game / "runs" / "world.staged.json")
        (self.work / "world.staged.round1.json").write_text(json.dumps(staged1, indent=2) + "\n", encoding="utf-8")
        # 3 sha, plain backup, apply
        self.res["sha_before"] = sha_file(self.bunker)
        pre = self.bunker.parent.parent / "backups" / f"map_gates_roundtrip_pre_{self.stamp}"
        pre.mkdir(parents=True)
        shutil.copyfile(self.bunker, pre / "world.json")
        self.res["plain_backup"] = str(pre / "world.json")
        self.check("plain backup SHA matches", sha_file(pre / "world.json") == self.res["sha_before"], self.res["sha_before"])
        tb1 = self.apply("apply 1")
        self.res["sha_after_apply_1"] = sha_file(self.bunker)
        self.check("apply 1 changed the file", self.res["sha_after_apply_1"] != self.res["sha_before"], self.res["sha_after_apply_1"])
        self.check("tool backup 1 equals the pre-test file", sha_file(tb1 / "world.json") == self.res["sha_before"])
        w1 = self.reopen_and_check("after apply 1", staged1)
        # 4 add one pack
        master = self.game / "MASTER_GAME.md"
        text = master.read_text(encoding="utf-8")
        lines = text.split("\n")
        idx = [i for i, l in enumerate(lines) if l.startswith(ANCHOR_ROW)]
        self.check("anchor row found exactly once", len(idx) == 1)
        lines.insert(idx[0] + 1, PACK_ROW)
        master.write_text("\n".join(lines), encoding="utf-8")
        self.check("lint passes with the added pack", "LINT OK" in run([*bl, "--lint"]).stdout)
        stale = run([*bl, "--apply-world", "--allow-apply", "--bunker-path", self.bunker], {"CONFIRM_APPLY": "YES"}, expect_ok=False)
        self.check("stale approval refused after master edit", stale.returncode == 2 and "changed after approval" in stale.stderr)
        self.check("file untouched by the refused apply", sha_file(self.bunker) == self.res["sha_after_apply_1"])
        run([*bl, "--approve"], {"CONFIRM_APPROVE": "YES"})
        run([*bl, "--materialize"])
        staged2 = json.loads((self.game / "runs" / "world.staged.json").read_text())
        (self.work / "world.staged.round2.json").write_text(json.dumps(staged2, indent=2) + "\n", encoding="utf-8")
        self.res["staged_world_2"] = str(self.work / "world.staged.round2.json")
        expect2 = copy.deepcopy(staged1)
        expect2["items"].append({"id": PACK_ID, "kind": "health_pack", "pos": [1.5, 0.45, -3.0]})
        self.check("staged world 2 = staged 1 + exactly one pack", staged2 == expect2)
        self.apply("apply 2")
        self.res["sha_after_add"] = sha_file(self.bunker)
        self.check("add changed the file", self.res["sha_after_add"] != self.res["sha_after_apply_1"], self.res["sha_after_add"])
        w2 = self.reopen_and_check("after add", staged2)
        self.check("pack present in start room", any(i["id"] == PACK_ID for i in w2["items"]))
        w1_no_items = {k: v for k, v in w1.items() if k != "items"}
        w2_no_items = {k: v for k, v in w2.items() if k != "items"}
        self.check("nothing else changed (all non-item keys equal)", w1_no_items == w2_no_items)
        self.check("existing items unchanged", w2["items"][: len(w1["items"])] == w1["items"] and len(w2["items"]) == len(w1["items"]) + 1)
        self.res["ok"] = True

    def finish(self, ok):
        self.res["ok"] = ok
        out = self.work / "roundtrip_result.json" if self.work.exists() else None
        if out:
            out.write_text(json.dumps(self.res, indent=2) + "\n", encoding="utf-8")
            print(f"result: {out}")
        print(json.dumps({k: v for k, v in self.res.items() if k != "checks"}, indent=2))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bunker-path", required=True, help="world.json to round-trip (a COPY for rehearsal, the live file for the real run)")
    ap.add_argument("--work-dir", required=True, help="new empty folder for the generated game, staged worlds and result json")
    ap.add_argument("--world-agent-dir", help="folder holding world_agent.py (its validate() checks every reopen)")
    ap.add_argument("--godot", action="store_true", help="also run a headless Godot load on the bunker's game folder")
    ap.add_argument("--stamp", help="timestamp label for backup folders (default: now)")
    a = ap.parse_args(argv)
    rt = Rt(a)
    try:
        rt.go()
    except Exception as e:  # noqa: BLE001
        print(f"ROUNDTRIP FAIL: {e}", file=sys.stderr)
        rt.res["error"] = str(e)
        rt.finish(False)
        print(f"Pre-test backup (restore from this if the file changed): {rt.res.get('plain_backup')}", file=sys.stderr)
        return 1
    rt.finish(True)
    print("ROUNDTRIP PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
