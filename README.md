# Map Building Gates

**Early / exploratory.** This repo is the first public home for a small design idea: building game maps with **gates** so an AI (or a person) can fill in a beginner path that actually reaches a playable ending—without requiring every creative detail to be perfect first.

It is **ideation only** right now. The full planner→builder game pipeline is not included yet.

## The idea in plain language

When you ask an AI to “make a map,” it can invent numbers that break the game: rooms that don’t connect, doors that don’t line up, a start with nowhere to go, or a “win” that can never happen.

So we split map decisions into two kinds of **gates**:

### Deterministic gates (hard numbers)

These are **required**. They have minimum viable values—size, exits, start point, goal, connectivity, at least one enemy for the current Home FPS rules, and so on. If any of these are missing or nonsense, the map fails the beginner test. The AI is not allowed to “get creative” below those floors.

### Generalistic gates (open / flavorful)

These are **open to interpretation**: mood, color palette, room names, optional side rooms, whether to drop a health pack, and similar. The AI fills them with **safe but flavorful defaults** and **flags** which ones a human might want to tweak (`leave`, `optional`, `suggested`, or `blocked`).

Creative fill must never break a deterministic gate.

## What “done” means for a beginner path

**Completion** is not “every gate filled perfectly.”

A beginner path **passes** when a first-time player can move from **start to finish** in a coherent world: no dead-end-only route, no nonsense required values, and a real end state (for our Home FPS target: reach the goal and clear the required grunts). Flavor can still be rough.

## What’s in this repo

| Path | What |
| --- | --- |
| [`ideation/MAP_BUILDING_GATES_PHASE1.md`](ideation/MAP_BUILDING_GATES_PHASE1.md) | Full Phase 1 gate lists, MV numbers, completion definition, Phase 2 readiness notes |
| [`ideation/DECISION_LOG.md`](ideation/DECISION_LOG.md) | Append-only log of every Phase 1 decision (so nothing is forgotten later) |
| [`ideation/README.md`](ideation/README.md) | Rules for keeping ideation append-only when implementation starts |

## Status

- **Phase 1 (ideation):** complete  
- **Phase 2 (implement on the existing game pipeline):** not started — waiting on an explicit go  
- **Codebase:** not published here yet on purpose

## License / credit

Darkwaters Studio / Doug — exploratory design notes, 2026.
