"""Block staged agent-authored files over 5,000 tokens (tokens = bytes / 4, i.e. 20,000 bytes).

Why: an agent pays ~28k tokens to read a 1,500-line file and keeps them for the rest of the
session. Files that stay small can be read whole; big ones get skimmed and edited blind.

Ratchet, not a wall: a file already over the limit on HEAD is blocked only if this commit makes
it bigger, so editing a legacy file never becomes an unpassable gate. New files over the limit
are always blocked.

A rename counts as the file it came from (`git diff -M`), so moving an over-limit file keeps its
place in the ratchet instead of reading as new. A copy counts as a new file.

Merge commits: a path whose staged blob is byte-identical to MERGE_HEAD's is already on the branch
being merged in, so this commit adds nothing new to it and it is skipped. A path that differs from
MERGE_HEAD (a conflict resolution) is still measured.

Only agent-authored text counts. Lockfiles, generated output, binaries, migrations and data are
exempt (EXEMPT below). Add repo-specific exemptions to `.token-budget-exempt` at the repo root, one
per line, each with a reason in the comment (`#` starts a comment):
  - `src/gen/*.ts`        an fnmatch glob against the repo-relative path (`*` also matches `/`)
  - `re:^a/[^/]+\\.ts$`   a regular expression searched in the path, when a glob is too broad
There is deliberately no per-commit escape hatch.

Stdlib-only, reads staged blobs and the staged exemption file (never the working tree).
"""
import fnmatch
import os
import re
import subprocess
import sys

MAX_TOKENS = 5000
BYTES_PER_TOKEN = 4
MAX_BYTES = MAX_TOKENS * BYTES_PER_TOKEN
EXEMPT_FILE = ".token-budget-exempt"

EXEMPT = [re.compile(p) for p in (
    # Lockfiles and resolved dependency manifests.
    r"(^|/)(package-lock\.json|bun\.lockb?|deno\.lock|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock|poetry\.lock|uv\.lock|Pipfile\.lock|Podfile\.lock|Package\.resolved|Gemfile\.lock|composer\.lock|go\.sum|gradle\.lockfile)$",
    r"\.lock$",
    # Generated or vendored output.
    r"(^|/)(generated|__generated__|__snapshots__|node_modules|vendor|Pods|dist)/",
    r"\.(snap|min\.js|min\.css|map|pb\.go|g\.dart|generated\.[a-z]+)$",
    r"(^|/)(openapi|swagger)[^/]*\.(ya?ml|json)$",
    # Immutable history and data, not code an agent edits by reading it.
    r"(^|/)(migrations|alembic/versions)/",
    r"\.(json|csv|tsv|ndjson|jsonl|svg|xml|sql|plist|xcstrings|strings|pbxproj)$",
    # Vendored agent skills and spec-kit scaffolding.
    r"^\.specify/",
    r"^\.tessl/",
)]


def repo_exemptions(text=None):
    """Parse the exemption file into (kind, pattern) pairs, kind 'glob' or 're'.

    Read from the index (never the working tree), so an unstaged edit cannot exempt a file for one commit.
    """
    if text is None:
        p = _git(["show", f":{EXEMPT_FILE}"], text=True)
        if p.returncode != 0:
            return []
        text = p.stdout
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("re:"):
            # A regex may contain '#', so only a trailing ' # reason' is stripped.
            pat = re.split(r"\s+#(?:\s|$)", line[3:], maxsplit=1)[0].strip()
            try:
                out.append(("re", re.compile(pat)))
            except re.error as e:
                sys.exit(f"{EXEMPT_FILE}:{n}: invalid regex {pat!r}: {e}")
        else:
            line = line.split("#", 1)[0].strip()
            if line:
                out.append(("glob", line))
    return out


def is_exempt(path, extra=()):
    if any(r.search(path) for r in EXEMPT):
        return True
    for kind, pat in extra:
        if kind == "re" and pat.search(path):
            return True
        if kind == "glob" and fnmatch.fnmatchcase(path, pat):
            return True
    return False


def split_advice(path, nbytes):
    tokens = -(-nbytes // BYTES_PER_TOKEN)
    parts = -(-nbytes // int(MAX_BYTES * 0.7))
    stem, ext = os.path.splitext(path)
    return "\n".join([
        f"ERROR: {path} is ~{tokens:,} tokens (limit {MAX_TOKENS:,}; tokens = bytes/{BYTES_PER_TOKEN}).",
        f"  Split it into ~{parts} files of well under {MAX_TOKENS:,} tokens each:",
        "  1. Find the seams: sections, classes, exported groups, components, or test groups.",
        f"     (grep -nE '^(class |def |func |export |## |describe)' {path})",
        "  2. Move each cohesive group into a new file beside it, named for what it holds",
        f"     ({stem}-<topic>{ext}, or the language's own convention) - not part1/part2.",
        f"  3. Keep {path} as the entry point: it re-exports/imports the moved symbols (code) or",
        "     links to the new files (docs), so existing imports and links keep working.",
        "  4. Move shared helpers and types to one small file the pieces import; no circular imports.",
        "  5. Re-stage everything (git add) and commit again.",
        "  Do not trim by deleting content or by cramming lines to dodge the count.",
        f"  Generated or data file? Add its glob, with a reason, to {EXEMPT_FILE}.",
    ])


def _git(args, **kw):
    return subprocess.run(["git", *args], capture_output=True, **kw)


def blob_size(spec):
    p = _git(["cat-file", "-s", spec])
    return int(p.stdout) if p.returncode == 0 else None


def is_binary(spec):
    p = _git(["cat-file", "blob", spec])
    return b"\0" in p.stdout[:8000]


def find_offenders(paths, size=blob_size, binary=is_binary, same_as_merge=lambda p: False,
                   renamed_from=lambda p: None, extra=()):
    out = []
    for path in paths:
        if is_exempt(path, extra) or same_as_merge(path):
            continue
        nbytes = size(f":{path}")
        if nbytes is None or nbytes <= MAX_BYTES or binary(f":{path}"):
            continue
        before = size(f"HEAD:{renamed_from(path) or path}")
        if before is not None and before > MAX_BYTES and nbytes <= before:
            continue
        out.append((path, nbytes))
    return out


def staged_paths():
    """Staged paths (added, modified, renamed; a copy counts as a new file) and a map of renamed path -> original."""
    raw = _git(["-c", "core.quotePath=false", "diff", "--cached", "-M", "-l0", "--name-status", "-z",
                "--diff-filter=AMR"], text=True, check=True).stdout.split("\0")
    entries = [e for e in raw if e]
    staged, moved, i = [], {}, 0
    while i < len(entries):
        if entries[i][0] == "R":
            staged.append(entries[i + 2])
            moved[entries[i + 2]] = entries[i + 1]
            i += 3
        else:
            staged.append(entries[i + 1])
            i += 2
    return staged, moved


def rev_parse(spec):
    p = _git(["rev-parse", "-q", "--verify", spec], text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def main():
    staged, moved = staged_paths()
    merge_head = rev_parse("MERGE_HEAD")

    def same_as_merge(path):
        if not merge_head:
            return False
        s = rev_parse(f":{path}")
        return s is not None and s == rev_parse(f"{merge_head}:{path}")

    offenders = find_offenders(staged, same_as_merge=same_as_merge, renamed_from=moved.get,
                               extra=repo_exemptions())
    if offenders:
        print("\n\n".join(split_advice(p, n) for p, n in offenders), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
