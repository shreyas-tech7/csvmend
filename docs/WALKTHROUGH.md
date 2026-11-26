# Walkthrough

A tour of every file. Short sentences, one idea each.

## The idea in one paragraph

A messy CSV goes in. A profiler writes a short summary of each column. A planner reads the summary and writes a plan. The plan is JSON data, not code. Plain Python checks the plan and runs it on a copy of the file. Every changed cell goes into a log. A verifier checks the output against a schema. In the benchmark, a score compares the output with the clean table that the generator kept.

## Top folder

- `README.md` is the front page. Its number blocks are written by `csvmend readme`. Do not edit them by hand.
- `init.sh` is the one command to set up and test. It makes `.venv`, installs, lints, checks links and runs every test.
- `pyproject.toml` lists the package, the `csvmend` command and the dev tools. The package has no runtime dependencies.
- `CLAUDE.md` tells an agent what to read first.
- `PROJECT_CONTEXT.md` is the short brief: what the project is and what done means.
- `PROGRESS.md` says where the build stands. `HANDOVER.md` says what to do next.
- `feature_list.json` lists each feature, the command that proves it and a `passes` flag.
- `DECISIONS.md` holds each choice and its reason. `BLOCKERS.md` holds each failure and the fallback.
- `CHANGELOG.md` lists releases. `CONTRIBUTING.md` says how to change the code.
- `.env.example` names the provider keys. The real `.env` is never committed.
- `.pre-commit-config.yaml` runs gitleaks before each commit.

## The library: `src/csvmend/`

- `tables.py` makes clean tables. There are three kinds: customers, orders and inventory. Each kind has a schema with column types, ranges, allowed values, a key and the columns used to find duplicates. A seed fixes every value.
- `messes.py` breaks a clean table on purpose. It has nine messes, for example mixed date formats, money in many formats, typos in categories and near duplicate rows. It returns the messy rows and the ground truth: the clean rows, which cells each mess touched and which rows are copies.
- `plan.py` defines the plan language. `OPS` holds the 12 operations and the check for each argument. `validate_plan` checks every step and also follows the header through the plan, so a step that names a missing column fails before anything runs.
- `executor.py` runs a plan. `load` reads the file and fixes the encoding. `Table` holds the rows and has five primitives: set a cell, rename, add a column, drop a column and drop a row. Every operation uses only these five, and each one writes a log line. `run` writes `clean.csv`, `plan.json`, `changes.csv` and `run.json` to a new folder. It refuses to write over the input. `replay` rebuilds the output from the input and the log.
- `profiler.py` summarizes each column. It counts value kinds, writes shapes such as `99/99/9999`, counts null words and lists top values when a column has few of them. It shows examples only from a fixed sample of 20 rows.
- `verifier.py` checks a cleaned table against the schema: columns, types, ranges, allowed values, a unique key and how many rows were dropped.
- `planners.py` holds three planners. `noop_plan` does nothing and gives the floor. `rule_plan` maps profile patterns to steps. `LLMPlanner` builds a prompt from the schema, the profile and at most 20 rows, then reads the plan out of the answer. In replay mode it reads saved answers from `fixtures/llm/`, keyed by a hash of the prompt. No answers are saved yet, because no record run could reach a provider. Record mode calls a free provider and needs a key.
- `score.py` compares an output with the ground truth. It gives cell accuracy, row recall and duplicate F1, for all cells and for each mess.
- `bench.py` builds the suite of 40 development and 24 held out datasets, runs each planner on each one and adds bootstrap intervals.
- `report.py` writes the README number blocks and `docs/index.html` from the results files. `csvmend readme --check` fails if they are stale.
- `cli.py` is the command line: `generate`, `profile`, `prompt`, `plan`, `run`, `verify`, `replay`, `bench`, `readme` and `demo`.

## Tests: `tests/`

- `conftest.py` blocks network access in every test. `test_network_guard.py` proves the guard works.
- `test_plan.py` checks valid and invalid arguments for each of the 12 operations.
- `test_executor.py` checks that the input file never changes, that each change is logged and that a replay of the log rebuilds the output.
- `test_pipeline.py` checks the generator, the profiler, the verifier, the rule baseline, the scores, the LLM prompt and fixture replay.
- `test_repo.py` checks the README order, that README numbers match the results files, the writing rules, the shipped files and the feature flags.

## Results: `results/`

- `bench.json` is the main run on held out seeds 1000 to 1023.
- `bench_seed2.json` is a second held out run on seeds 2000 to 2023. It exists because the first run looked very good.

## Scripts: `scripts/`

- `check_links.py` checks every relative link and anchor in the Markdown and HTML files.
- `make_social_preview.py` draws `docs/social-preview.png` at 1280 by 640 pixels.

## Docs: `docs/`

- `index.html` is the demo page. It shows the messy table, the plan and the clean table with changed cells marked.
- `DEMO.md` is a real terminal transcript.
- `PLAN.md` is the build plan. `PROPOSALS.md` lists ideas for later.
- `INTERVIEW_QA.md` has questions and answers about the design.
- `HUMAN_STEPS.md` lists what only Shreyas can do.
- `RELEASE_CHECK.md` records the checks run before the release candidate.
- `build/BUILD_PROMPT.md` is the full prompt that the build agent followed.

## CI: `.github/workflows/`

- `ci.yml` runs `./init.sh`, `csvmend readme --check` and `csvmend demo` on Python 3.11.
- `bench.yml` runs the full benchmark, only by hand.
