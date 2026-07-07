"""Checkpoint engine: snapshots to a shadow ref without touching the user's
index/HEAD/branch, rollback is reversible, and the approval gate is never
captured or clobbered."""
from conftest import hook_json, run_hook


def cp(repo, *args):
    """Run checkpoint.py as a CLI subcommand."""
    return run_hook("checkpoint.py", None, project_dir=repo, args=list(args))


def head(repo):
    import subprocess
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, text=True,
                          stdout=subprocess.PIPE).stdout.strip()


def test_snapshot_creates_ref(git_repo):
    (git_repo / "a.txt").write_text("two\n")
    out = cp(git_repo, "snapshot").stdout
    assert "refs/dev-workflow/checkpoints" in out          # snapshot prints the full ref
    assert "dev-workflow/checkpoints" in cp(git_repo, "list").stdout  # list prints the short ref


def test_snapshot_does_not_move_head_or_branch(git_repo):
    before = head(git_repo)
    (git_repo / "a.txt").write_text("two\n")
    cp(git_repo, "snapshot")
    assert head(git_repo) == before  # branch/HEAD untouched


def test_identical_snapshot_is_deduped(git_repo):
    (git_repo / "a.txt").write_text("two\n")
    assert "refs/dev-workflow" in cp(git_repo, "snapshot").stdout
    # No change since the last snapshot -> skipped.
    assert "no change" in cp(git_repo, "snapshot").stdout.lower()


def test_rollback_restores_and_undo_reverses(git_repo):
    (git_repo / "a.txt").write_text("two\n")
    cp(git_repo, "snapshot")                 # checkpoint captures "two"
    (git_repo / "a.txt").write_text("three\n")
    cp(git_repo, "rollback")                 # -> working tree back to "two"
    assert (git_repo / "a.txt").read_text() == "two\n"
    cp(git_repo, "undo")                     # -> reverse, back to "three"
    assert (git_repo / "a.txt").read_text() == "three\n"


def test_rollback_preserves_live_gate(git_repo):
    (git_repo / ".approval-gate").write_text("LOCKED\n")
    (git_repo / "a.txt").write_text("two\n")
    cp(git_repo, "snapshot")
    (git_repo / ".approval-gate").write_text("UNLOCKED\n")  # user unlocks after the snapshot
    cp(git_repo, "rollback")
    # The gate reflects the LIVE state, never the snapshot's — rollback can't relock.
    assert (git_repo / ".approval-gate").read_text().strip() == "UNLOCKED"


def test_non_git_dir_is_noop(tmp_path):
    out = cp(tmp_path, "snapshot").stdout
    assert "no change" in out.lower()
    assert "no checkpoints" in cp(tmp_path, "list").stdout.lower()


def test_unborn_branch_snapshots(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("one\n")
    out = cp(tmp_path, "snapshot").stdout  # no commits yet -> parentless snapshot
    assert "refs/dev-workflow/checkpoints" in out


def test_hook_mode_snapshots_on_mutating_tool(git_repo):
    (git_repo / "a.txt").write_text("two\n")
    proc = run_hook("checkpoint.py", {"tool_name": "Edit", "cwd": str(git_repo)},
                    project_dir=git_repo)
    assert proc.returncode == 0
    assert "dev-workflow/checkpoints" in cp(git_repo, "list").stdout


def test_hook_mode_ignores_non_mutating_tool(git_repo):
    run_hook("checkpoint.py", {"tool_name": "Read", "cwd": str(git_repo)}, project_dir=git_repo)
    assert "no checkpoints" in cp(git_repo, "list").stdout.lower()
