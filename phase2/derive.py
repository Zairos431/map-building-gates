"""Derive an unapproved BUILD_QUEUE.json from MASTER build steps.

This is the thin slice of the planner's --derive-queue step. It does not
approve the queue and it does not run a builder.
"""

from __future__ import annotations

from collections import Counter

from phase2.model import MasterDoc
from phase2.schema import ACTIONS


def derive_queue(doc: MasterDoc) -> dict[str, object]:
    errors = section_ref_errors(doc)
    if errors:
        raise ValueError("MASTER build steps do not match its headings:\n" + "\n".join(errors))
    for step in doc.steps:
        if step.action not in ACTIONS:
            raise ValueError(f"{step.id} action {step.action!r} is not one of {', '.join(ACTIONS)}")
        if not step.instruction:
            raise ValueError(f"{step.id} is missing its instruction")
        if not step.acceptance:
            raise ValueError(f"{step.id} is missing acceptance")
        if not step.section_refs:
            raise ValueError(f"{step.id} is missing section_refs")
    game_id = doc.fm("game_id")
    if not isinstance(game_id, str) or not game_id:
        raise ValueError("MASTER frontmatter is missing game_id")
    return {
        "schema_version": 1,
        "game_id": game_id,
        "master_path": "MASTER_GAME.md",
        "approved": False,
        "approved_at": None,
        "approved_master_sha256": None,
        "status": "planning",
        "current_step": None,
        "steps": [
            {
                "id": step.id,
                "title": step.title,
                "section_refs": list(step.section_refs),
                "action": step.action,
                "instruction": step.instruction,
                "acceptance": list(step.acceptance),
                "replaces": step.replaces,
                "ops_hint": step.ops_hint,
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "verify_notes": "",
                "receipt_path": None,
            }
            for step in doc.steps
        ],
    }


def section_ref_errors(doc: MasterDoc) -> list[str]:
    """Each section_ref must be one exact heading line in the master."""
    headings = [line.strip() for line in doc.text.splitlines() if line.startswith("#")]
    counts = Counter(headings)
    errors: list[str] = []
    seen_ids: set[str] = set()
    for step in doc.steps:
        if step.id in seen_ids:
            errors.append(f"{step.id} is duplicated")
        seen_ids.add(step.id)
        for ref in step.section_refs:
            found = counts.get(ref, 0)
            if found != 1:
                errors.append(f"{step.id} section_ref {ref!r} appears {found} times")
    return errors
