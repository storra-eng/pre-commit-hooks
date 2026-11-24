import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import file_token_budget as ftb  # noqa: E402

BIG = ftb.MAX_BYTES + 1000
HOOK = [sys.executable, os.path.join(os.path.dirname(__file__), "..", "file_token_budget.py")]


def fake(staged, head=None, binary=()):
    head = head or {}
    return dict(
        size=lambda spec: staged.get(spec[1:]) if spec.startswith(":") else head.get(spec[5:]),
        binary=lambda spec: spec[1:] in binary,
    )


class Unit(unittest.TestCase):
    def names(self, paths, **kw):
        return [p for p, _ in ftb.find_offenders(paths, **kw)]

    def test_new_over_blocked_at_limit_passes(self):
        self.assertEqual(self.names(["a", "b"], **fake({"a": ftb.MAX_BYTES + 1, "b": ftb.MAX_BYTES})), ["a"])

    def test_legacy_shrink_same_pass_grow_blocked(self):
        head = {"a": BIG, "b": BIG, "c": BIG}
        self.assertEqual(self.names(["a", "b", "c"], **fake({"a": BIG - 1, "b": BIG, "c": BIG + 1}, head)), ["c"])

    def test_under_limit_growing_past_blocked(self):
        self.assertEqual(self.names(["a"], **fake({"a": ftb.MAX_BYTES + 1}, {"a": 100})), ["a"])

    def test_rename_measured_against_origin(self):
        head = {"old/a": BIG, "old/b": BIG}
        self.assertEqual(
            self.names(["new/a", "new/b"], renamed_from=lambda p: p.replace("new/", "old/"),
                       **fake({"new/a": BIG, "new/b": BIG + 1}, head)), ["new/b"])

    def test_merge_head_identical_skipped_resolution_measured(self):
        self.assertEqual(
            self.names(["from-main", "resolved"], same_as_merge=lambda p: p == "from-main",
                       **fake({"from-main": BIG, "resolved": BIG})), ["resolved"])

    def test_exempt_and_binary(self):
        paths = ["package-lock.json", "uv.lock", "db/migrations/1.sql", "x.bin", ".tessl/a.md", "n/node_modules/a.js"]
        self.assertEqual(self.names(paths, **fake({p: BIG * 3 for p in paths}, binary={"x.bin"})), [])
        self.assertFalse(ftb.is_exempt("src/A.tsx"))

    def test_repo_exemptions_glob_and_regex(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, ".token-budget-exempt"), "w") as f:
                f.write("# why\ndocs/legal/*.md  # wide table\nre:^encore/[^/]+\\.ts$  # mirrors\n\n")
            extra = ftb.repo_exemptions(d)
        self.assertTrue(ftb.is_exempt("docs/legal/x.md", extra))
        self.assertTrue(ftb.is_exempt("encore/a.ts", extra))
        self.assertFalse(ftb.is_exempt("encore/sub/a.ts", extra), "regex stays single-level")
        self.assertFalse(ftb.is_exempt("docs/other.md", extra))

    def test_advice(self):
        msg = ftb.split_advice("src/Big.tsx", 60000)
        self.assertIn("src/Big.tsx is ~15,000 tokens", msg)
        self.assertIn("Split it into ~5 files", msg)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.git("config", "commit.gpgsign", "false")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *a):
        return subprocess.run(["git", *a], cwd=self.d, capture_output=True, text=True, check=True)

    def write(self, name, n):
        p = os.path.join(self.d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write("x" * n)
        self.git("add", name)

    def run_hook(self):
        return subprocess.run(HOOK, cwd=self.d, capture_output=True, text=True).returncode

    def test_blocks_new_big_file_and_allows_small(self):
        self.write("a.md", 30000)
        self.assertEqual(self.run_hook(), 1)
        self.git("reset", "-q")
        self.write("a.md", 100)
        self.assertEqual(self.run_hook(), 0)

    def test_ratchet_and_rename(self):
        self.write("a.md", BIG)
        self.git("commit", "-qm", "legacy")
        self.write("a.md", BIG)  # unchanged-size edit
        self.assertEqual(self.run_hook(), 0)
        self.git("mv", "a.md", "b.md")
        self.assertEqual(self.run_hook(), 0, "plain rename keeps its place in the ratchet")
        self.write("b.md", BIG + 5)
        self.assertEqual(self.run_hook(), 1, "growing a renamed legacy file is blocked")

    def test_exempt_file(self):
        self.write("gen/a.md", 30000)
        self.assertEqual(self.run_hook(), 1)
        self.write(".token-budget-exempt", 0)
        with open(os.path.join(self.d, ".token-budget-exempt"), "w") as f:
            f.write("gen/*  # generated\n")
        self.git("add", ".token-budget-exempt")
        self.assertEqual(self.run_hook(), 0)

    def test_merge_skips_paths_already_on_merged_branch(self):
        self.write("seed", 1)
        self.git("commit", "-qm", "seed")
        self.git("checkout", "-q", "-b", "other")
        self.write("big.md", BIG)
        self.git("commit", "-qm", "big on other (hooks skipped)")
        self.git("checkout", "-q", "main")
        self.write("m.txt", 1)
        self.git("commit", "-qm", "diverge")
        subprocess.run(["git", "merge", "--no-commit", "--no-ff", "other"], cwd=self.d, capture_output=True)
        self.assertTrue(os.path.exists(os.path.join(self.d, ".git", "MERGE_HEAD")))
        self.assertEqual(self.run_hook(), 0)


if __name__ == "__main__":
    unittest.main()
