#!/usr/bin/env python3
"""Fixture for the --pr-fix push safety rules (pr-fix/stage-06-finish.md): ordinary
non-force push, ancestor check before push, rejected when the PR head moved."""
import shutil, subprocess, tempfile, unittest
from pathlib import Path


def git(cwd, *a, check=True):
    r = subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                       capture_output=True, text=True)
    if check and r.returncode:
        raise AssertionError(r.stderr)
    return r


def commit(repo, name):
    (Path(repo) / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-qm", name)


class PrFixPush(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.remote, self.local, self.other = (self.tmp / n for n in ("remote.git", "local", "other"))
        git(self.tmp, "init", "-q", "--bare", "-b", "pr", str(self.remote))
        git(self.tmp, "clone", "-q", str(self.remote), str(self.local))
        git(self.local, "checkout", "-qB", "pr")
        commit(self.local, "base")
        git(self.local, "push", "-q", "origin", "pr")
        git(self.tmp, "clone", "-q", "-b", "pr", str(self.remote), str(self.other))

    def head(self):
        return git(self.remote, "rev-parse", "pr").stdout.strip()

    def test_fast_forward_push_succeeds(self):
        commit(self.local, "fix")
        git(self.local, "fetch", "-q", "origin", "refs/heads/pr:refs/tmp/pr-head")
        git(self.local, "merge-base", "--is-ancestor", "refs/tmp/pr-head", "HEAD")  # unmoved head passes
        git(self.local, "push", "-q", "origin", "HEAD:refs/heads/pr")
        self.assertEqual(self.head(), git(self.local, "rev-parse", "HEAD").stdout.strip())

    def test_concurrent_update_is_rejected_and_not_overwritten(self):
        commit(self.other, "teammate")
        git(self.other, "push", "-q", "origin", "pr")
        teammate = self.head()
        commit(self.local, "fix")
        git(self.local, "fetch", "-q", "origin", "refs/heads/pr:refs/tmp/pr-head")
        ancestor = git(self.local, "merge-base", "--is-ancestor", "refs/tmp/pr-head", "HEAD", check=False)
        self.assertNotEqual(ancestor.returncode, 0)  # ancestor check refuses first
        push = git(self.local, "push", "-q", "origin", "HEAD:refs/heads/pr", check=False)
        self.assertNotEqual(push.returncode, 0)  # and a plain push is rejected too
        self.assertEqual(self.head(), teammate)


if __name__ == "__main__":
    unittest.main()
