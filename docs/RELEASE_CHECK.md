# Release check

Run on 2026-11-21 on branch `claude/project-thread-32rdr4`.

| Step | Command | Result |
| --- | --- | --- |
| Code review (Ponytail rules, by hand) | read the branch diff | One must fix: a model answer with no JSON crashed the whole benchmark. `bench.py` `run_one` now counts it as a rejected plan, with a test. Fixed the fixture path in the `LLMPlanner` docstring. No extra layers found |
| Security audit | skipped | The brief says skip it. No sign-in, personal data or payments |
| Secret scan, full history | `gitleaks git -v .` | no leaks found |
| Dependency audit | `pip-audit -r <dev deps from the venv> --no-deps --disable-pip` | No known vulnerabilities found. The package has no runtime dependencies |
| Security lint | `ruff check --select S src scripts` | 7 findings, all accepted: 6 are S311 (seeded `random.Random` for data generation and the bootstrap, no crypto use) and 1 is S101 (the module level assert that caps the plan language at 12 operations, also checked by a test) |
| Workflow lint | `actionlint .github/workflows/*.yml` | clean |
| Links | `scripts/check_links.py` | 0 problems. The CI badge is listed as not checked |
| Humanizer rules (by hand) | `tests/test_repo.py::test_writing_rules` | README and docs pass: no em dashes, no dashes as punctuation, no semicolons in prose, no listed buzzwords |
| CI on GitHub | Actions runs on the branch | green on Python 3.11 |
| Outside check | separate reviewer subagent, fresh clone, `./init.sh` | Items 1, 2, 3, 5, 6 and 7 pass. Item 4 passes for the rule baseline and is blocked for the free model column (F12), which the reviewer found stated honestly in four places. The reviewer found nine weak spots. Fixed with tests: duplicate column names lost data with no log entry, rename swaps and chains and a split into its own name crashed the executor, `cast` lost digits on long ids, fuzzy_dedupe merged blank values, a non string `op`, a `%Q` date format, blank lines read as rows, CLI tracebacks, an output folder made for a rejected plan and `connect_ex` outside the network guard. Logged as README limits: commas as decimal marks and silent case collisions in `map_values`. Doc fixes: the README now names the 95% interval in the results block and the dup F1 dataset count, and INTERVIEW_QA answers 5, 6 and 15 match the code. Both benchmarks were rerun after the fixes and every metric stayed the same |
| Clean tree and flags | `git status`, feature_list.json | clean after the release commit. Every `passes` flag matches a passing check. F12 stays false with its row in BLOCKERS.md |
