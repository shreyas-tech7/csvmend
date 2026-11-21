# Proposals

Ideas that are out of scope for v0.1.0. Each one says why it waits.

- **Plan repair loop.** When the verifier fails, the planner gets the failed checks and edits its plan once. This is the stretch goal in the brief. It waits until a real LLM run exists, because the rule baseline cannot learn from failures.
- **An operation that repairs shifted rows.** It would find the empty field that pushed a row one column right and move the values back. It would make 13 operations, so one old operation would have to go, or the cap would change by a decision.
- **Blocking keys for fuzzy_dedupe that survive a typo.** Today the block key is the first two letters of one column. A sorted neighborhood or two block keys would find pairs with a typo in that column.
- **A schema writer.** `csvmend schema data.csv` would draft a schema from the profile for a person to edit. Today the user writes the schema by hand.
- **Excel input.** Read `.xlsx` with the standard library zip reader. Out of scope because formulas and merged cells need their own rules.
