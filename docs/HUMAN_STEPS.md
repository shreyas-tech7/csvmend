# Human steps

Only Shreyas can do these. Do them in order.

Release commit: 030c0fd51676993f645a673fa4ff6ad80c5ec041 on branch `claude/project-thread-32rdr4`.

1. Open a pull request from `claude/project-thread-32rdr4` into `main` on GitHub (the session page has a button for it). Read the diff. Merge with a merge commit, so the release commit stays in the history of `main`. The project coordinator may already have done this.
2. Create the tag on the release commit. Either run `git fetch origin`, then `git tag -a v0.1.0-rc1 030c0fd51676993f645a673fa4ff6ad80c5ec041 -m "Release candidate 1"`, then `git push origin v0.1.0-rc1`, or create a pre-release with that tag on the GitHub releases page.
3. Run the secret scan once more: `gitleaks git -v .` in a fresh clone.
4. Check that the CI run on the merge commit is green on the Actions page.
5. Make the repo public. Done 2026-11-26: the repo is public.
6. Pages: not needed. The demo page `docs/index.html` opens from disk. Turn on Pages from `/docs` only if you want it online.
7. Upload `docs/social-preview.png` in Settings, General, Social preview. Fill in the About box from [GITHUB_ABOUT.md](GITHUB_ABOUT.md) and the topics from [topics.txt](topics.txt) if the coordinator did not.
8. Pin the repo or list it in your profile README.
9. Publish to PyPI with trusted publishing, if you want the package public. The name `csvmend` was free on PyPI on 2026-11-21.
10. Record run with one free model. The build machine could not reach api.groq.com or openrouter.ai, and no key was set. On a machine with network access, put a free key in `.env` (for example `GROQ_API_KEY`, see `.env.example`), check the free limits on the provider's page, then run:

    ```bash
    set -a && . ./.env && set +a
    csvmend bench --llm groq:llama-3.3-70b-versatile --record
    csvmend readme
    ```

    The first command saves each answer in `fixtures/llm/`, so later runs replay it with no key. The second adds the LLM columns to the README tables. Commit `fixtures/llm/`, `results/bench.json` and the README together. Only synthetic data goes to the provider. Then set F12 to true in `feature_list.json` and remove its row from BLOCKERS.md.
11. Decide whether `docs/build/BUILD_PROMPT.md` stays public.
12. Do the human checks listed in the README: read the plan language and the change log format, run csvmend on one real export of your own, and review the benchmark design for leaks between the generator and the rules.
