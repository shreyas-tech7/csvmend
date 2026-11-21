# Handover

Done: everything in feature_list.json except F12 (record run with a free model). See PROGRESS.md.

Next, on a machine that can reach a free provider:

```bash
./init.sh
source .venv/bin/activate
set -a && . ./.env && set +a      # GROQ_API_KEY or OPENROUTER_API_KEY, see .env.example
csvmend bench --llm groq:llama-3.3-70b-versatile --record
csvmend readme
./init.sh
```

Then set F12 to true, remove its row from BLOCKERS.md and commit `fixtures/llm/`, `results/` and `README.md` together. After that the stretch goal (plan repair loop, docs/PROPOSALS.md) can start.

Open decisions: whether the 12 operation cap should grow for a shifted row repair (docs/PROPOSALS.md).
