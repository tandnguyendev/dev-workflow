"""Comment guard: added comments that cite the workflow, narrate the diff or talk
to the reviewer are denied; density is capped by the file's own habits (zero for a
comment-free or new file); no comment block runs past two lines; and tool
directives are never counted."""
import json
import sys

import pytest
from conftest import HOOKS, hook_json, run_hook

sys.path.insert(0, HOOKS)
import comment_guard  # noqa: E402


def edit(path, new, old=""):
    return {"tool_name": "Edit",
            "tool_input": {"file_path": str(path), "old_string": old, "new_string": new}}


def write(path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": content}}


def denied(proc):
    out = hook_json(proc)
    return bool(out) and out["hookSpecificOutput"]["permissionDecision"] == "deny"


def reason(proc):
    return hook_json(proc)["hookSpecificOutput"]["permissionDecisionReason"]


def run(payload, project_dir, **kw):
    return run_hook("comment_guard.py", payload, project_dir=project_dir, **kw)


# --- noise patterns ---------------------------------------------------------

WORKFLOW_NOISE = [
    "# AC-2: reject an expired token",
    "# AC 3 covered here",
    "# Acceptance criteria: the parser must not raise",
    "# See plan.md for the rollback story",
    "# Phase 2: wire the retry budget",
    "# This phase only handles the happy path",
    "# Per the spec, empty input is a no-op",
    "# Requirement 4: audit every write",
    "# Done when the suite is green",
]
DIFF_NARRATION = [
    "# This change moves the lock inside the loop",
    "# We now retry three times",
    "# I removed the old fallback",
    "# Added a helper so the caller stays flat",
    "# New: the caller owns the session",
    "# Previously this swallowed the error",
    "# Instead of the old regex, split on tabs",
]
REVIEWER_TALK = [
    "# This ensures the lock is always released",
    "# This is correct because the caller holds the lock",
    "# Note for the reviewer: the cast is safe",
    "# As requested, the retry is capped",
    "# Per your review, the guard moved up",
    "# Addresses the review finding about ordering",
    "# To satisfy AC the token is re-checked",
]


@pytest.mark.parametrize("comment", WORKFLOW_NOISE + DIFF_NARRATION + REVIEWER_TALK)
def test_noise_comments_are_denied(tmp_path, comment):
    src = tmp_path / "src.py"
    src.write_text("def f():\n    return 1\n")
    proc = run(edit(src, f"def f():\n    {comment}\n    return 2\n"), tmp_path)
    assert denied(proc), comment
    # The refusal has to quote the offending line, or the coder cannot tell WHICH
    # of the comments in a multi-line edit it is being asked to drop.
    assert comment.lstrip("# ") in reason(proc)


LEGITIMATE = [
    "# The API returns 200 for an expired token, so status is not enough.",
    "# Ordering matters: close() flushes, and flush() can raise.",
    "# Kept sorted so the binary search below stays valid.",
    "# phase 2 of the TLS handshake sends the client cert",
    "# Fails loudly: a silent default here hid a prod outage.",
    "# The vendor SDK mutates this dict in place.",
]


def floor(tmp_path, n):
    (tmp_path / ".dev-workflow").mkdir(exist_ok=True)
    (tmp_path / ".dev-workflow" / "comment-guard.json").write_text(
        json.dumps({"density": {"floor": n}}))


@pytest.mark.parametrize("comment", LEGITIMATE)
def test_real_comments_are_not_mistaken_for_noise(tmp_path, comment):
    # With the density floor raised out of the way, a comment that carries a
    # constraint must pass the NOISE patterns — including one that merely CONTAINS
    # a word they look for ("phase 2 of the handshake").
    floor(tmp_path, 1)
    src = tmp_path / "src.py"
    src.write_text("def f():\n    return 1\n")
    assert hook_json(run(edit(src, f"def f():\n    {comment}\n    return 2\n"), tmp_path)) is None, comment


def test_preexisting_noise_carried_through_an_edit_is_not_blamed(tmp_path):
    # The coder is told to keep changes minimal, so an edit whose context window
    # happens to include somebody else's "AC-1" comment has NO compliant move:
    # dropping the comment is an unrelated change, keeping it would be denied.
    src = tmp_path / "src.py"
    old = "    # AC-1: the legacy contract\n    return 1\n"
    new = "    # AC-1: the legacy contract\n    return 2\n"
    src.write_text("def f():\n" + old)
    assert hook_json(run(edit(src, new, old), tmp_path)) is None


def test_noise_in_a_docstring_is_denied(tmp_path):
    # Python's docstrings are its comment surface; a guard blind to them would miss
    # the most natural place to write "implements AC-3".
    src = tmp_path / "src.py"
    src.write_text("def f():\n    return 1\n")
    proc = run(edit(src, 'def f():\n    """Implements AC-3."""\n    return 2\n'), tmp_path)
    assert denied(proc)


def test_noise_in_a_c_block_comment_is_denied(tmp_path):
    src = tmp_path / "src.ts"
    src.write_text("export function f() { return 1 }\n")
    proc = run(edit(src, "/* We now cache the token */\nexport function f() { return 2 }\n"),
               tmp_path)
    assert denied(proc)


def test_refusal_names_phase_log_only_inside_an_active_feature(tmp_path):
    # The guard runs on every edit, so most of the time it is read by an agent with
    # no orchestrator and no phase-log. Naming them anyway sends it to a file that
    # does not exist.
    src = tmp_path / "src.py"
    src.write_text("def f():\n    return 1\n")
    payload = edit(src, "def f():\n    # AC-3: return two\n    return 2\n")

    outside = reason(run(payload, tmp_path))
    assert "phase-log.md" not in outside and "orchestrator" not in outside
    assert "commit message" in outside

    feature = tmp_path / ".dev-workflow" / "features" / "checkout"
    feature.mkdir(parents=True)
    (tmp_path / ".dev-workflow" / "active").write_text("checkout\n")
    assert "phase-log.md" in reason(run(payload, tmp_path))


def test_a_dangling_active_slug_does_not_name_phase_log(tmp_path):
    # `.dev-workflow/active` outliving its feature dir is the state a deleted or
    # renamed feature leaves behind; the file it points at is gone either way.
    src = tmp_path / "src.py"
    src.write_text("def f():\n    return 1\n")
    (tmp_path / ".dev-workflow").mkdir()
    (tmp_path / ".dev-workflow" / "active").write_text("deleted-feature\n")
    out = reason(run(edit(src, "def f():\n    # AC-3: return two\n    return 2\n"), tmp_path))
    assert "phase-log.md" not in out


# --- scope ------------------------------------------------------------------

def test_markdown_and_data_files_are_out_of_scope(tmp_path):
    # Working docs are SUPPOSED to talk about acceptance criteria and phases —
    # that is what phase-log.md is for.
    for name in ("notes.md", "data.json", "conf.yaml", "notes.txt"):
        f = tmp_path / name
        f.write_text("x\n")
        assert hook_json(run(edit(f, "# AC-1: whatever\n"), tmp_path)) is None, name


def test_state_dir_is_out_of_scope(tmp_path):
    f = tmp_path / ".dev-workflow" / "features" / "x" / "helper.py"
    f.parent.mkdir(parents=True)
    assert hook_json(run(edit(f, "# AC-1: whatever\n"), tmp_path)) is None


def test_markdown_notebook_cell_is_out_of_scope(tmp_path):
    payload = {"tool_name": "NotebookEdit",
               "tool_input": {"notebook_path": str(tmp_path / "a.ipynb"),
                              "cell_type": "markdown", "new_source": "# AC-1: prose"}}
    assert hook_json(run(payload, tmp_path)) is None


def test_notebook_code_cell_is_checked(tmp_path):
    payload = {"tool_name": "NotebookEdit",
               "tool_input": {"notebook_path": str(tmp_path / "a.ipynb"),
                              "cell_type": "code", "new_source": "# AC-1: load the frame\ndf = load()"}}
    assert denied(run(payload, tmp_path))


# --- density ----------------------------------------------------------------

TERSE = "".join(f"def f{i}():\n    return {i}\n\n" for i in range(12))  # 0 comments


def test_dense_comment_block_on_a_terse_file_is_denied(tmp_path):
    src = tmp_path / "src.py"
    src.write_text(TERSE)
    new = ("def g():\n"
           + "".join(f"    # explanation line {i}\n" for i in range(9))
           + "    return 1\n")
    assert denied(run(edit(src, new), tmp_path))


COMMENTED = "".join(f"# reason {i} the code below is written this way\n"
                    f"def f{i}():\n    return {i}\n" for i in range(12))


def test_a_heavily_commented_file_keeps_granting_its_own_density(tmp_path):
    # The cap is the FILE's own density, not a fixed ratio — a codebase that
    # genuinely documents keeps its habit, one short comment at a time.
    src = tmp_path / "src.py"
    src.write_text(COMMENTED)
    new = ("def g():\n"
           + "".join(f"    # reason {i}\n    step{i} = {i}\n    more{i} = {i}\n" for i in range(4))
           + "    return 1\n")
    assert hook_json(run(edit(src, new), tmp_path)) is None


def test_a_long_block_is_denied_even_on_a_heavily_commented_file(tmp_path):
    # Density used to let an essay through wherever essays already were — which is
    # how they compounded. A paragraph is a design argument, not a caveat.
    src = tmp_path / "src.py"
    src.write_text(COMMENTED)
    new = ("def g():\n"
           + "".join(f"    # explanation line {i}\n" for i in range(3))
           + "".join(f"    step{i} = {i}\n" for i in range(18))
           + "    return 1\n")
    proc = run(edit(src, new), tmp_path)
    assert denied(proc)
    assert "block too long" in reason(proc)


def test_block_markers_do_not_count_toward_the_block_limit(tmp_path):
    src = tmp_path / "src.ts"
    src.write_text("".join(f"// reason {i}\nexport const x{i} = {i}\n" for i in range(12)))
    new = "/**\n * Seconds, not millis: the vendor API says so.\n */\nexport const ttl = 60\n"
    assert hook_json(run(edit(src, new), tmp_path)) is None


def test_separate_blocks_are_not_joined(tmp_path):
    lines = "// one\n// two\nconst a = 1\n/**\n * three\n */\nconst b = 2\n".splitlines()
    flags = comment_guard.scan(lines, comment_guard.SYNTAX[".ts"])
    comments = [(i, comment_guard.comment_text(l, comment_guard.SYNTAX[".ts"]))
                for i, (l, f) in enumerate(zip(lines, flags)) if f]
    assert comment_guard.longest_block(comments) == ["one", "two"]


def test_max_block_is_configurable(tmp_path):
    (tmp_path / ".dev-workflow").mkdir()
    (tmp_path / ".dev-workflow" / "comment-guard.json").write_text(
        json.dumps({"max_block": 0, "density": {"floor": 10}}))
    src = tmp_path / "src.py"
    src.write_text(TERSE)
    new = "def g():\n" + "".join(f"    # line {i}\n" for i in range(5)) + "    return 1\n"
    assert hook_json(run(edit(src, new), tmp_path)) is None


def test_a_single_comment_on_a_terse_file_is_denied_by_default(tmp_path):
    # The default is NO comment: a comment-free file grants nothing.
    src = tmp_path / "src.py"
    src.write_text(TERSE)
    new = "def g():\n    # The vendor SDK mutates this in place.\n    return 1\n"
    assert denied(run(edit(src, new), tmp_path))


def test_the_floor_can_be_raised_per_project(tmp_path):
    floor(tmp_path, 1)
    src = tmp_path / "src.py"
    src.write_text(TERSE)
    new = "def g():\n    # The vendor SDK mutates this in place.\n    return 1\n"
    assert hook_json(run(edit(src, new), tmp_path)) is None


@pytest.mark.parametrize("pragma", [
    "// eslint-disable-next-line no-console",
    "// @ts-expect-error vendor types are wrong",
    "/* istanbul ignore next */",
    "// prettier-ignore",
    "//go:build linux",
])
def test_tool_directives_are_not_comments(tmp_path, pragma):
    src = tmp_path / "src.ts"
    src.write_text("export const a = 1\n")
    assert hook_json(run(edit(src, f"{pragma}\nexport const a = 2\n"), tmp_path)) is None


@pytest.mark.parametrize("pragma", [
    "#!/usr/bin/env python3", "# -*- coding: utf-8 -*-", "x = f()  # noqa: E501",
    "# type: ignore", "# pylint: disable=unused-import",
])
def test_python_directives_are_not_comments(tmp_path, pragma):
    src = tmp_path / "src.py"
    src.write_text("x = 1\n")
    line = pragma if pragma.startswith("x") else pragma + "\nx = 2"
    assert hook_json(run(edit(src, line + "\n"), tmp_path)) is None


def test_a_second_comment_line_on_a_terse_file_is_denied(tmp_path):
    src = tmp_path / "src.py"
    src.write_text(TERSE)
    new = ("def g():\n"
           "    # The vendor SDK mutates this in place.\n"
           "    # So the caller's copy is already updated.\n"
           "    return 1\n")
    assert denied(run(edit(src, new), tmp_path))


def test_a_terse_file_grants_nothing_beyond_the_floor_however_big_the_edit(tmp_path):
    # No min_ratio: a large edit to a comment-free file does not earn a paragraph.
    src = tmp_path / "src.py"
    src.write_text(TERSE)
    new = ("def g():\n"
           + "".join(f"    # explanation line {i}\n" for i in range(3))
           + "".join(f"    step{i} = {i}\n" for i in range(40))
           + "    return 1\n")
    assert denied(run(edit(src, new), tmp_path))


def test_new_file_header_is_charged(tmp_path):
    # A header docstring on a new file is where the design essay moves once the
    # body is policed; it gets no free pass.
    src = tmp_path / "new.py"
    content = ('"""Loads the ledger."""\n'
               + "".join(f"def f{i}():\n    return {i}\n" for i in range(6)))
    assert denied(run(write(src, content), tmp_path))


def test_new_file_does_not_inherit_its_siblings_density(tmp_path):
    # Borrowing the directory's density is how agent-written comments compounded:
    # every commented file raised the budget of the next one.
    (tmp_path / "sibling.py").write_text(COMMENTED)
    src = tmp_path / "new.py"
    content = "def g():\n    # a reason\n    return 1\n"
    assert denied(run(write(src, content), tmp_path))


def test_new_file_with_only_a_licence_header_passes(tmp_path):
    src = tmp_path / "new.ts"
    content = "// SPDX-License-Identifier: MIT\nexport const a = 1\n"
    assert hook_json(run(write(src, content), tmp_path)) is None


# --- escape hatches and failure modes ---------------------------------------

def test_env_var_disables_the_guard(tmp_path):
    src = tmp_path / "src.py"
    src.write_text("def f():\n    return 1\n")
    proc = run(edit(src, "# AC-1: whatever\n"), tmp_path,
               env={"DEV_WORKFLOW_COMMENT_GUARD": "off"})
    assert hook_json(proc) is None


def test_config_can_disable_the_guard(tmp_path):
    (tmp_path / ".dev-workflow").mkdir()
    (tmp_path / ".dev-workflow" / "comment-guard.json").write_text('{"enabled": false}')
    src = tmp_path / "src.py"
    src.write_text("def f():\n    return 1\n")
    assert hook_json(run(edit(src, "# AC-1: whatever\n"), tmp_path)) is None


def test_config_allowlist_exempts_a_pattern(tmp_path):
    # A project whose domain genuinely says "phase 2" in code needs a way out that
    # is narrower than switching the whole guard off.
    (tmp_path / ".dev-workflow").mkdir()
    (tmp_path / ".dev-workflow" / "comment-guard.json").write_text(
        json.dumps({"allow": [r"phase \d of the handshake"]}))
    src = tmp_path / "src.py"
    src.write_text("def f():\n    return 1\n")
    proc = run(edit(src, "# Phase 2 of the handshake needs the cert\ndef f():\n    return 2\n"),
               tmp_path)
    # Exempt from the density budget too, or the allowlist is no escape at floor 0.
    assert hook_json(proc) is None


def test_malformed_config_does_not_disable_the_guard(tmp_path):
    # Failing OPEN on a typo'd config would silently switch the rule back off, which
    # is the exact drift this hook exists to stop.
    (tmp_path / ".dev-workflow").mkdir()
    (tmp_path / ".dev-workflow" / "comment-guard.json").write_text("{not json")
    src = tmp_path / "src.py"
    src.write_text("def f():\n    return 1\n")
    assert denied(run(edit(src, "# AC-1: whatever\ndef f():\n    return 2\n"), tmp_path))


def test_malformed_stdin_fails_open(tmp_path):
    proc = run("{not json", tmp_path)
    assert hook_json(proc) is None and proc.returncode == 0


def test_unterminated_triple_quote_does_not_swallow_the_file(tmp_path):
    # The closing line of a multi-line SQL string also starts with `"""`. Treated as
    # an opener, it would mark every following line a comment — turning a normal
    # edit into a density denial and, worse, scanning code for noise patterns.
    lines = comment_guard.SYNTAX[".py"]
    text = 'sql = """\nSELECT 1\n"""\nx = 1\ny = 2\nz = 3\n'
    flags = comment_guard.scan(text.splitlines(), lines)
    assert flags[3:] == [False, False, False]


def test_scan_marks_a_real_docstring(tmp_path):
    text = 'def f():\n    """Doc.\n\n    More.\n    """\n    return 1\n'
    flags = comment_guard.scan(text.splitlines(), comment_guard.SYNTAX[".py"])
    assert flags == [False, True, True, True, True, False]
