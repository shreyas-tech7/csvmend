# Interview questions and answers

Each answer points at code (file and function) or a result (file and field). Numbers come from `results/bench.json` and `results/bench_seed2.json`, run on 2026-11-21 with the rule baseline. No LLM run exists yet.

**1. What does csvmend do, in one breath?**
It cleans a messy CSV with a short JSON plan that a person can read before it runs. Plain code checks the plan (`plan.py`, `validate_plan`), runs it on a copy (`executor.py`, `run`), logs every change in `changes.csv` and checks the output against a schema (`verifier.py`, `verify`).

**2. Why a plan in a small language instead of letting the LLM write Python?**
Three reasons. A plan is data, so it cannot open files, call the network or loop forever. Each of the 12 operations checks its own arguments in `plan.py` (`OPS`, `check_step`), so a bad plan fails before any row changes. And a person can read nine short steps in a minute, which is not true of 200 lines of generated pandas. The cost is reach: a mess that no operation covers stays unfixed. Shifted rows are the example (question 9).

**3. Why cap the language at 12 operations?**
A small language is easier for a model to use well and easier for a person to audit. `tests/test_plan.py` asserts the count, so adding a thirteenth operation is a decision, not a drift. New ideas go to `docs/PROPOSALS.md`.

**4. How does the validator catch a step that names a missing column?**
`validate_plan` keeps a copy of the header and passes it through each step with `apply_header`. A rename changes the name, a split adds columns and a merge removes them. If step 5 uses a column that step 3 renamed away, the error names step 5 before anything runs.

**5. What does the LLM see?**
The target schema, the column profile and at most 20 sampled rows. `planners.py`, `build_prompt` raises an error if it gets more than 20 rows. `profiler.py` takes its examples only from the same 20 row sample. A test in `tests/test_pipeline.py` checks that no row id outside the sample appears in the prompt. The schema examples use ids that no row holds (C00000, O00000, SKU-0000) so that test can tell them apart. One nuance: the profile lists the top values of a low cardinality column (at most 80 distinct values) counted over all rows. So the model can see a category value from a row outside the sample, but never a whole row and never an id.

**6. Why does the change log build trust?**
Every change goes through five primitives on `Table` in `executor.py`: set, rename, add column, drop column and drop row. Each one writes a line with the step, the operation, the row, the column, the old value and the new value. `replay` applies the log to the input with the same primitives and checks each old value on the way. `tests/test_executor.py` proves that the replay rebuilds `clean.csv` byte for byte. So the log is not a summary. It is the full change. You can audit any single cell, and reverse one by hand by swapping its old and new values. There is no undo command yet. Files with two columns of the same name are refused at load, because a cell there has no single address.

**7. What does the verifier catch?**
Wrong columns, values of the wrong type, values out of range, values outside an allowed list, a key that repeats and a run that dropped more than a fifth of its rows (`verifier.py`, `MAX_DROP`). On the held out sets it passed every check on 16 of 24 outputs, and all 8 failures were the row count check (`results/bench.json`, `planners.rules.heldout.verifier_pass` and the `checks_failed` lists).

**8. What does the verifier miss?**
A wrong value of the right type. If `03/04/2025` means April 3 and the plan reads it as March 4, the date is valid and in range, so every check passes. It also cannot see a bad merge of two real customers that look alike. That is why the benchmark scores against ground truth, and why the plan is shown to a person first.

**9. Where does the rule baseline fail?**
Shifted rows. A row with a stray extra field has every value under the wrong column. No operation can shift it back, so the plan drops it. Held out row recall for that mess is low (README table, `shifted rows` row). The repair is a proposal in `docs/PROPOSALS.md`.

**10. How do you know the scores are not leaking from the generator?**
I do not fully know, and the README says so. The same person wrote the generator and the rules. The guard is the held out set: new seeds (1000 to 1023), four to six messes per file instead of three, a higher mess rate and only mixes that no development set uses (`bench.py`, `suite`). Because the first held out run looked very good, a second one ran on seeds 2000 to 2023 and gave about the same numbers (`results/bench_seed2.json`). Both are in the README. A real export would still be the true test, and that is a human check.

**11. Why bootstrap over datasets and not over cells?**
Cells in one file are not independent. One bad date format breaks a whole column. Resampling whole datasets 2000 times with seed 0 gives an interval that reflects file to file variation (`bench.py`, `interval`).

**12. Why split cell accuracy and row recall?**
If a dropped row also counted as wrong cells, one loss would count twice. Cell accuracy uses only rows that reached the output. Row recall counts the rows that did not (`score.py`, `score`).

**13. How is duplicate F1 computed?**
The generator records which rows are copies. The executor logs each row that `fuzzy_dedupe` drops and the row it kept. The score compares unordered pairs, so it does not matter which copy survives. Held out duplicate F1 for the rule baseline is in the README table.

**14. Why does a blanked cell have an empty ground truth value?**
No cleaner can know a value that the file lost. If the truth kept the old value, every planner would lose points for a fact it could not see, and a planner that guessed would win by luck. csvmend never guesses a value.

**15. What did the build get wrong along the way?**
Three live bugs, all found on development data or the demo, plus one test gap and a round of fixes from the outside review. The profiler read shifted rows into column stats, which misled the date and split rules (dev28, dev34). It hid category values in small tables, so typos went unmapped in the 10 row demo. And the customer dedupe merged different people with the same name until phone joined the dedupe columns (dev03, dev15, dev21, dev39). The test gap: schema example ids matched real ids, so the prompt test could not tell them apart. The outside review then found that duplicate column names lost data with no log entry, that rename swaps and chains passed the validator but crashed the executor, and that large integer ids lost digits in `cast`. All are fixed with tests. Each one is in `BLOCKERS.md` or `DECISIONS.md`.

**16. What would you do next?**
First, a record run with one free model, which needs a key (`docs/HUMAN_STEPS.md`). Second, a repair loop: when the verifier fails, the planner gets the failures and edits its plan once. Third, an operation that repairs shifted rows. All three are in `docs/PROPOSALS.md`.
