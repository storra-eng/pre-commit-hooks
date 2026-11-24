# pre-commit-hooks

Storra's [pre-commit](https://pre-commit.com) hooks, one module per hook in `storra_pre_commit_hooks/`.

| Hook id | What it does |
|---|---|
| `file-token-budget` | Blocks a new file, or a change that grows one, past 5,000 tokens (bytes / 4 = 20,000 bytes) |

## Use

```yaml
repos:
  - repo: https://github.com/storra-eng/pre-commit-hooks
    rev: v1.1.0
    hooks:
      - id: file-token-budget
```

Husky repos: `pre-commit run file-token-budget --files .pre-commit-config.yaml` from the hook (`--files` stops
pre-commit stashing the unstaged tree).

## file-token-budget

| Rule | Behaviour |
|---|---|
| Scope | Staged files only (reads blobs, not the working tree) |
| New file | Over the cap: blocked |
| Existing file over the cap | Blocked only if the commit makes it bigger (ratchet against HEAD) |
| Rename | Counts as the file it came from; a copy counts as new |
| Merge commit | Paths identical to `MERGE_HEAD` are skipped |
| Exempt | Lockfiles, generated, vendored, migrations, data, binaries, `.specify/`, `.tessl/` |
| Per-repo exemptions | `.token-budget-exempt` at the repo root, read from the index (stage it) |

`.token-budget-exempt`: one entry per line, each with a `# reason`.

```
docs/legal/*.md                   # fnmatch glob; * also matches /
re:^encore/shared/[^/]+\.ts$      # regex, when a glob is too broad
```

## Develop

```bash
python3 -I -m unittest discover -s tests
```

Add a hook: a module in `storra_pre_commit_hooks/` with a `main()`, an entry in `pyproject.toml` `[project.scripts]` and
`.pre-commit-hooks.yaml`, tests in `tests/`, a row above. Release: push to `main`, tag `vX.Y.Z`, bump `rev:` in each
consumer.
