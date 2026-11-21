# Tooling

| Tool | Source | Version | Why | Check result |
| --- | --- | --- | --- | --- |
| superpowers skills | already in the session (claude.ai account) | as installed | plans, TDD, debugging, verification | followed inline to save tokens |
| ponytail, caveman, humanizer, find-skills | `npx skills add ...` | none | code style, terse progress, doc pass, skill search | not installed. The permission system denied the first `npx skills add` on 2026-11-21, so no install was retried. The rules were applied by hand: small plain code, plain word docs, a writing rules test |
| gitleaks | `go install github.com/zricethezav/gitleaks/v8@latest` | v8.30.1 | secret scan before each commit and on full history | installed, see docs/RELEASE_CHECK.md |
| actionlint | `go install github.com/rhysd/actionlint/cmd/actionlint@latest` | at install time | workflow lint | installed, both workflows pass |
| pip-audit | `uv tool install pip-audit` | at install time | dependency audit | see docs/RELEASE_CHECK.md |
| ruff | PyPI (dev extra) | at install time | lint, format, `--select S` | runs in init.sh |
| graphify, cisco-ai-skill-scanner, pre-commit | `uv tool install` | not installed | not needed: 12 source files, no third-party skills installed, gitleaks runs directly | skipped |
| security-audit | session skill | not used | the brief says skip it: no sign-in, personal data or payments | skipped by design |

## Repos from the shared list (GITHUB_REPOS.md)

| Repo | Fit | What happened |
| --- | --- | --- |
| obra/superpowers | yes | already in the session, used inline |
| DietrichGebert/ponytail, JuliusBrussee/caveman, blader/humanizer | yes | install denied by the permission system, rules followed by hand |
| gitleaks/gitleaks | yes | used |
| google/osv-scanner, semgrep/semgrep | partly | api.osv.dev and semgrep.dev did not answer. pip-audit and ruff S rules instead |
| Graphify-Labs/graphify | no | small codebase |
| OmniRoute, litellm, free-llm-api-resources | for record mode | key needed and provider hosts blocked. The record command is in docs/HUMAN_STEPS.md. The planner speaks the OpenAI compatible chat format, so a router would work later |
| meta-llama/PurpleLlama, protectai prompt injection model | idea only | the input is CSV cells, and the model sees 20 rows. A cell that holds instructions could still steer a model. The plan language limits the damage, because a plan cannot do more than the 12 operations. A prompt injection filter is a later idea |
| cisco-ai-defense/skill-scanner, mcp-scanner | no | no skills or MCP server installed |
| NVIDIA/garak | no | needs a model endpoint |
| microsoft/playwright-mcp, crawl4ai, anatomy | no | no UI, no crawling, figure is a stretch |
| rtk-ai/rtk | no | optional, not needed |
| NousResearch/hermes-agent | no | not an agent runtime project |
| coreyhaines31/marketingskills | partly | README structure follows the brief. Not installed |

## Prior work read before building

- CleanAgent (arXiv 2403.08291): an LLM calls a declarative cleaning library. csvmend takes the same idea further with a fixed, checked plan language and a benchmark with ground truth.
- OpenRefine: records operations as JSON and replays them. csvmend's change log works at the cell level instead.
