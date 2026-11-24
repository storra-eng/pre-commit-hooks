# file-token-budget

The one shared file-token-budget pre-commit hook for every storra-eng repo (STO-1145). Replaces the per-repo
`scripts/check-file-token-budget.{py,mjs}` copies.

## Rules

- Stdlib-only Python in a single module; no dependencies.
- Behaviour changes need a test in `tests/test_budget.py` first. Run `python3 -I -m unittest discover -s tests`.
- Release: land on `main`, tag `vX.Y.Z` (semver; a new generic exemption is minor, a changed rule is major).
  Then bump `rev:` in each consumer's `.pre-commit-config.yaml`.
- Generic exemptions only. A path specific to one repo goes in that repo's `.token-budget-exempt`.
- Consumers: cyrus, hive, skills, claude-plugins, agent-automation, canos, repo-template (pre-commit); storra (husky
  runs `pre-commit run file-token-budget`).

## Landing

Work in a `git gtr` worktree and push straight to `main`; no PR. Never `--no-verify`.

## Agent instructions

`AGENTS.md` is a symlink to this file.
