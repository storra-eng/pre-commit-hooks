# pre-commit-hooks

Storra's shared pre-commit hooks, one module per hook in `storra_pre_commit_hooks/` (the layout of
`pre-commit/pre-commit-hooks`). Started with `file-token-budget` (STO-1145), which replaced the per-repo
`scripts/check-file-token-budget.{py,mjs}` copies.

## Rules

- Stdlib-only Python, one module per hook; no dependencies. Keep the repo free of Storra-specific values: it is meant to be
  consumable by public repos.
- Behaviour changes need a test in `tests/` first. Run `python3 -I -m unittest discover -s tests`.
- Release: land on `main`, tag `vX.Y.Z` (semver; a new generic exemption is minor, a changed rule is major).
  Then bump `rev:` in each consumer's `.pre-commit-config.yaml`.
- Generic exemptions only. A path specific to one repo goes in that repo's `.token-budget-exempt`.
- Consumers: cyrus, hive, skills, claude-plugins, agent-automation, canos, repo-template (pre-commit); storra (husky
  runs `pre-commit run file-token-budget`).

## Landing

Work in a `git gtr` worktree and push straight to `main`; no PR. Never `--no-verify`.

## Agent instructions

`AGENTS.md` is a symlink to this file.
