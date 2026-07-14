"""The shared parsing module — the single source of truth for phase-log
structure that status.py and evidence_guard.py both depend on."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "hooks"))
import _workflow  # noqa: E402


def test_iter_phases_splits_and_reads_approval():
    log = (
        "# Phase log: t\n\n"
        "## Phase 1 - a\n- Status: [x] USER APPROVED\nbody one\n\n"
        "## Phase 2 - b\n- Status: [ ] USER APPROVED\nbody two\n\n"
        "## Final review (all phases)\n- Status: [ ] USER APPROVED\n"
    )
    got = list(_workflow.iter_phases(log))
    assert [t for t, _, _ in got] == ["Phase 1 - a", "Phase 2 - b", "Final review (all phases)"]
    assert [ok for _, _, ok in got] == [True, False, False]
    assert "body one" in got[0][1]  # body is scoped to its own section


def test_iter_phases_empty_when_no_headings():
    assert list(_workflow.iter_phases("# Phase log: t\n\njust prose\n")) == []


def test_heading_match_survives_ordinary_capitalisation():
    # The heading regex was case-sensitive, so `## Final Review` (capital R) was not
    # a section at all: its body — including a `[x] USER APPROVED` — was absorbed
    # into the phase ABOVE it, marking the WRONG phase approved. Since the evidence
    # gate only inspects the first unapproved phase, that also switched the gate off
    # for the whole feature. Nothing in the docs said the capital R mattered.
    log = (
        "# Phase log: t\n\n"
        "## Phase 1 - a\n- Status: [ ] USER APPROVED\n- Evidence:\n\n"
        "## Final Review (all phases)\n- Status: [x] USER APPROVED\n"
    )
    got = list(_workflow.iter_phases(log))
    assert [t for t, _, _ in got] == ["Phase 1 - a", "Final Review (all phases)"]
    assert [ok for _, _, ok in got] == [False, True], "approval leaked into Phase 1"


def test_approval_stays_case_sensitive_so_prose_cannot_approve():
    # APPROVED must fail CLOSED: an incidental lowercase "user approved" in a note
    # must NOT mark the phase approved, or an unproven phase gets waved through and
    # the evidence gate skips it. Only the literal `[x] USER APPROVED` counts.
    prose = ("# Phase log: t\n\n## Phase 1 - a\n- Status: [ ] USER APPROVED\n"
             "- User notes: we discussed and [x] user approved verbally last week\n")
    assert [ok for _, _, ok in _workflow.iter_phases(prose)] == [False]
    real = "# Phase log: t\n\n## Phase 1 - a\n- Status: [x] USER APPROVED\n"
    assert [ok for _, _, ok in _workflow.iter_phases(real)] == [True]


def test_heading_does_not_match_deeper_hashes_or_fenced_phase():
    # Kept to the template's `##` depth: a `#### Phase` line (e.g. inside a fenced
    # code block in the notes) is NOT a phantom phase that perturbs "first
    # unapproved = current".
    log = ("# Phase log: t\n\n## Phase 1 - a\n- Status: [ ] USER APPROVED\n"
           "```\n#### Phase X - not real\n```\n")
    assert [t for t, _, _ in _workflow.iter_phases(log)] == ["Phase 1 - a"]


def test_final_reviewer_prose_is_not_a_section():
    # `\b` after "review" keeps `## Final reviewer notes` from matching as the
    # Final review section.
    log = ("# Phase log: t\n\n## Phase 1 - a\n- Status: [x] USER APPROVED\n\n"
           "## Final reviewer notes\n- Status: [ ] USER APPROVED\n")
    assert [t for t, _, _ in _workflow.iter_phases(log)] == ["Phase 1 - a"]


def test_docs_dir_resolves_active_feature(tmp_path):
    (tmp_path / ".dev-workflow" / "features" / "wallet").mkdir(parents=True)
    (tmp_path / ".dev-workflow" / "active").write_text("wallet\n")
    d, slug = _workflow.docs_dir(str(tmp_path))
    assert slug == "wallet" and os.path.basename(d) == "wallet"


def test_docs_dir_falls_back_to_root(tmp_path):
    d, slug = _workflow.docs_dir(str(tmp_path))
    assert slug is None and d == str(tmp_path)


def test_read_missing_file_returns_none():
    assert _workflow.read("/no/such/file/here") is None
