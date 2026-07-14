"""Verify + scope checks of the Stop pre-approval gate.

Both share the evidence gate's trigger (current phase reviewed, not yet approved),
so every test here gives the phase real evidence — isolating the check under test
from the evidence check.
"""
import subprocess

from conftest import hook_json, phase, phase_log, run_hook

REAL_EVIDENCE = "pytest -q -> 12 passed; parse() at x.py:20 handles the empty case"


def blocked(proc):
    out = hook_json(proc)
    return out if (out and out.get("decision") == "block") else None


def setup(tmp_path, *, conventions=None, plan=None, evidence=REAL_EVIDENCE):
    (tmp_path / "phase-log.md").write_text(
        phase_log(phase("Phase 1 - a", reviewed=True, evidence=evidence)))
    if conventions is not None:
        (tmp_path / "conventions.md").write_text(conventions)
    if plan is not None:
        (tmp_path / "plan.md").write_text(plan)
    return run_hook("evidence_guard.py", {}, project_dir=tmp_path)


def conventions_with(lint=None, test=None):
    body = "".join(f"{k}: {v}\n" for k, v in (("lint", lint), ("test", test)) if v)
    return f"# Project conventions\n\n## Verify commands\n```verify\n{body}```\n"


def plan_with(files, phase_no=1):
    return (f"# Plan: t\n\n## Phases\n\n### Phase {phase_no} - a\n"
            f"- Scope: x\n- Files: {files}\n- Done when: y\n")


# --- verify: the declared commands must actually pass -----------------------

def test_failing_command_blocks(tmp_path):
    out = blocked(setup(tmp_path, conventions=conventions_with(test="exit 1")))
    assert out and "VERIFY" in out["reason"] and "exit 1" in out["reason"]


def test_passing_command_allows(tmp_path):
    assert setup(tmp_path, conventions=conventions_with(test="exit 0")).stdout.strip() == ""


def test_command_output_tail_is_shown(tmp_path):
    out = blocked(setup(tmp_path, conventions=conventions_with(
        test="echo 'assert failed: balance went negative'; exit 2")))
    assert out and "balance went negative" in out["reason"]


def test_both_commands_reported(tmp_path):
    out = blocked(setup(tmp_path, conventions=conventions_with(lint="exit 3", test="exit 4")))
    assert out and "exit 3" in out["reason"] and "exit 4" in out["reason"]


def test_no_verify_block_is_opt_out(tmp_path):
    # A project that declares no commands is never gated on them.
    assert setup(tmp_path, conventions="# Project conventions\n\nNo commands here.\n").stdout.strip() == ""


def test_no_conventions_file_is_silent(tmp_path):
    assert setup(tmp_path).stdout.strip() == ""


def test_unfilled_placeholder_command_is_never_run(tmp_path):
    # Straight from templates/conventions.md — must not be executed as a shell command.
    assert setup(tmp_path, conventions=conventions_with(
        test="<exact command, e.g. pytest -q>")).stdout.strip() == ""


# --- scope: changed files must stay inside the phase's declared Files -------

def test_undeclared_file_blocks(git_repo):
    (git_repo / "sneaky.py").write_text("x = 1\n")
    out = blocked(setup(git_repo, plan=plan_with("`a.txt`")))
    assert out and "SCOPE" in out["reason"] and "sneaky.py" in out["reason"]


def test_declared_file_allows(git_repo):
    (git_repo / "a.txt").write_text("two\n")
    assert setup(git_repo, plan=plan_with("`a.txt`")).stdout.strip() == ""


def test_declared_directory_covers_its_files(git_repo):
    (git_repo / "src").mkdir()
    (git_repo / "src" / "deep.py").write_text("x = 1\n")
    assert setup(git_repo, plan=plan_with("`src/`")).stdout.strip() == ""


def test_workflow_docs_are_never_a_violation(git_repo):
    # The coder is expected to update these; they are not phase scope.
    (git_repo / "phase-log.md").write_text(
        phase_log(phase("Phase 1 - a", reviewed=True, evidence=REAL_EVIDENCE)))
    (git_repo / "conventions.md").write_text("# c\n")
    assert setup(git_repo, plan=plan_with("`a.txt`")).stdout.strip() == ""


def test_unfilled_files_placeholder_does_not_block(git_repo):
    # `- Files: <exact paths...>` straight from the template = unknown, not empty.
    (git_repo / "sneaky.py").write_text("x = 1\n")
    assert setup(git_repo, plan=plan_with("<exact paths>")).stdout.strip() == ""


def test_no_plan_file_does_not_block(git_repo):
    (git_repo / "sneaky.py").write_text("x = 1\n")
    assert setup(git_repo).stdout.strip() == ""


def test_scope_matches_the_current_phase(git_repo):
    # Phase 2 is current; its Files must be the ones enforced, not Phase 1's.
    (git_repo / "phase-log.md").write_text(phase_log(
        phase("Phase 1 - a", reviewed=True, approved=True, evidence=REAL_EVIDENCE),
        phase("Phase 2 - b", reviewed=True, evidence=REAL_EVIDENCE)))
    (git_repo / "plan.md").write_text(
        plan_with("`a.txt`", phase_no=1) + "\n### Phase 2 - b\n- Files: `b.txt`\n")
    (git_repo / "a.txt").write_text("changed by phase 1\n")
    out = blocked(run_hook("evidence_guard.py", {}, project_dir=git_repo))
    assert out and "a.txt" in out["reason"]


def test_artifacts_from_the_verify_run_are_not_scope_violations(git_repo):
    # The gate runs the test command itself; whatever that command drops (pycache,
    # coverage files) must not come back as an edit the coder never made.
    (git_repo / "a.txt").write_text("two\n")
    out = setup(git_repo, plan=plan_with("`a.txt`"),
                conventions=conventions_with(test="touch build-artifact.tmp"))
    assert out.stdout.strip() == ""
    assert (git_repo / "build-artifact.tmp").exists()  # the command really ran


# --- the checks compose -----------------------------------------------------

def test_all_three_failures_reported_in_one_block(git_repo):
    (git_repo / "sneaky.py").write_text("x = 1\n")
    out = blocked(setup(git_repo, evidence="<proof>", plan=plan_with("`a.txt`"),
                        conventions=conventions_with(test="exit 1")))
    assert out
    for expected in ("EVIDENCE", "VERIFY", "SCOPE"):
        assert expected in out["reason"]


def test_stop_hook_active_short_circuits_every_check(tmp_path):
    (tmp_path / "phase-log.md").write_text(
        phase_log(phase("Phase 1 - a", reviewed=True, evidence=REAL_EVIDENCE)))
    (tmp_path / "conventions.md").write_text(conventions_with(test="exit 1"))
    proc = run_hook("evidence_guard.py", {"stop_hook_active": True}, project_dir=tmp_path)
    assert hook_json(proc) is None


def test_unreviewed_phase_runs_no_commands(tmp_path):
    # Too early to gate -> the declared commands must not run at all.
    marker = tmp_path / "ran"
    (tmp_path / "phase-log.md").write_text(
        phase_log(phase("Phase 1 - a", reviewed=False, evidence="<proof>")))
    (tmp_path / "conventions.md").write_text(
        conventions_with(test=f"touch {marker}; exit 1"))
    proc = run_hook("evidence_guard.py", {}, project_dir=tmp_path)
    assert hook_json(proc) is None and not marker.exists()


def test_uninstalled_command_surfaces_rather_than_passing_silently(tmp_path):
    out = blocked(setup(tmp_path, conventions=conventions_with(test="definitely-not-a-real-cmd")))
    assert out and "VERIFY" in out["reason"]
