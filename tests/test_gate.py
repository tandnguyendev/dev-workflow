"""Approval-gate hook: LOCKED blocks source edits, docs stay editable, and the
gate file itself can never be written by the model."""
from conftest import hook_json, run_hook


def edit(path):
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}


def denied(proc):
    out = hook_json(proc)
    return bool(out) and out["hookSpecificOutput"]["permissionDecision"] == "deny"


def lock(d, state="LOCKED\n"):
    (d / ".approval-gate").write_text(state)


def test_locked_blocks_source_edit(tmp_path):
    lock(tmp_path)
    assert denied(run_hook("gate.py", edit(tmp_path / "src.py"), project_dir=tmp_path))


def test_locked_allows_working_doc(tmp_path):
    lock(tmp_path)
    # phase-log.md must stay editable while locked so the log can be maintained.
    proc = run_hook("gate.py", edit(tmp_path / "phase-log.md"), project_dir=tmp_path)
    assert hook_json(proc) is None and proc.returncode == 0


def test_locked_allows_state_dir(tmp_path):
    lock(tmp_path)
    doc = tmp_path / ".dev-workflow" / "features" / "x" / "spec.md"
    proc = run_hook("gate.py", edit(doc), project_dir=tmp_path)
    assert hook_json(proc) is None


def test_unlocked_allows_source_edit(tmp_path):
    lock(tmp_path, "UNLOCKED\n")
    assert hook_json(run_hook("gate.py", edit(tmp_path / "src.py"), project_dir=tmp_path)) is None


def test_no_gate_file_allows(tmp_path):
    # Gate is opt-in: absent file -> allow.
    assert hook_json(run_hook("gate.py", edit(tmp_path / "src.py"), project_dir=tmp_path)) is None


def test_model_may_not_edit_gate_even_unlocked(tmp_path):
    lock(tmp_path, "UNLOCKED\n")
    proc = run_hook("gate.py", {"tool_name": "Write",
                                "tool_input": {"file_path": str(tmp_path / ".approval-gate")}},
                    project_dir=tmp_path)
    assert denied(proc)


def test_bash_touching_gate_is_denied(tmp_path):
    proc = run_hook("gate.py", {"tool_name": "Bash",
                                "tool_input": {"command": "echo UNLOCKED > .approval-gate"}},
                    project_dir=tmp_path)
    assert denied(proc)


def test_bash_unrelated_allowed_even_when_locked(tmp_path):
    lock(tmp_path)
    proc = run_hook("gate.py", {"tool_name": "Bash", "tool_input": {"command": "ls -la"}},
                    project_dir=tmp_path)
    assert hook_json(proc) is None


def test_malformed_stdin_fails_open(tmp_path):
    lock(tmp_path)
    proc = run_hook("gate.py", "{not json", project_dir=tmp_path)
    assert hook_json(proc) is None and proc.returncode == 0
