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
