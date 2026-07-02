#!/usr/bin/env python3
"""Checkpoint engine for the dev-workflow plugin (Phase 1: snapshot + list).

As a PreToolUse hook (no args, JSON on stdin): before a mutating tool
(Edit/Write/MultiEdit/Bash) runs, snapshot the working tree to an immutable
commit on a shadow ref `refs/dev-workflow/checkpoints/<ts>` WITHOUT touching the
user's index, HEAD, branch, or working tree. Always exits 0 and never denies —
it is a side-effecting recorder, not a gate. Fails open on any error.

As a CLI: `checkpoint.py snapshot|list` (rollback/undo arrive in Phase 2).

Mechanism (never mutates the user's real index):
  GIT_INDEX_FILE=<tmp> git read-tree HEAD      # seed tmp index from HEAD
  GIT_INDEX_FILE=<tmp> git add -A              # stage working tree into tmp index
  tree=$(GIT_INDEX_FILE=<tmp> git write-tree)
  commit=$(git commit-tree $tree -p HEAD -m <json>)
  git update-ref refs/dev-workflow/checkpoints/<ts> $commit

Safety: operates only inside CLAUDE_PROJECT_DIR (never an arbitrary cwd); git is
run with a timeout, non-interactive, and fsmonitor disabled. v1 scope: git repos
only (silent no-op otherwise); no retention yet.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

REF_PREFIX = "refs/dev-workflow/checkpoints"
MUTATING_TOOLS = {"Edit", "Write", "MultiEdit", "Bash"}
_GIT = shutil.which("git") or "git"
# Defense-in-depth: never let repo config run commands or prompt/block us.
_HARDEN = ["-c", "core.fsmonitor="]
_TIMEOUT = 15


def git(project_dir, args, env_extra=None, check=True):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    if env_extra:
        env.update(env_extra)
    try:
        p = subprocess.run(
            [_GIT] + _HARDEN + args,
            cwd=project_dir, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"git unavailable or timed out: {e}")
    if check and p.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {p.stderr.decode('utf-8','replace').strip()}")
    return p.returncode, p.stdout.decode("utf-8", "replace").strip()


def is_git_repo(project_dir):
    try:
        rc, out = git(project_dir, ["rev-parse", "--is-inside-work-tree"], check=False)
    except RuntimeError:
        return False
    return rc == 0 and out == "true"


def head_sha(project_dir):
    rc, out = git(project_dir, ["rev-parse", "HEAD"], check=False)
    return out if rc == 0 else None  # None on an unborn branch


def last_snapshot(project_dir):
    """(ref, tree) of the newest existing snapshot, or (None, None)."""
    rc, out = git(project_dir, [
        "for-each-ref", "--sort=-refname", "--count=1",
        "--format=%(refname) %(objectname)", REF_PREFIX,
    ], check=False)
    if rc != 0 or not out:
        return None, None
    ref, commit = out.split()
    _, tree = git(project_dir, ["rev-parse", commit + "^{tree}"])
    return ref, tree


def snapshot(project_dir, tool_name=""):
    """Create a snapshot ref if the tree changed. Returns the ref or None."""
    if not is_git_repo(project_dir):
        return None

    head = head_sha(project_dir)
    # A fresh temp DIRECTORY (mode 0700) with a never-preexisting index path,
    # so git creates a valid index and there is no shared-temp TOCTOU/symlink.
    tmpdir = tempfile.mkdtemp(prefix="dwf-idx-")
    tmp_index = os.path.join(tmpdir, "index")
    try:
        env = {"GIT_INDEX_FILE": tmp_index}
        if head:
            git(project_dir, ["read-tree", "HEAD"], env_extra=env)
        git(project_dir, ["add", "-A"], env_extra=env)
        _, tree = git(project_dir, ["write-tree"], env_extra=env)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Dedup: skip if the working tree is identical to the newest snapshot.
    _, prev_tree = last_snapshot(project_dir)
    if prev_tree == tree:
        return None

    meta = json.dumps({"timestamp": _now(), "tool": tool_name, "head_before": head},
                      separators=(",", ":"))
    commit_args = ["commit-tree", tree, "-m", meta]
    if head:
        commit_args += ["-p", head]
    _, commit = git(project_dir, commit_args)

    ref = f"{REF_PREFIX}/{_ref_stamp()}"
    git(project_dir, ["update-ref", ref, commit])
    return ref


def list_snapshots(project_dir):
    if not is_git_repo(project_dir):
        return []
    rc, out = git(project_dir, [
        "for-each-ref", "--sort=-refname",
        "--format=%(refname:short)\t%(subject)", REF_PREFIX,
    ], check=False)
    if rc != 0 or not out:
        return []
    rows = []
    for line in out.splitlines():
        ref, _, subject = line.partition("\t")
        try:
            meta = json.loads(subject)
        except ValueError:
            meta = {}
        rows.append({"ref": ref, "timestamp": meta.get("timestamp"), "tool": meta.get("tool")})
    return rows


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ref_stamp():
    # Sortable timestamp + random suffix so concurrent snapshots never collide
    # (a collision would silently overwrite an earlier snapshot).
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + os.urandom(4).hex()


def resolve_project_dir(payload=None):
    """Only ever operate inside the trusted CLAUDE_PROJECT_DIR. Honor the hook
    payload's cwd only when it resolves inside that root (else ignore it), so a
    session that cd'd into an untrusted repo cannot redirect our git ops there."""
    base = os.environ.get("CLAUDE_PROJECT_DIR")
    cwd = (payload or {}).get("cwd")
    if base:
        base_r = os.path.realpath(base)
        if cwd:
            try:
                cwd_r = os.path.realpath(cwd)
                if os.path.commonpath([base_r, cwd_r]) == base_r:
                    return cwd_r
            except Exception:
                pass
        return base_r
    return os.path.realpath(cwd) if cwd else os.getcwd()


def hook_main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # fail open
    if payload.get("tool_name", "") not in MUTATING_TOOLS:
        return
    try:
        snapshot(resolve_project_dir(payload), payload.get("tool_name", ""))
    except Exception:
        pass  # never block the tool call


def cli_main(argv):
    cmd = argv[0]
    project_dir = resolve_project_dir()
    try:
        if cmd == "snapshot":
            ref = snapshot(project_dir, "cli")
            print(ref or "(no change; snapshot skipped)")
        elif cmd == "list":
            rows = list_snapshots(project_dir)
            if not rows:
                print("(no checkpoints)")
            for r in rows:
                print(f"{r['ref']}\t{r.get('timestamp','?')}\t{r.get('tool','?')}")
        else:
            print(f"unknown or not-yet-implemented command: {cmd}", file=sys.stderr)
            sys.exit(2)
    except Exception as e:
        print(f"checkpoint: {e}", file=sys.stderr)  # fail gracefully


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        cli_main(args)
    else:
        hook_main()
    sys.exit(0)
