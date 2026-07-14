"""Evidence gate (Stop hook): keep blocking while the current phase is reviewed but
its Evidence ledger is empty; stay silent otherwise."""
import json
import os
import sys

import pytest

from conftest import HOOKS, hook_json, phase, phase_log, run_hook

sys.path.insert(0, HOOKS)
import evidence_guard  # noqa: E402
from evidence_guard import MAX_BLOCKS  # noqa: E402  (the budget under test)

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


def test_blocks_again_when_the_model_changed_nothing(tmp_path):
    # THE realistic sequence, and the one that made this gate advisory: the model
    # stops, is blocked, changes nothing, and stops again. Claude Code sets
    # stop_hook_active on that second stop — trusting it let the phase through with
    # an empty ledger, which is precisely what the gate exists to prevent.
    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence="<proof>"))
    assert blocked(run_hook("evidence_guard.py", {}, project_dir=tmp_path))
    again = run_hook("evidence_guard.py", {"stop_hook_active": True}, project_dir=tmp_path)
    assert blocked(again), "gate gave up after ONE block; the ledger is still empty"


def test_gives_up_loudly_rather_than_hard_locking_the_turn(tmp_path):
    # It must never be able to trap a turn forever. After MAX_BLOCKS refusals it
    # yields — but says so out loud, so an empty ledger never passes SILENTLY.
    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence="<proof>"))
    payload = {"stop_hook_active": True}
    for _ in range(MAX_BLOCKS):
        assert blocked(run_hook("evidence_guard.py", payload, project_dir=tmp_path))
    out = hook_json(run_hook("evidence_guard.py", payload, project_dir=tmp_path))
    assert out is None or out.get("decision") != "block", "hard-locked the turn"
    assert out and "gave up" in json.dumps(out).lower(), "gave up SILENTLY"

    # And it STAYS given up. Forgetting the count here would re-arm the gate, so it
    # would oscillate block/block/block/pass forever rather than yield.
    again = hook_json(run_hook("evidence_guard.py", payload, project_dir=tmp_path))
    assert again is None or again.get("decision") != "block", "re-armed after giving up"
    assert again and "gave up" in json.dumps(again).lower(), "stopped warning"


def test_unwritable_counter_cannot_trap_the_turn(tmp_path):
    # If `.dev-workflow/` is read-only (or full), the count cannot be persisted and
    # every load returns 0, so it never reaches the give-up bound. The whole point
    # of the bound is that the gate cannot block forever — so a broken counter must
    # fall back to yielding, not to blocking on every stop.
    if os.getuid() == 0:
        pytest.skip("root bypasses the directory write permission this test needs")
    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence="<proof>"))
    (tmp_path / ".dev-workflow").mkdir()
    os.chmod(tmp_path / ".dev-workflow", 0o555)
    try:
        # First stop blocks (nothing persisted yet is fine — it hasn't blocked yet).
        assert blocked(run_hook("evidence_guard.py", {}, project_dir=tmp_path))
        # On the re-stop it CANNOT keep blocking: it has already blocked once and it
        # cannot track that it did, so it yields instead of trapping the turn.
        out = hook_json(run_hook("evidence_guard.py",
                                 {"stop_hook_active": True}, project_dir=tmp_path))
        assert out is None or out.get("decision") != "block", "trapped the turn"
    finally:
        os.chmod(tmp_path / ".dev-workflow", 0o755)


def test_save_counter_reports_write_failure(tmp_path):
    # The give-up fallback depends on save_counter telling the truth about failure.
    if os.getuid() == 0:
        pytest.skip("root bypasses the directory write permission this test needs")
    (tmp_path / ".dev-workflow").mkdir()
    os.chmod(tmp_path / ".dev-workflow", 0o555)
    try:
        assert evidence_guard.save_counter(str(tmp_path), "k", 1) is False
    finally:
        os.chmod(tmp_path / ".dev-workflow", 0o755)


def test_counter_is_per_phase_so_features_do_not_clobber(tmp_path):
    # Two concurrent features must not reset each other's budget — a single-slot file
    # let one feature's stop wipe the other's count, so alternating stuck features
    # could each keep restarting at 1 and neither would ever give up.
    root = str(tmp_path)
    evidence_guard.save_counter(root, "fa::Phase 1", 2)
    evidence_guard.save_counter(root, "fb::Phase 1", 1)
    assert evidence_guard.load_counter(root, "fa::Phase 1") == 2  # survived fb's write
    assert evidence_guard.load_counter(root, "fb::Phase 1") == 1
    evidence_guard.clear_counter(root, "fb::Phase 1")            # fb advances
    assert evidence_guard.load_counter(root, "fa::Phase 1") == 2  # fa untouched


def test_corrupt_counter_resets_rather_than_fails_shut(tmp_path):
    (tmp_path / ".dev-workflow").mkdir()
    (tmp_path / ".dev-workflow" / "evidence-gate.json").write_text("{not json")
    assert evidence_guard.load_counter(str(tmp_path), "k") == 0


def test_filling_the_ledger_resets_the_counter(tmp_path):
    # Burn a block, then supply real evidence: the phase passes, and a later phase
    # that goes empty again gets the full budget rather than an exhausted one.
    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence="<proof>"))
    assert blocked(run_hook("evidence_guard.py", {}, project_dir=tmp_path))

    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence=REAL_EVIDENCE))
    assert hook_json(run_hook("evidence_guard.py", {}, project_dir=tmp_path)) is None

    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence="<proof>"))
    assert blocked(run_hook("evidence_guard.py", {}, project_dir=tmp_path))


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


def test_evidence_written_as_sub_bullets_counts(tmp_path):
    # The most natural way to cite several artifacts is a list under the field. The
    # terminator lookahead matched the evidence's OWN sub-bullets, so the ledger read
    # as EMPTY and real, cited proof was refused — while the identical text on one
    # line passed. The docstring promised both forms count.
    (tmp_path / "phase-log.md").write_text(
        "# Phase log: t\n\n"
        "## Phase 1 - a\n"
        "- Status: [x] coded  [x] code-reviewed  [ ] USER APPROVED\n"
        "- Evidence:\n"
        "  - tests: 42 passed\n"
        "  - parse() at x.py:20 handles the empty case\n"
        "- User notes:\n"
    )
    proc = run_hook("evidence_guard.py", {}, project_dir=tmp_path)
    assert hook_json(proc) is None, "false block: real evidence read as empty"


def test_next_field_still_terminates_the_ledger(tmp_path):
    # ...but an empty ledger followed by the next top-level field is still empty.
    (tmp_path / "phase-log.md").write_text(
        "# Phase log: t\n\n"
        "## Phase 1 - a\n"
        "- Status: [x] coded  [x] code-reviewed  [ ] USER APPROVED\n"
        "- Evidence:\n"
        "- User notes: the user said it looked good\n"
    )
    assert blocked(run_hook("evidence_guard.py", {}, project_dir=tmp_path))


def test_short_nonempty_evidence_still_blocks(tmp_path):
    # A too-short scrap ("ok") is not real cited proof.
    write_log(tmp_path, phase("Phase 1 - a", reviewed=True, evidence="ok"))
    assert blocked(run_hook("evidence_guard.py", {}, project_dir=tmp_path))
