#!/usr/bin/env python3
"""Phase 3 builder loop — executes an APPROVED MASTER_GAME.md one step at a time.

Ported from the proven /workspace/game_pipeline/builder/builder_loop.py pattern
and rewired to this repo's phase2 gate-lint. Adds world.json materialize and a
hard-gated live bunker apply.

The plan lives on disk (MASTER_GAME.md + BUILD_QUEUE.json in --game-dir). Every iteration reloads both
files, re-reads the exact MASTER sections the step names, checks the queue still matches the master,
checks the step has no design holes, checks all prior work is still intact, does the step, verifies it,
and writes a receipt + a JSONL log line. Nothing is cached between steps. Python 3 stdlib only.

  python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --lint
  python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --dry-run --all
  CONFIRM_APPROVE=YES python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --approve
  python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --all
  python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --materialize
  python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --apply-world \
      --allow-apply --bunker-path <live world.json>          # also needs CONFIRM_APPLY=YES
"""
import argparse, datetime as dt, hashlib, json, os, re, subprocess, sys
from pathlib import Path

from phase2.gates import format_report, lint_text
from phase3.world_io import apply_live, materialize, resolve_bunker, write_world

ACTIONS = {"world_ops", "schema_note", "code_note", "verify", "docs", "materialize", "apply_world"}
STEP_FIELDS = ("section_refs", "action", "instruction", "acceptance", "replaces")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class StepFail(Exception):
    """A step failed a gate. The message is the hole/failure report."""


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------- master document parsing ----------------
def split_frontmatter(md):
    """Returns (dict, body). Frontmatter is simple `key: value` YAML between --- lines."""
    m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if not m:
        raise StepFail("MASTER_GAME.md has no YAML frontmatter")
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, md[m.end():]


def master_hash(md):
    """Hash of the design, ignoring the frontmatter status/updated lines the builder itself changes."""
    keep = [l for l in md.splitlines() if not re.match(r"^(status|updated):", l)]
    return sha("\n".join(keep))


def set_frontmatter(md, **vals):
    for k, v in vals.items():
        md, n = re.subn(rf"^{k}:.*$", f"{k}: {v}", md, count=1, flags=re.M)
        if not n:
            raise StepFail(f"frontmatter key {k!r} missing")
    return md


def headings(md):
    """[(line_index, level, heading_line)] ignoring fenced code blocks."""
    out, fence = [], False
    for i, line in enumerate(md.splitlines()):
        if line.strip().startswith("```"):
            fence = not fence
            continue
        m = HEADING.match(line)
        if m and not fence:
            out.append((i, len(m.group(1)), f"{m.group(1)} {m.group(2)}"))
    return out


def extract_sections(md, refs):
    """Strict: each ref must be an exact heading line ('## Map layout') that appears exactly once.
    A section runs to the next heading of the same or higher level. Returns {ref: text}.
    Raises StepFail listing every missing/duplicate/empty ref (a 'hole')."""
    if not refs:
        raise StepFail("hole: step has no section_refs")
    lines, hs, out, problems = md.splitlines(), headings(md), {}, []
    for ref in refs:
        ref_n = " ".join(ref.split())
        hits = [h for h in hs if h[2] == ref_n]
        if not hits:
            problems.append(f"hole: section {ref!r} not found in MASTER_GAME.md")
            continue
        if len(hits) > 1:
            problems.append(f"hole: section {ref!r} appears {len(hits)} times (ambiguous)")
            continue
        start, level, _ = hits[0]
        end = next((i for i, lv, _ in hs if i > start and lv <= level), len(lines))
        text = "\n".join(lines[start:end]).strip()
        if len(text.splitlines()) < 2:
            problems.append(f"hole: section {ref!r} is empty")
            continue
        out[ref] = text
    if problems:
        raise StepFail("; ".join(problems))
    return out


def _value(raw):
    raw = raw.strip()
    if raw in ("null", "None", ""):
        return None
    if raw[:1] in "[{":
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise StepFail(f"bad JSON in master step field: {raw[:80]} ({e})")
    return raw


def parse_master_steps(md):
    """Parses '### Sxx: title' blocks under '## Build Steps' into step dicts (the design's own copy)."""
    body = extract_sections(md, ["## Build Steps"])["## Build Steps"]
    steps, cur, field = [], None, None
    for line in body.splitlines()[1:]:
        m = re.match(r"^###\s+(S\d{2,})\s*:\s*(.+?)\s*$", line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2), "acceptance": []}
            steps.append(cur); field = None
            continue
        if cur is None:
            continue
        f = re.match(r"^- (\w+):\s*(.*)$", line)
        if f:
            field = f.group(1)
            if field != "acceptance":
                cur[field] = _value(f.group(2))
            continue
        a = re.match(r"^\s+- (?:\[.\]\s*)?(.+)$", line)
        if a and field == "acceptance":
            cur["acceptance"].append(a.group(1).strip())
    for s in steps:
        s.setdefault("replaces", None); s.setdefault("ops_hint", None)
    return steps


# ---------------- gates ----------------
def no_holes_check(step, master):
    """Returns a list of hole reports (empty = OK). If the step replaces/removes something, the
    instruction must name the better replacement and say how it serves the design."""
    p = []
    if not re.fullmatch(r"S\d{2,}", str(step.get("id", ""))):
        p.append("step id must look like S01")
    if not step.get("title"):
        p.append("missing title")
    if step.get("action") not in ACTIONS:
        p.append(f"action must be one of {sorted(ACTIONS)}")
    ins = (step.get("instruction") or "").strip()
    if not ins or "\n" in ins:
        p.append("instruction must be one non-empty line (one concrete action)")
    if not step.get("acceptance"):
        p.append("acceptance checklist is empty")
    if not step.get("section_refs"):
        p.append("section_refs is empty")
    rep = step.get("replaces")
    if rep is not None:
        if not isinstance(rep, dict) or not all(rep.get(k) for k in ("element_id", "replacement_id", "why_better")):
            p.append("replaces must be {element_id, replacement_id, why_better}")
        else:
            if rep["replacement_id"] not in ins:
                p.append(f"instruction must name the replacement {rep['replacement_id']!r}")
            if len(rep["why_better"]) < 20 or not re.search(r"because|so that|serves|better", ins + " " + rep["why_better"], re.I):
                p.append("replaces.why_better must say how the replacement better serves the design")
            design = master.split("## Build Steps")[0]
            if rep["replacement_id"] not in design:
                p.append(f"replacement {rep['replacement_id']!r} is not specified in the design sections")
    # no silent removals: a remove op must be declared in replaces
    for op in step.get("ops_hint") or []:
        if isinstance(op, dict) and op.get("op") == "remove":
            if not isinstance(rep, dict) or rep.get("element_id") != op.get("id"):
                p.append(f"ops_hint removes {op.get('id')!r} without a matching replaces entry")
    return p


def queue_matches_master(qstep, master_steps):
    """Anti-drift: the queue's copy of a step must equal the master's copy."""
    m = next((s for s in master_steps if s["id"] == qstep["id"]), None)
    if m is None:
        return [f"step {qstep['id']} is in BUILD_QUEUE.json but not in MASTER_GAME.md Build Steps"]
    return [f"{qstep['id']}.{k} differs between queue and master" for k in ("title",) + STEP_FIELDS + ("ops_hint",)
            if (qstep.get(k) or None) != (m.get(k) or None)]


def verify_prior_work(game_dir, queue, step, master, simulated=()):
    """All earlier steps must be pass, with a receipt on disk whose outputs still exist and whose
    re-read sections still hash the same (the design they were built against has not shifted)."""
    notes, checked = [], []
    for s in queue["steps"]:
        if s["id"] == step["id"]:
            break
        checked.append(s["id"])
        if s["id"] in simulated:
            continue
        if s["status"] != "pass":
            notes.append(f"{s['id']} status is {s['status']}, not pass")
            continue
        rp = game_dir / (s.get("receipt_path") or "")
        if not s.get("receipt_path") or not rp.is_file():
            notes.append(f"{s['id']} receipt missing")
            continue
        r = json.loads(rp.read_text(encoding="utf-8"))
        if r.get("outcome") != "pass":
            notes.append(f"{s['id']} receipt outcome is {r.get('outcome')}")
        for o in r.get("outputs", []):
            if not (game_dir / o).exists():
                notes.append(f"{s['id']} output {o} is gone (prior work broken)")
        for sec in r.get("sections_reread", []):
            try:
                cur = extract_sections(master, [sec["ref"]])[sec["ref"]]
            except StepFail as e:
                notes.append(f"{s['id']}: {e}"); continue
            if sha(cur) != sec["sha256"]:
                notes.append(f"{s['id']}: section {sec['ref']!r} changed since it was built")
    return {"ok": not notes, "checked_steps": checked, "notes": notes}


# ---------------- actions ----------------
def run_checks(game_dir, step, master, queue, simulated, sim_outputs):
    """'check:' acceptance items are machine-checked; other items are recorded as manual."""
    res = []
    for item in step["acceptance"]:
        m = re.match(r"^check:\s*(\w+)\s+(.+)$", item)
        if not m:
            res.append({"item": item, "result": "manual", "detail": "recorded; needs human eyes"}); continue
        kind, arg = m.group(1), m.group(2).strip()
        ok, detail = False, ""
        if kind == "master_contains":
            ok = arg in master.split("## Build Steps")[0]; detail = "found in design" if ok else "not in design sections"
        elif kind == "file":
            ok = (game_dir / arg).exists() or arg in sim_outputs; detail = arg
        elif kind == "receipts":
            bad = []
            for sid in [x.strip() for x in arg.split(",") if x.strip()]:
                if sid in simulated:
                    continue
                qs = next((s for s in queue["steps"] if s["id"] == sid), None)
                rp = game_dir / (qs.get("receipt_path") or "") if qs else None
                if not qs or not qs.get("receipt_path") or not rp.is_file() or json.loads(rp.read_text())["outcome"] != "pass":
                    bad.append(sid)
            ok = not bad; detail = "all present" if ok else f"missing/failed: {bad}"
        else:
            detail = f"unknown check kind {kind!r}"
        res.append({"item": item, "result": "pass" if ok else "fail", "detail": detail})
    return res


def do_action(args, game_dir, step, excerpts, dry):
    """Performs the step. Returns (outputs, notes). Never touches the network unless --world-agent is set."""
    runs = game_dir / "runs"
    sid, act = step["id"], step["action"]
    if act == "world_ops":
        req = {"step_id": sid, "title": step["title"], "instruction": step["instruction"],
               "ops_hint": step.get("ops_hint"), "acceptance": step["acceptance"],
               "section_excerpts": excerpts, "created": now(),
               "how_to_apply": "world_agent.py --ops-file <ops_hint file> (dry run) then --apply after review"}
        out = f"runs/step_{sid}_ops_request.json"
        (game_dir / out).write_text(json.dumps(req, indent=2), encoding="utf-8")
        if dry or not args.world_agent:
            return [out], "ops request staged (world_agent not called)"
        cmd = [sys.executable, args.world_agent]
        if step.get("ops_hint"):
            opsf = runs / f"step_{sid}_ops.json"
            opsf.write_text(json.dumps({"ops": step["ops_hint"]}, indent=2), encoding="utf-8")
            cmd += ["--ops-file", str(opsf)]
        if args.allow_apply:
            cmd.append("--apply")
        cmd.append(step["instruction"])
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        log = f"runs/step_{sid}_world_agent.log"
        (game_dir / log).write_text(p.stdout + "\n--- stderr ---\n" + p.stderr, encoding="utf-8")
        if p.returncode != 0 or "Result: VALID" not in p.stdout:
            raise StepFail(f"world_agent rejected the ops (see {log})")
        return [out, log], "world_agent VALID" + (" + applied" if args.allow_apply else " (dry run, not applied)")
    if act in ("schema_note", "code_note", "docs"):
        out = f"runs/step_{sid}_{act}.md"
        if not dry:
            body = [f"# {sid}: {step['title']}", "", f"Action: {act}", "", f"Instruction: {step['instruction']}", "",
                    "## Acceptance", *[f"- {a}" for a in step["acceptance"]], "", "## Design excerpts (re-read from MASTER_GAME.md)"]
            for ref, txt in excerpts.items():
                body += ["", f"<!-- {ref} -->", txt]
            if act == "code_note":
                body += ["", "> Code change is NOT made by the builder. Hand this note to a human or code agent."]
            (game_dir / out).write_text("\n".join(body) + "\n", encoding="utf-8")
        return [out], f"{act} written" if not dry else f"{act} would be written"
    if act == "materialize":
        world = materialize(master)
        out = f"runs/step_{sid}_world.json"
        write_world(game_dir / out, world)
        return [out], f"staged world.json ({len(world['pieces'])} pieces, {len(world['enemies'])} enemies)"
    if act == "apply_world":
        if dry:
            raise StepFail("apply_world cannot be dry-run as a step; use --materialize for staging")
        raise StepFail("apply_world steps must run via --apply-world, not the step loop")
    return [], "verify step: checks only"


# ---------------- main loop ----------------
def load(game_dir):
    q = json.loads((game_dir / "BUILD_QUEUE.json").read_text(encoding="utf-8"))
    master = (game_dir / q.get("master_path", "MASTER_GAME.md")).read_text(encoding="utf-8")
    return q, master


def save_queue(game_dir, q):
    tmp = game_dir / "BUILD_QUEUE.json.tmp"
    tmp.write_text(json.dumps(q, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, game_dir / "BUILD_QUEUE.json")


def write_master_status(game_dir, q, status):
    p = game_dir / q.get("master_path", "MASTER_GAME.md")
    p.write_text(set_frontmatter(p.read_text(encoding="utf-8"), status=status,
                                 updated=dt.date.today().isoformat()), encoding="utf-8")


def log(game_dir, rec):
    with open(game_dir / "runs" / "builder.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now(), **rec}) + "\n")


def lint(game_dir):
    """Every step: no holes, refs resolve, queue == master. Used by the planner before asking for APPROVE."""
    q, master = load(game_dir)
    fm, _ = split_frontmatter(master)
    probs = []
    report = lint_text(master)
    if not report.ok:
        probs.append("phase2 gate-lint FAIL:\n" + format_report(report))
    for k in ("schema_version", "game_id", "title", "mode", "status", "target", "created", "updated"):
        if not fm.get(k):
            probs.append(f"frontmatter missing {k}")
    if fm.get("mode") not in ("ffa", "progression"):
        probs.append("mode must be ffa or progression")
    for sec in ("## Vision", "## Player fantasy / win condition", "## Mode & difficulty tiers", "## Map layout",
                "## Weapons & tools", "## Enemies & spawns", "## Items / pickups", "## Constraints / out-of-scope", "## Build Steps"):
        try:
            extract_sections(master, [sec])
        except StepFail as e:
            probs.append(str(e))
    if not any(h[2] in ("## Progression", "## FFA rules") for h in headings(master)):
        probs.append("hole: need '## Progression' or '## FFA rules'")
    ms = parse_master_steps(master)
    if [s["id"] for s in ms] != [s["id"] for s in q["steps"]]:
        probs.append(f"step ids differ: master {[s['id'] for s in ms]} vs queue {[s['id'] for s in q['steps']]}")
    for s in q["steps"]:
        probs += [f"{s['id']}: {x}" for x in no_holes_check(s, master)]
        probs += queue_matches_master(s, ms)
        try:
            extract_sections(master, s.get("section_refs") or [])
        except StepFail as e:
            probs.append(f"{s['id']}: {e}")
    return probs


def derive_queue(game_dir):
    """Rebuild BUILD_QUEUE.json from the master's Build Steps (only before approval)."""
    master = (game_dir / "MASTER_GAME.md").read_text(encoding="utf-8")
    fm, _ = split_frontmatter(master)
    qp = game_dir / "BUILD_QUEUE.json"
    if qp.exists() and json.loads(qp.read_text())["approved"]:
        raise StepFail("queue already approved; derive refused")
    steps = [{"id": s["id"], "title": s["title"], "section_refs": s.get("section_refs"), "action": s.get("action"),
              "instruction": s.get("instruction"), "acceptance": s["acceptance"], "replaces": s["replaces"],
              "ops_hint": s["ops_hint"], "status": "pending", "started_at": None, "finished_at": None,
              "verify_notes": "", "receipt_path": None} for s in parse_master_steps(master)]
    save_queue(game_dir, {"schema_version": 1, "game_id": fm.get("game_id", ""), "master_path": "MASTER_GAME.md",
                          "approved": False, "approved_at": None, "approved_master_sha256": None,
                          "status": "planning", "current_step": None, "steps": steps})


def approve(game_dir):
    if os.environ.get("CONFIRM_APPROVE") != "YES":
        raise StepFail("approve refused: set CONFIRM_APPROVE=YES only after Doug says APPROVE")
    q, master = load(game_dir)
    fm, _ = split_frontmatter(master)
    if fm.get("status") not in ("draft", "approved"):
        raise StepFail(f"approve refused: master status is {fm.get('status')}")
    probs = lint(game_dir)
    if probs:
        raise StepFail("approve refused, plan has holes:\n  " + "\n  ".join(probs))
    write_master_status(game_dir, q, "approved")
    q, master = load(game_dir)
    q.update(approved=True, approved_at=now(), approved_master_sha256=master_hash(master), status="approved")
    save_queue(game_dir, q)
    log(game_dir, {"event": "approved", "master_sha256": q["approved_master_sha256"]})


def run_step(args, game_dir, simulated, sim_outputs):
    """One iteration. Returns 'done', 'pass', or raises StepFail. Reloads everything from disk first."""
    dry = args.dry_run
    q, master = load(game_dir)                                   # 1. fresh from disk, every step
    if not dry:                                                  # 2. approval gate
        if q.get("approved") is not True:
            raise StepFail("refused: plan not approved (Doug must say APPROVE)")
        if q.get("approved_master_sha256") != master_hash(master):
            raise StepFail("refused: MASTER_GAME.md changed after approval — re-lint and re-approve")
    if any(s["status"] in ("fail", "running") for s in q["steps"]) and not dry:
        raise StepFail("refused: a step is fail/running — fix and reset it to pending first")
    step = next((s for s in q["steps"] if s["status"] != "pass" and s["id"] not in simulated), None)  # 3. in order
    if step is None:
        return "done"
    if step["status"] != "pending" and not dry:
        raise StepFail(f"refused: next step {step['id']} is {step['status']}, not pending")
    started = now()
    if not dry:
        step.update(status="running", started_at=started); q["status"] = "building"; q["current_step"] = step["id"]
        save_queue(game_dir, q)
        if split_frontmatter(master)[0].get("status") != "building":
            write_master_status(game_dir, q, "building")
            master = (game_dir / q.get("master_path", "MASTER_GAME.md")).read_text(encoding="utf-8")
    print(f"\n=== {step['id']}: {step['title']}  [{step['action']}]{'  (DRY RUN)' if dry else ''}")
    excerpts = extract_sections(master, step["section_refs"])   # 4. strict re-read
    for ref, txt in excerpts.items():                            # 5. show what was re-read
        print(f"\n--- re-read {ref} ---\n{txt}")
    print(f"\n>>> instruction: {step['instruction']}")
    drift = queue_matches_master(step, parse_master_steps(master))
    holes = no_holes_check(step, master)
    if drift or holes:
        raise StepFail("design mismatch: " + "; ".join(drift + holes))
    prior = verify_prior_work(game_dir, q, step, master, simulated)   # 7. nothing earlier broken
    if not prior["ok"]:
        raise StepFail("prior work check failed: " + "; ".join(prior["notes"]))
    outputs, note = do_action(args, game_dir, step, excerpts, dry)    # 6. the action
    sim_outputs.update(outputs)
    checks = run_checks(game_dir, step, master, q, simulated, sim_outputs)
    if any(c["result"] == "fail" for c in checks):
        raise StepFail("acceptance failed: " + "; ".join(f"{c['item']} ({c['detail']})" for c in checks if c["result"] == "fail"))
    receipt = {"schema_version": 1, "game_id": q["game_id"], "step_id": step["id"], "title": step["title"],
               "action": step["action"], "outcome": "pass", "dry_run": dry, "started_at": started, "finished_at": now(),
               "master_sha256": master_hash(master),
               "sections_reread": [{"ref": r, "sha256": sha(t), "chars": len(t)} for r, t in excerpts.items()],
               "instruction": step["instruction"],
               "design_match": {"queue_matches_master": True, "no_holes": True, "notes": []},
               "acceptance": checks, "prior_work": prior, "outputs": outputs, "replaces": step.get("replaces"), "notes": note}
    for c in checks:
        print(f"  [{c['result']}] {c['item']} — {c['detail']}")
    print(f"  result: {note}")
    if dry:
        simulated.add(step["id"])
        log(game_dir, {"event": "dry_run_step", "step": step["id"], "outputs": outputs, "note": note})
        return "pass"
    rp = f"runs/step_{step['id']}_receipt.json"                  # 8. receipt + queue update
    (game_dir / rp).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    q, _ = load(game_dir)
    qs = next(s for s in q["steps"] if s["id"] == step["id"])
    qs.update(status="pass", finished_at=receipt["finished_at"], receipt_path=rp,
              verify_notes=f"{sum(c['result']=='pass' for c in checks)} checks pass, "
                           f"{sum(c['result']=='manual' for c in checks)} manual; {note}")
    q["current_step"] = None
    save_queue(game_dir, q)
    log(game_dir, {"event": "step_pass", "step": step["id"], "receipt": rp, "note": note})   # 10.
    return "pass"


def mark_fail(game_dir, msg):
    """9. failure: step -> fail, queue -> blocked, stop."""
    try:
        q, _ = load(game_dir)
        if any(x["status"] == "fail" for x in q["steps"]):   # already blocked: just log, don't fail more steps
            log(game_dir, {"event": "refused", "error": msg}); return
        s = next((s for s in q["steps"] if s["status"] == "running"), None) or \
            next((s for s in q["steps"] if s["status"] == "pending"), None)
        if s and q.get("approved"):
            s.update(status="fail", finished_at=now(), verify_notes=msg)
            q["status"] = "blocked"; q["current_step"] = s["id"]
            save_queue(game_dir, q)
        log(game_dir, {"event": "step_fail", "step": s["id"] if s else None, "error": msg})
    except Exception as e:  # logging must never hide the original failure
        print(f"(could not record failure: {e})", file=sys.stderr)


def finish(game_dir):
    q, master = load(game_dir)
    if q["status"] != "done":
        q["status"] = "done"; save_queue(game_dir, q); write_master_status(game_dir, q, "done")
    lines = [f"# Finished: {split_frontmatter(master)[0].get('title')} ({q['game_id']})", "", f"Finished {now()}", "",
             "| step | title | action | result | receipt |", "| --- | --- | --- | --- | --- |"]
    manual = []
    for s in q["steps"]:
        lines.append(f"| {s['id']} | {s['title']} | {s['action']} | {s['status']} | {s['receipt_path']} |")
        r = json.loads((game_dir / s["receipt_path"]).read_text())
        manual += [f"- {s['id']}: {c['item']}" for c in r["acceptance"] if c["result"] == "manual"]
        manual += [f"- {s['id']}: staged output {o} (apply/review)" for o in r["outputs"] if "ops_request" in o]
    lines += ["", "## Still needs Doug's eyes / hands", *(manual or ["- nothing"])]
    (game_dir / "runs" / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(game_dir, {"event": "done"})
    print("\nAll steps pass. Report: runs/FINAL_REPORT.md")


def do_materialize(args, game_dir):
    """Stage or apply the materialized world. All live-write gates checked here."""
    q, master = load(game_dir)
    report = lint_text(master)
    if not report.ok:
        print(format_report(report))
        raise StepFail("gate-lint FAIL; refusing to materialize")
    world = materialize(master)
    if not args.apply_world:
        out = game_dir / "runs" / "world.staged.json"
        write_world(out, world)
        log(game_dir, {"event": "materialize_staged", "output": str(out.relative_to(game_dir)),
                       "pieces": len(world["pieces"])})
        print(f"Staged world written (dry-run default, live bunker untouched): {out}")
        return 0
    # live apply: every gate, in order
    if not args.allow_apply_world:
        raise StepFail("live apply refused: pass --allow-apply explicitly")
    if os.environ.get("CONFIRM_APPLY") != "YES":
        raise StepFail("live apply refused: set CONFIRM_APPLY=YES only after Doug approves this exact apply")
    if q.get("approved") is not True:
        raise StepFail("live apply refused: queue is not approved (Doug must say APPROVE)")
    mhash = master_hash(master)
    if q.get("approved_master_sha256") != mhash:
        raise StepFail("live apply refused: MASTER_GAME.md changed after approval; re-approve first")
    try:
        bunker = resolve_bunker(args.bunker_path)
    except ValueError as e:
        raise StepFail(f"live apply refused: {e}")
    receipt = apply_live(world, bunker=bunker, master_sha256=mhash, game_id=q["game_id"])
    out = game_dir / "runs" / f"apply_receipt_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    log(game_dir, {"event": "live_apply", "receipt": receipt})
    print(f"Live world applied: {receipt['live_world']}\nBackup + receipt: {receipt['backup_world']}")
    return 0


class Lock:
    """One builder per game dir (background runs must not overlap)."""
    def __init__(self, game_dir):
        self.p = game_dir / "runs" / ".builder.lock"
    def __enter__(self):
        if self.p.exists():
            pid = int(self.p.read_text().strip() or 0)
            try:
                os.kill(pid, 0); raise StepFail(f"another builder (pid {pid}) is running")
            except (ProcessLookupError, PermissionError, ValueError):
                pass  # stale lock
        self.p.write_text(str(os.getpid()))
    def __exit__(self, *a):
        self.p.unlink(missing_ok=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Step-by-step builder for an approved MASTER_GAME.md plan.")
    ap.add_argument("--game-dir", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true", help="run the next pending step")
    g.add_argument("--all", action="store_true", help="run remaining steps until fail or done")
    g.add_argument("--lint", action="store_true", help="check the plan for holes (planner uses this)")
    g.add_argument("--derive-queue", action="store_true", help="rebuild BUILD_QUEUE.json from MASTER Build Steps")
    g.add_argument("--approve", action="store_true", help="needs env CONFIRM_APPROVE=YES")
    g.add_argument("--materialize", action="store_true", help="write runs/world.staged.json; never touches live")
    g.add_argument("--apply-world", action="store_true", help="live write; needs --allow-apply + CONFIRM_APPLY=YES")
    ap.add_argument("--bunker-path", help="live world.json; default is the Citadel home_first_person_shooter path")
    ap.add_argument("--dry-run", action="store_true", help="no queue/receipt/world changes; still re-reads and prints")
    ap.add_argument("--world-agent", help="path to world_agent.py (else world_ops steps are staged as request files)")
    ap.add_argument("--allow-apply", dest="allow_apply_world", action="store_true",
                    help="explicit opt-in for live writes: --apply-world and world_agent --apply")
    a = ap.parse_args(argv)
    game_dir = Path(a.game_dir).resolve()
    (game_dir / "runs").mkdir(exist_ok=True)
    try:
        if a.lint:
            probs = lint(game_dir)
            print("LINT OK — no holes" if not probs else "LINT FAIL:\n  " + "\n  ".join(probs))
            return 0 if not probs else 1
        if a.derive_queue:
            derive_queue(game_dir); print("BUILD_QUEUE.json derived (approved=false)"); return 0
        if a.approve:
            approve(game_dir); print("APPROVED. Builder may now run."); return 0
        if a.materialize or a.apply_world:
            return do_materialize(a, game_dir)
        simulated, sim_outputs = set(), set()
        with Lock(game_dir):
            while True:
                r = run_step(a, game_dir, simulated, sim_outputs)
                if r == "done":
                    if a.dry_run:
                        print("\nDry run: no pending steps left.")
                    else:
                        finish(game_dir)
                    return 0
                if a.once:
                    return 0
    except StepFail as e:
        print(f"\nSTOP: {e}", file=sys.stderr)
        if not a.dry_run and (a.once or a.all):
            mark_fail(game_dir, str(e))
        return 2


if __name__ == "__main__":
    sys.exit(main())
