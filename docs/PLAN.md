# Build plan

From the build order in the brief. Each step ends with tests and a commit.

| Step | What | Files | Status |
| --- | --- | --- | --- |
| 1 | Initializer and clean table generator | `init.sh`, `pyproject.toml`, `tables.py` | done |
| 2 | Mess generator with ground truth | `messes.py` | done |
| 3 | Plan language and executor | `plan.py`, `executor.py` | done |
| 4 | Change log and replay test | `executor.py`, `tests/test_executor.py` | done |
| 5 | Profiler | `profiler.py` | done |
| 6 | Verifier | `verifier.py` | done |
| 7 | Rule baseline | `planners.py` | done |
| 8 | Metrics and benchmark | `score.py`, `bench.py`, `results/` | done |
| 9 | LLM planner with replay, prompt test | `planners.py` | done. Record run blocked (F12) |
| 10 | CLI, README generator, demo page | `cli.py`, `report.py`, `docs/index.html` | done |
| 11 | Repo quality bar, study kit | `tests/test_repo.py`, `docs/` | done |
| 12 | Release check and hand-off | `docs/RELEASE_CHECK.md`, `docs/HUMAN_STEPS.md` | see PROGRESS.md |
| Stretch | Plan repair loop | none | not started. It needs a real model run first |
