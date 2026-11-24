# file-token-budget

Pre-commit hook. Blocks a new file, or a change that grows one, past 5,000 tokens (bytes / 4 = 20,000 bytes).

| Rule | Behaviour |
|---|---|
| Scope | Staged files only (reads blobs, not the working tree) |
| New file | Over the cap: blocked |
| Existing file over the cap | Blocked only if the commit makes it bigger (ratchet against HEAD) |
| Rename | Counts as the file it came from |
| Merge commit | Paths identical to `MERGE_HEAD` are skipped |
| Exempt | Lockfiles, generated, vendored, migrations, data, binaries, `.specify/`, `.tessl/` |
| Per-repo exemptions | `.token-budget-exempt` at the repo root |

## Use

```yaml
repos:
  - repo: https://github.com/storra-eng/file-token-budget
    rev: v1.0.1
    hooks:
      - id: file-token-budget
```

Husky repos: `pre-commit run file-token-budget --hook-stage pre-commit` from the hook (see CLAUDE.md).

## `.token-budget-exempt`

One entry per line, each with a `# reason`. Read from the index, so stage the file.

```
docs/legal/*.md                   # fnmatch glob; * also matches /
re:^encore/shared/[^/]+\.ts$      # regex, when a glob is too broad
```

## Develop

```bash
python3 -I -m unittest discover -s tests
```

Release: push to `main`, then tag `vX.Y.Z` and bump `rev:` in each consumer.
