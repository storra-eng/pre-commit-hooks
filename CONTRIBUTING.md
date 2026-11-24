# Contributing

Developer docs for this repository. The README covers what it is and how to use it.

## Setup

| Step | Command |
|---|---|
| Install dependencies | none (stdlib-only Python 3.8+) |
| Git hooks (once per clone; worktrees share it) | `brew install pre-commit` (or `pipx install pre-commit`), then `pre-commit install` |

## Tests and checks

| Check | Command |
|---|---|
| Full test suite | `python3 -I -m unittest discover -s tests` |

Run the full suite before landing a meaningful change.

## Adding or changing a hook

| Step | Where |
|---|---|
| Hook code | `storra_pre_commit_hooks/<hook>.py` with a `main()` |
| Entry point | `pyproject.toml` `[project.scripts]` and `.pre-commit-hooks.yaml` |
| Tests | `tests/test_<hook>.py`; behaviour changes get a failing test first |
| Docs | a row in the README table |
| Release | land on `main`, tag `vX.Y.Z`, bump `rev:` in each consumer repo |

Hooks stay stdlib-only and free of Storra-specific values: this repo is public and other public repos pin it.

## Git hooks

Commits are checked by [pre-commit](https://pre-commit.com).

| Hook | Blocks |
|---|---|
| file-token-budget | a new file, or a change that grows one, past 5,000 tokens (runs this repo's own code) |
| gitleaks | a secret in the staged diff (false positive: add its fingerprint to `.gitleaksignore`) |
| actionlint | an invalid workflow under `.github/workflows/` (unknown runner labels go in `.github/actionlint.yaml`) |

The file-size limit counts bytes / 4; the error explains how to split the file. Repo-specific exemptions, with a
reason, go in `.token-budget-exempt`.

## Landing changes

Work in a `git gtr` worktree, then rebase onto `origin/main` and push straight to `main`: no pull request. Never
commit in the main checkout, never force-push `main`, never `--no-verify`. Details: `CLAUDE.md` and
`.claude/rules/git.md`.
