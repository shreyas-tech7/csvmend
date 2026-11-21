# Blockers

| Date | What failed | Exact error | What I did instead |
| --- | --- | --- | --- |
| 2026-11-21 | `npx -y skills add DietrichGebert/ponytail -g -a claude-code -y` | "Permission for this action was denied by the Claude Code auto mode classifier" | Did not retry any skill install. Followed the Ponytail, caveman and humanizer rules by hand. Superpowers skills were already in the session |
| 2026-11-21 | Record mode for the LLM planner (F12) | `curl` to api.groq.com and openrouter.ai answered `000` (proxy refused). No key variables set | Fallback from the brief: the README reports the rule baseline only. The LLM planner, prompt and fixture replay are built and tested. The record command is in docs/HUMAN_STEPS.md |
| 2026-11-21 | api.osv.dev, semgrep.dev | curl answered `000` | pip-audit and `ruff check --select S` instead |
| 2026-11-21 | `gh`, PR creation, tag push, repo settings | not available from this machine (brief) | The coordinator opens the PR, merges, tags and sets About and topics. Values are in docs/GITHUB_ABOUT.md and docs/topics.txt |

| 2026-11-21 | F16 and F17 open until the release check and hand-off finish | not an error | Set to true once docs/RELEASE_CHECK.md and the release SHA exist |

## Bugs found and scored (frequency x severity)

| Bug | Score | Kind | State |
| --- | --- | --- | --- |
| Profiler counted shifted rows in column stats, so the baseline split `ship_to` on the wrong separator | 4 x 4 = 16 | live bug | fixed |
| Profiler hid category values when a table had few rows, so typos stayed | 3 x 3 = 9 | live bug | fixed |
| Schema example ids matched real row ids, so the prompt test could not tell them apart | 2 x 3 = 6 | test gap | fixed |
| fuzzy_dedupe merged different customers with the same name, because the customer dedupe columns were name and email only | 3 x 3 = 9 | live bug | fixed: phone added to the customer dedupe columns, found on dev sets |
| fuzzy_dedupe still misses some held out duplicate pairs and makes a few false merges | 2 x 3 = 6 | live bug | logged as a limit. A fix would mean tuning on held out sets |
| A typo in the first two letters of the blocking column hides a duplicate pair | 2 x 2 = 4 | live bug | logged as a limit |
