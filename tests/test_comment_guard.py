"""Comment guard: added comments that cite the workflow, narrate the diff or talk
to the reviewer are denied; density is capped by the file's own habits; and
everything the guard cannot judge mechanically is left alone."""
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


@pytest.mark.parametrize("comment", LEGITIMATE)
def test_real_comments_are_allowed(tmp_path, comment):
    # A guard that cries wolf gets switched off. Comments that carry a constraint,
    # a caveat or a non-obvious reason must pass untouched — including ones that
    # merely CONTAIN a word the patterns look for ("phase 2 of the handshake").
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
    proc = run(edit(src, new), tmp_path)
    assert denied(proc)
    assert "comment lines" in reason(proc)


def test_the_same_block_is_allowed_on_a_heavily_commented_file(tmp_path):
    # The cap is the FILE's own density, not a fixed ratio — that is the only way
    # to enforce "match the surrounding style" without being wrong for one of the
    # two kinds of file.
    src = tmp_path / "src.py"
    src.write_text("".join(f"# reason {i} the code below is written this way\n"
                           f"def f{i}():\n    return {i}\n" for i in range(12)))
    new = ("def g():\n"
           + "".join(f"    # explanation line {i}\n" for i in range(9))
           + "".join(f"    step{i} = {i}\n" for i in range(18))
           + "    return 1\n")
    assert hook_json(run(edit(src, new), tmp_path)) is None


def test_a_few_comments_always_pass(tmp_path):
    # A floor, so a real caveat on a two-line fix is never blocked by arithmetic.
    src = tmp_path / "src.py"
    src.write_text(TERSE)
    new = "def g():\n    # The vendor SDK mutates this in place.\n    return 1\n"
    assert hook_json(run(edit(src, new), tmp_path)) is None


def test_new_file_header_is_not_charged(tmp_path):
    # Module docstrings and licence headers are conventional; charging a new file
    # for its own header would make every well-documented module a denial.
    (tmp_path / "sibling.py").write_text(
        "".join(f"# reason {i}\ndef f{i}():\n    return {i}\n" for i in range(12)))
    src = tmp_path / "new.py"
    content = ('"""' + "\n".join(f"header line {i}" for i in range(12)) + '"""\n'
               + "".join(f"def f{i}():\n    return {i}\n" for i in range(6)))
    assert hook_json(run(write(src, content), tmp_path)) is None


def test_new_file_matches_its_siblings_density(tmp_path):
    # With no file of its own to compare against, "match the surrounding code"
    # means the directory. Terse neighbours -> a terse budget.
    (tmp_path / "sibling.py").write_text(TERSE)
    src = tmp_path / "new.py"
    content = ("def g():\n"
               + "".join(f"    # explanation line {i}\n" for i in range(9))
               + "    return 1\n")
    assert denied(run(write(src, content), tmp_path))


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
