# Contributing

1. Run `./init.sh`. It makes `.venv`, installs the dev tools, lints, checks links and runs every test offline.
2. Write a failing test first, then the code.
3. Keep the plan language at 12 operations. A new operation needs a proposal in [docs/PROPOSALS.md](docs/PROPOSALS.md) and a reason to drop an old one.
4. Never type a number into the README. Run `csvmend bench`, then `csvmend readme`. The tests fail if the README and the results files disagree.
5. Use synthetic data only. Tests may not open network connections, and a guard in `tests/conftest.py` stops them.
6. Run `gitleaks git --pre-commit --redact --staged --verbose` before each commit.
7. Write docs in plain words. The writing rules test in `tests/test_repo.py` checks dashes, semicolons and a short list of filler words.
