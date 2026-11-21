# Changelog

## v0.1.0-rc1 (2026-11-21)

Release commit: 030c0fd51676993f645a673fa4ff6ad80c5ec041 on branch `claude/project-thread-32rdr4`. The tag waits for Shreyas, see [docs/HUMAN_STEPS.md](docs/HUMAN_STEPS.md).

- Seeded generator for three table kinds with nine named messes and ground truth.
- Plan language with 12 operations. Each one checks its own arguments, and the validator follows the header through the plan.
- Executor that runs a plan on a copy, logs every change in `changes.csv` and can replay the log.
- Profiler, verifier, rule baseline and an LLM planner with fixture replay.
- Benchmark of 40 development and 24 held out datasets with bootstrap intervals, plus a second held out run on new seeds.
- README tables, the demo page and the CI check all come from the results files.
