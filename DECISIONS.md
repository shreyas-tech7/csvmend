# Decisions

One line per choice: what I picked, what else I weighed, and why.

- 2026-11-21 Name: `csvmend`. PyPI and npm both answered 404 and a web search showed no well known GitHub project with that name. The backup `tidyplan` was not needed. Repo name matches.
- 2026-11-21 Branch: `claude/project-thread-32rdr4`, not `claude/build-csvmend`. The session's git rules allow only that branch, and the brief's rule 11 says to use the allowed branch.
- 2026-11-21 Clone location: `/home/user/csvmend`, the clone the session already had, not `~/work/csvmend`. Same origin, so nothing changes for the coordinator.
- 2026-11-21 Planners get the user's target schema (column names, types, ranges, allowed values, units, key, dedupe columns) next to the profile. Weighed: profile only. Picked schema because a cleaner needs a target, the schema holds no rows from the file, and the verifier needs the same spec. The 20 row limit still holds.
- 2026-11-21 Ground truth for a blanked cell is an empty cell, not the old value. No cleaner can know a value that the file lost. Guessing would only add noise to the score.
- 2026-11-21 Currency mess keeps one currency (USD) and changes only symbols and locale formats ($1,234.50, US$, USD, 1.234,50, 1 234,50 $). Weighed: mixing EUR with a fixed rate. Picked formats only, so the right answer is never a guess about an exchange rate.
- 2026-11-21 Shifted rows (one stray empty field) are detected and dropped with `drop_rows where ragged`. None of the 12 operations can repair them, and the cap stays. The repair idea is in docs/PROPOSALS.md. Row recall for that mess shows the cost honestly.
- 2026-11-21 Cell accuracy counts only rows that reach the output. Row recall counts lost rows. Keeping the two apart stops a dropped row from being counted twice.
- 2026-11-21 Duplicate F1 is computed on unordered (kept, dropped) row pairs from the dedupe log, so it does not matter which copy a cleaner keeps.
- 2026-11-21 Numbers compare with a 0.006 tolerance because unit round trips (kg to lb to kg) can move the third decimal. Everything else compares as exact strings.
- 2026-11-21 Intervals: 95% percentile bootstrap, 2000 resamples over datasets, seed 0. Datasets are the unit because cells inside one dataset are not independent.
- 2026-11-21 Held out sets: seeds 1000 to 1023, four to six messes, mess rate 0.35, only mixes that no development set uses. Development sets: seeds 0 to 39, three messes, rate 0.3.
- 2026-11-21 I looked at the held out numbers once, early, before two fixes. Both fixes came from bugs seen on development data or the demo: the profiler read shifted rows into column stats (dev28, dev34), and it hid category values in small tables (the 10 row demo). No rule was tuned against a held out result.
- 2026-11-21 Held out cell accuracy looked very good, so I ran a second held out set with new seeds (2000 to 2023) as the truth rules ask. Both runs are in the README.
- 2026-11-21 The profiler skips rows with the wrong field count in its column stats. Those rows put values under the wrong column and mislead every planner.
- 2026-11-21 Schema examples use ids that no data row holds (C00000, O00000, SKU-0000), so the prompt test can prove that no unsampled row id reaches the model.
- 2026-11-21 The rule baseline always adds fuzzy_dedupe on the schema's dedupe columns with threshold 0.92. I picked it by reasoning about distinct orders that share a customer and a category, not by a sweep.
- 2026-11-21 The customer schema dedupes on first name, last name, email and phone. With name and email only, dev sets showed false merges of different customers with the same name (dev03, dev15, dev21, dev39), because their emails differ by two digits. Phone tells them apart.
- 2026-11-21 No skill installs. The permission system denied `npx skills add`, so I did not retry. Ponytail rules (small plain code), caveman (terse status) and humanizer (plain docs) were applied by hand.
