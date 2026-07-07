"""Shared helpers for the dev-workflow hook tests.

The hooks are standalone scripts driven by a JSON stdin payload, emitting a
decision on stdout and communicating allow/deny via the presence of that output
(never a nonzero exit — they always exit 0 and fail open). So the most faithful
test is to run each hook exactly as Claude Code does: as a subprocess with a JSON
payload piped to stdin and CLAUDE_PROJECT_DIR set.
"""
import json
import os
import subprocess
import sys

import pytest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")


def run_hook(script, payload, project_dir=None, env=None, args=None):
    """Run hooks/<script> with `payload` on stdin. `payload` may be a dict/list
    (JSON-encoded), a raw str (sent verbatim — for malformed-input tests), or None
    (empty stdin). Returns the CompletedProcess."""
    if isinstance(payload, str):
        stdin = payload
    elif payload is None:
        stdin = ""
    else:
        stdin = json.dumps(payload)

    e = os.environ.copy()
    e.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir is not None:
        e["CLAUDE_PROJECT_DIR"] = str(project_dir)
    if env:
        e.update(env)

    return subprocess.run(
        [sys.executable, os.path.join(HOOKS, script)] + (args or []),
        input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=e,
    )


def hook_json(proc):
    """Parse the hook's stdout as JSON, or None when it emitted nothing (= allow)."""
    out = proc.stdout.strip()
    return json.loads(out) if out else None


def phase(title, *, coded=True, reviewed=False, approved=False, evidence="<proof>"):
    """One phase-log section matching templates/phase-log.md."""
    box = lambda on: "[x]" if on else "[ ]"
    return (
        f"## {title}\n"
        f"- Status: {box(coded)} coded  {box(reviewed)} code-reviewed  "
        f"[ ] security-scanned  {box(approved)} USER APPROVED\n"
        f"- Changed: foo.py\n"
        f"- Evidence: {evidence}\n"
        f"- User notes:\n\n"
    )


def phase_log(*sections, feature="Test feature"):
    return f"# Phase log: {feature}\n\n" + "".join(sections)


@pytest.fixture
def git_repo(tmp_path):
    """A tmp git repo with one commit (a.txt='one'), identity set locally so
    commit-tree works on CI runners with no global git identity."""
    def g(*a):
        subprocess.run(["git"] + list(a), cwd=tmp_path, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    g("init", "-q")
    g("config", "user.email", "test@example.com")
    g("config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("one\n")
    g("add", "-A")
    g("commit", "-q", "-m", "init")
    return tmp_path
