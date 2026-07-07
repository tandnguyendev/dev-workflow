"""Evidence gate (Stop hook): block once when the current phase is reviewed but
its Evidence ledger is empty; stay silent otherwise."""
from conftest import hook_json, phase, phase_log, run_hook

REAL_EVIDENCE = "pytest -q -> 12 passed; parse() at x.py:20 handles the empty case"


def blocked(proc):
    out = hook_json(proc)
    return out if (out and out.get("decision") == "block") else None


def write_log(tmp_path, *sections):
    (tmp_path / "phase-log.md").write_text(phase_log(*sections))


def test_reviewed_but_empty_evidence_blocks(tmp_path):
    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence="<proof>"))
    out = blocked(run_hook("evidence_guard.py", {}, project_dir=tmp_path))
    assert out and "Phase 1" in out["reason"]


def test_reviewed_with_evidence_passes(tmp_path):
    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence=REAL_EVIDENCE))
    proc = run_hook("evidence_guard.py", {}, project_dir=tmp_path)
    assert hook_json(proc) is None and proc.returncode == 0


def test_unreviewed_phase_is_not_gated(tmp_path):
    # Not reviewed yet -> nothing to prove -> allowed.
    write_log(tmp_path, phase("Phase 1 - a", reviewed=False, evidence="<proof>"))
    assert hook_json(run_hook("evidence_guard.py", {}, project_dir=tmp_path)) is None


def test_stop_hook_active_short_circuits(tmp_path):
    # Loop guard: never block twice in a row, even if evidence is still empty.
    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence="<proof>"))
    proc = run_hook("evidence_guard.py", {"stop_hook_active": True}, project_dir=tmp_path)
    assert hook_json(proc) is None


def test_no_phase_log_is_silent(tmp_path):
    assert hook_json(run_hook("evidence_guard.py", {}, project_dir=tmp_path)) is None


def test_gates_current_phase_not_earlier_ones(tmp_path):
    # Phase 1 approved (skip); Phase 2 is the current unapproved+empty one.
    write_log(
        tmp_path,
        phase("Phase 1 - a", reviewed=True, approved=True, evidence=REAL_EVIDENCE),
        phase("Phase 2 - b", reviewed=True, evidence="<proof>"),
    )
    out = blocked(run_hook("evidence_guard.py", {}, project_dir=tmp_path))
    assert out and "Phase 2" in out["reason"] and "Phase 1" not in out["reason"]


def test_short_nonempty_evidence_still_blocks(tmp_path):
    # A too-short scrap ("ok") is not real cited proof.
    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence="ok"))
    assert blocked(run_hook("evidence_guard.py", {}, project_dir=tmp_path))
