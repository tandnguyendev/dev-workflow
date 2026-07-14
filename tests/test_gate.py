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


def bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def test_bash_touching_gate_is_denied(tmp_path):
    assert denied(run_hook("gate.py", bash("echo UNLOCKED > .approval-gate"),
                           project_dir=tmp_path))


def test_bash_touching_gate_is_denied_through_shell_quoting(tmp_path):
    # A raw substring test on the filename is defeated by the shell's own quoting:
    # `.approval-gat"e"` is the same file to the shell but a different string to us.
    # Unlocked, that let the model DELETE its own gate — which disables the gate for
    # every phase that follows.
    lock(tmp_path, "UNLOCKED\n")
    for cmd in ('echo UNLOCKED > .approval-gat"e"',
                "rm .approval-gat'e'",
                'rm .approval\\-gate'):
        assert denied(run_hook("gate.py", bash(cmd), project_dir=tmp_path)), cmd


def test_locked_denies_bash_writing_source(tmp_path):
    # THE escape: gate.py returned early for Bash, so the LOCKED source-edit block
    # was never reached — and `coder` has Bash. A here-doc, `sed -i`, `patch` or
    # `python -c "open(...,'w')"` wrote source while the gate said LOCKED, so the
    # phase advanced without the user's approval.
    lock(tmp_path)
    assert denied(run_hook("gate.py", bash("cat > src.py <<EOF\nhacked=1\nEOF"),
                           project_dir=tmp_path))


def test_locked_denies_all_bash(tmp_path):
    # A denylist of write constructs cannot be closed (gate.py's own docstring says
    # so), so LOCKED denies Bash outright rather than trying to spot the writes.
    # LOCKED means "stop and wait for the user", so there is nothing legitimate to
    # run: the coder does its work — tests and lint included — while UNLOCKED.
    lock(tmp_path)
    for cmd in ("ls -la", "pytest -q", "sed -i s/a/b/ src.py",
                "python -c \"open('src.py','w').write('x')\""):
        assert denied(run_hook("gate.py", bash(cmd), project_dir=tmp_path)), cmd


def test_unlocked_allows_bash(tmp_path):
    # ...and unlocked, the coder gets its full toolkit back.
    lock(tmp_path, "UNLOCKED\n")
    assert hook_json(run_hook("gate.py", bash("pytest -q"), project_dir=tmp_path)) is None


def test_no_gate_file_allows_bash(tmp_path):
    # The gate is opt-in; with no gate file the hook must not touch anything.
    assert hook_json(run_hook("gate.py", bash("pytest -q"), project_dir=tmp_path)) is None


def test_malformed_stdin_fails_open(tmp_path):
    lock(tmp_path)
    proc = run_hook("gate.py", "{not json", project_dir=tmp_path)
    assert hook_json(proc) is None and proc.returncode == 0
