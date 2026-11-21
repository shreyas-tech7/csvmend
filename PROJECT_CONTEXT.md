# Project context: csvmend

## What it is

csvmend cleans messy CSV files. A planner writes a short plan in a JSON language with 12 operations. Plain code checks the plan, runs it on a copy, logs every change and verifies the result. A seeded generator makes messy tables with ground truth, so accuracy is a measured number.

## Status

v0.1.0-rc1 on branch `claude/project-thread-32rdr4`. Rule baseline measured on 40 development and 24 held out datasets, plus a second held out run. The LLM planner and its fixture replay are built and tested. The record run is blocked because the build machine cannot reach any provider.

## Stack

Python 3.11 or newer, standard library only (`csv`, `json`, `difflib`, `urllib`). pytest and ruff for development. uv makes the `.venv`.

## Commands

- `./init.sh`: install, lint, link check, all tests offline
- `csvmend generate`, `profile`, `plan`, `prompt`, `run`, `verify`, `replay`
- `csvmend bench`: writes `results/bench.json`. `csvmend bench --held-base 2000 --out results/bench_seed2.json` writes the second held out run
- `csvmend readme`: writes the README number blocks and `docs/index.html`. `--check` fails when stale
- `csvmend demo`: the terminal demo

## Layout

- `src/csvmend/tables.py`: clean synthetic tables and their schemas
- `src/csvmend/messes.py`: the 9 named messes and the ground truth
- `src/csvmend/plan.py`: the plan language and its argument checks
- `src/csvmend/executor.py`: load, the 12 operations, the change log, replay
- `src/csvmend/profiler.py`: column summaries and the 20 row sample
- `src/csvmend/planners.py`: no plan, rule baseline, LLM planner
- `src/csvmend/verifier.py`: schema checks on the output
- `src/csvmend/score.py`, `bench.py`, `report.py`: metrics, benchmark, generated docs
- `tests/`: offline tests. `conftest.py` blocks network access

## Rules

- Plans are data, never code. The LLM never edits data. It sees the schema, the profile and at most 20 rows.
- Cap the language at 12 operations. New ideas go in `docs/PROPOSALS.md`.
- Do not tune rules on the held out sets.
- Never type numbers into the README.

## Skills that fit

superpowers TDD, systematic debugging and verification. Ponytail rules by hand (the skill install was denied).

## Do not read

`.venv/`, `.cache/`, `results/*.json` in full (large, read with jq), `docs/build/BUILD_PROMPT.md` unless you need the brief.
