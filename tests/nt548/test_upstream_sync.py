"""ops/nt548/upstream_sync.sh on two throwaway git repositories (an "upstream" and a fork of it): nothing new, a
clean merge onto a sync branch, and a conflict that is reported and aborted."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "ops/nt548/upstream_sync.sh"
BASH = shutil.which("bash")
if not BASH or not shutil.which("git") or (os.name == "nt" and "system32" in BASH.lower()):
    pytest.skip("needs a POSIX bash and git", allow_module_level=True)

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@example.com", "SYNC_DATE": "2026-11-28", "GITHUB_OUTPUT": ""}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, check=True, capture_output=True, text=True).stdout.strip()


def commit(repo, path, text, msg):
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text)
    git(repo, "add", path)
    git(repo, "commit", "-q", "-m", msg)


@pytest.fixture
def repos(tmp_path):
    up, fork = tmp_path / "up", tmp_path / "fork"
    up.mkdir()
    git(up, "init", "-q", "-b", "main")
    commit(up, "README.md", "TripGuardian\n", "init")
    git(tmp_path, "clone", "-q", up.as_posix(), fork.as_posix())
    commit(fork, "docs/nt548/README.md", "NT548\n", "nt548 docs")
    return up, fork


def sync(fork, up):
    p = subprocess.run([BASH, SCRIPT.as_posix(), up.as_posix(), "main"], cwd=fork, env=ENV, capture_output=True,
                       text=True)
    assert p.returncode == 0, p.stderr
    return dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)


def test_nothing_new_upstream(repos):
    up, fork = repos
    assert sync(fork, up)["status"] == "up-to-date"
    assert git(fork, "branch", "--show-current") == "main"


def test_new_upstream_commit_is_merged_on_a_sync_branch(repos):
    up, fork = repos
    commit(up, "src/app.py", "print(1)\n", "feature")
    o = sync(fork, up)
    assert o["status"] == "merged" and o["branch"] == "nt548/sync-2026-11-28" and o["commits"] == "1"
    assert git(fork, "branch", "--show-current") == "nt548/sync-2026-11-28"
    assert (fork / "src/app.py").exists() and (fork / "docs/nt548/README.md").exists()
    assert len(git(fork, "log", "-1", "--format=%P").split()) == 2  # --no-ff: a merge commit
    assert sync(fork, up)["status"] == "up-to-date"  # the next run finds nothing new


def test_conflict_is_reported_and_aborted(repos):
    up, fork = repos
    commit(up, "README.md", "TripGuardian v2\n", "upstream readme")
    commit(fork, "README.md", "TripGuardian fork\n", "fork readme")
    o = sync(fork, up)
    assert o["status"] == "conflict" and o["files"] == "README.md" and o["commits"] == "1"
    assert git(fork, "status", "--porcelain") == ""  # merge aborted, nothing half-done
    assert (fork / "README.md").read_text() == "TripGuardian fork\n"
