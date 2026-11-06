# Phase 3 — builder loop, materialize, gated live apply

**Added 2026-11-06** (Doug's Phase 3 go via Anthony - Coordinator II).

- `builder.py` — the step-by-step builder, ported from the proven
  `/workspace/game_pipeline/builder/builder_loop.py` pattern and rewired to
  Phase 2 `gate_lint`. Re-reads MASTER + queue every step; approval pins a master hash.
- `world_io.py` — materialize a parsed MASTER into Home FPS `world.json`
  (rooms, palette, grunts, health packs only), plus the gated live apply.

## Use

```bash
python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --lint
python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --dry-run --all
CONFIRM_APPROVE=YES python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --approve
python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --all
python3 tools/builder_loop.py --game-dir games/beginner_path_20261106 --materialize   # staged only
```

`--world-agent <path to world_agent.py>` validates world_ops steps with the real
Citadel checker when present; without it they are staged as ops request files.

## Live apply (off by default; needs Doug's yes every time)

`--materialize` writes `runs/world.staged.json` and never touches the live bunker.
A live write (`--apply-world`) requires ALL of:

1. `--allow-apply` on the command line.
2. `CONFIRM_APPLY=YES` in the environment.
3. Queue `approved: true` with `approved_master_sha256` matching the current master.
4. Phase 2 gate-lint PASS.
5. `--bunker-path` resolving to a real existing `world.json`. The default is the
   one real Citadel bunker:
   `C:\Users\manfr\citadel\project_files\creative_projects\home_first_person_shooter\game\world.json`.
   No second bunker is ever invented.

Before replacing, the tool copies the old world to
`home_first_person_shooter\backups\map_gates_apply_<stamp>\world.json` and writes a
`receipt.json` beside it, then replaces atomically (temp file + `os.replace`).
