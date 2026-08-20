"""Test guard: a provider assembled from empty positional placeholders and a test
that asserts nothing are denied; everything the guard cannot judge mechanically —
including whether a mock stands in for the real risk — is left alone."""
import sys

import pytest
from conftest import HOOKS, hook_json, run_hook

sys.path.insert(0, HOOKS)
import test_guard  # noqa: E402


def write(path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": content}}


def edit(path, new, old=""):
    return {"tool_name": "Edit",
            "tool_input": {"file_path": str(path), "old_string": old, "new_string": new}}


def denied(proc):
    out = hook_json(proc)
    return bool(out) and out["hookSpecificOutput"]["permissionDecision"] == "deny"


def reason(proc):
    return hook_json(proc)["hookSpecificOutput"]["permissionDecisionReason"]


def run(payload, project_dir, **kw):
    return run_hook("test_guard.py", payload, project_dir=project_dir, **kw)


FAKES = """
const svc = new OrderService({} as any, {} as any, counterModel, {} as any);
it('draws a ref', async () => { expect(await svc.next()).toBe('1'); });
"""

NAMED = """
const svc = new OrderService({ counterModel, clock, config });
it('draws a ref', async () => { expect(await svc.next()).toBe('1'); });
"""


# --- positional empty fakes -------------------------------------------------

def test_denies_a_provider_built_from_empty_positional_placeholders(tmp_path):
    spec = tmp_path / "order.service.spec.ts"
    proc = run(write(spec, FAKES), tmp_path)
    assert denied(proc)
    assert "OrderService" in reason(proc)
    assert "by NAME" in reason(proc)


def test_allows_dependencies_bound_by_name(tmp_path):
    assert not denied(run(write(tmp_path / "order.service.spec.ts", NAMED), tmp_path))


def test_allows_one_or_two_placeholders(tmp_path):
    """Binding a couple of unused dependencies by position is how a focused unit
    test stays short — the check is aimed at the call that has become a slot count."""
    src = """
    const svc = new StateService({} as any, cursorModel, {} as any);
    it('guards the cursor', () => { expect(svc.ok()).toBe(true); });
    """
    assert not denied(run(write(tmp_path / "state.spec.ts", src), tmp_path))


@pytest.mark.parametrize("placeholder", [
    "{} as any", "{ } as any", "[] as any", "null as any", "undefined as any",
    "null as unknown",
])
def test_every_placeholder_spelling_counts(tmp_path, placeholder):
    src = f"const s = new Svc({placeholder}, {placeholder}, {placeholder});"
    assert denied(run(write(tmp_path / "svc.spec.ts", src), tmp_path))


def test_a_real_argument_is_not_a_placeholder(tmp_path):
    src = ("const s = new Svc(model as any, clock as any, config as any, {} as any);\n"
           "it('works', () => { expect(s.ok()).toBe(true); });")
    assert not denied(run(write(tmp_path / "svc.spec.ts", src), tmp_path))


def test_placeholders_are_counted_per_call_not_per_file(tmp_path):
    """Three separate one-placeholder constructions are three readable calls; the
    denial is about ONE call whose interface has vanished."""
    src = "\n".join(
        f"const s{i} = new Svc{i}({{}} as any);\n"
        f"it('case {i}', () => {{ expect(s{i}.ok()).toBe(true); }});"
        for i in range(3))
    assert not denied(run(write(tmp_path / "svc.spec.ts", src), tmp_path))


# --- assertionless tests ----------------------------------------------------

def test_denies_a_test_block_with_no_assertion(tmp_path):
    src = "it('creates an order', async () => { await svc.create({ id: 1 }); });"
    proc = run(write(tmp_path / "order.spec.ts", src), tmp_path)
    assert denied(proc)
    assert "asserts nothing" in reason(proc)


@pytest.mark.parametrize("body", [
    "expect(x).toBe(1);",
    "await expect(p).rejects.toThrow();",
    "await expect(p).resolves.toBe(1);",
    "assert.equal(x, 1);",
    "expect(x).toMatchSnapshot();",
])
def test_recognizes_the_usual_assertion_shapes(tmp_path, body):
    src = f"it('does the thing', async () => {{ {body} }});"
    assert not denied(run(write(tmp_path / "a.spec.ts", src), tmp_path))


def test_a_named_assertion_helper_counts_as_asserting(tmp_path):
    """Extracting a shared assertion into `expectNetwork(...)` is good practice; a
    guard that read those blocks as empty would punish exactly the right habit."""
    src = ("const expectNetwork = (svc, net) => { expect(svc.net).toBe(net); };\n"
           "it('resolves mainnet', async () => { expectNetwork(svc, 'mainnet'); });")
    assert not denied(run(write(tmp_path / "chain.spec.ts", src), tmp_path))


def test_a_local_helper_that_asserts_counts_whatever_it_is_named(tmp_path):
    src = ("function theRowLooksRight(row) { expect(row.id).toBe(1); }\n"
           "it('writes the row', async () => { theRowLooksRight(await svc.write()); });")
    assert not denied(run(write(tmp_path / "row.spec.ts", src), tmp_path))


def test_a_helper_that_does_not_assert_does_not_rescue_the_block(tmp_path):
    src = ("function build() { return { id: 1 }; }\n"
           "it('writes the row', async () => { await svc.write(build()); });")
    assert denied(run(write(tmp_path / "row.spec.ts", src), tmp_path))


# --- what the guard must NOT judge ------------------------------------------

def test_a_mocked_store_is_not_the_guards_business(tmp_path):
    """Left to `code-reviewer`: measured against 93 real test files, no mechanical
    version of this check reached usable precision."""
    src = ("const counter: any = { findOneAndUpdate: jest.fn(async () => ({ seq: 1 })) };\n"
           "it('never yields the same ref across 200 concurrent draws', async () => {\n"
           "  expect(new Set(await draws()).size).toBe(200);\n"
           "});")
    assert not denied(run(write(tmp_path / "order.spec.ts", src), tmp_path))


def test_a_fake_that_injects_a_driver_error_is_never_flagged(tmp_path):
    src = ("const model: any = { findOneAndUpdate: jest.fn(async () => { throw dup; }) };\n"
           "it('resolves a lost insert race to the winning row', async () => {\n"
           "  expect(await svc.createIfNotExists()).toEqual(winner);\n"
           "});")
    assert not denied(run(write(tmp_path / "tx.spec.ts", src), tmp_path))


# --- scope ------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "order.service.spec.ts", "order.test.ts", "order.spec.tsx", "order.spec.js",
])
def test_test_files_are_in_scope(tmp_path, name):
    assert denied(run(write(tmp_path / name, FAKES), tmp_path))


def test_production_code_is_out_of_scope(tmp_path):
    """A test lying is the subject here, not a codebase's type hygiene."""
    assert not denied(run(write(tmp_path / "order.service.ts", FAKES), tmp_path))


def test_a_file_under_tests_is_in_scope(tmp_path):
    d = tmp_path / "tests"
    d.mkdir()
    assert denied(run(write(d / "order.ts", FAKES), tmp_path))


def test_the_workflow_state_dir_is_never_checked(tmp_path):
    d = tmp_path / ".dev-workflow" / "features" / "f"
    d.mkdir(parents=True)
    assert not denied(run(write(d / "notes.spec.ts", FAKES), tmp_path))


def test_python_tests_are_out_of_scope_for_the_js_checks(tmp_path):
    assert not denied(run(write(tmp_path / "test_order.py", FAKES), tmp_path))


# --- only what the edit adds ------------------------------------------------

def test_an_edit_is_not_blamed_for_placeholders_it_carries_through(tmp_path):
    """The coder keeps changes minimal, so denying a line it did not write would
    leave no compliant move."""
    spec = tmp_path / "order.spec.ts"
    spec.write_text(FAKES)
    carried = edit(spec, FAKES + "\nit('more', () => { expect(1).toBe(1); });", FAKES)
    assert not denied(run(carried, tmp_path))


def test_a_truncated_fragment_is_skipped_rather_than_guessed_at(tmp_path):
    frag = "const svc = new OrderService({} as any, {} as any, {} as any,"
    assert not denied(run(edit(tmp_path / "a.spec.ts", frag), tmp_path))


# --- strings and comments ---------------------------------------------------

def test_punctuation_inside_a_title_does_not_break_the_scan(tmp_path):
    src = ("it('rejects a ) unbalanced paren in the title', async () => {\n"
           "  expect(await svc.ok()).toBe(true);\n"
           "});")
    assert not denied(run(write(tmp_path / "a.spec.ts", src), tmp_path))


def test_an_assertion_inside_a_comment_does_not_count(tmp_path):
    src = ("it('creates an order', async () => {\n"
           "  // expect(order.id).toBe(1) — TODO\n"
           "  await svc.create();\n"
           "});")
    assert denied(run(write(tmp_path / "a.spec.ts", src), tmp_path))


def test_a_placeholder_inside_a_string_is_not_a_placeholder(tmp_path):
    src = ("const msg = 'new Svc({} as any, {} as any, {} as any)';\n"
           "it('logs', () => { expect(msg).toContain('Svc'); });")
    assert not denied(run(write(tmp_path / "a.spec.ts", src), tmp_path))


# --- configuration and failure modes ----------------------------------------

def test_the_env_switch_turns_it_off(tmp_path):
    proc = run(write(tmp_path / "a.spec.ts", FAKES), tmp_path,
               env={"DEV_WORKFLOW_TEST_GUARD": "off"})
    assert not denied(proc)


def test_the_project_can_disable_it(tmp_path):
    d = tmp_path / ".dev-workflow"
    d.mkdir()
    (d / "test-guard.json").write_text('{"enabled": false}')
    assert not denied(run(write(tmp_path / "a.spec.ts", FAKES), tmp_path))


def test_a_project_can_disable_one_check_and_keep_the_other(tmp_path):
    d = tmp_path / ".dev-workflow"
    d.mkdir()
    (d / "test-guard.json").write_text('{"checks": {"fakes": false}}')
    assert not denied(run(write(tmp_path / "a.spec.ts", FAKES), tmp_path))
    bare = "it('creates an order', async () => { await svc.create(); });"
    assert denied(run(write(tmp_path / "b.spec.ts", bare), tmp_path))


def test_a_project_can_raise_the_placeholder_budget(tmp_path):
    d = tmp_path / ".dev-workflow"
    d.mkdir()
    (d / "test-guard.json").write_text('{"max_empty_args": 8}')
    assert not denied(run(write(tmp_path / "a.spec.ts", FAKES), tmp_path))


def test_an_allow_pattern_exempts_a_file(tmp_path):
    d = tmp_path / ".dev-workflow"
    d.mkdir()
    (d / "test-guard.json").write_text('{"allow": ["legacy fixture"]}')
    src = "// legacy fixture\n" + FAKES
    assert not denied(run(write(tmp_path / "a.spec.ts", src), tmp_path))


@pytest.mark.parametrize("bad", ["not json", "[]", '{"allow": ["(("]}'])
def test_a_malformed_config_falls_back_to_defaults(tmp_path, bad):
    """A config nobody can parse must not disable the guard silently, and must not
    crash the edit either."""
    d = tmp_path / ".dev-workflow"
    d.mkdir()
    (d / "test-guard.json").write_text(bad)
    proc = run(write(tmp_path / "a.spec.ts", FAKES), tmp_path)
    assert proc.returncode == 0
    assert denied(proc)


@pytest.mark.parametrize("payload", [None, "", "{not json", "[]", {}])
def test_it_fails_open_on_any_payload(tmp_path, payload):
    proc = run(payload, tmp_path)
    assert proc.returncode == 0
    assert not denied(proc)


def test_an_empty_write_is_ignored(tmp_path):
    assert not denied(run(write(tmp_path / "a.spec.ts", "   \n"), tmp_path))
