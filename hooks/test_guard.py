#!/usr/bin/env python3
"""PreToolUse test guard for the dev-workflow plugin.

The workflow asks for "one artifact per acceptance criterion" (SKILL.md Stage 4)
and `evidence_guard.py` refuses to end the turn until the ledger cites one. The
cheapest artifact to produce is a new test, so criteria turn into tests one-for-one
whether or not the criterion has any logic worth testing — and the tests that come
out of that quota are shaped to be CITABLE, not to be able to fail.

Two deterministic checks, applied only to test files and only to what an edit
ADDS. Each is a shape no reviewer disagrees about, because every judgement call
here ("is this test worth its lines?") belongs to `code-reviewer`, which reads the
subject as well as the test. A guard that cries wolf gets configured off, and then
it guards nothing.

1. POSITIONAL EMPTY FAKES — `new Service({} as any, {} as any, model, {} as any...)`.
   A provider built by position out of empty placeholders is a test that silently
   lies the day someone reorders or inserts a constructor parameter: the wrong
   object lands in the slot and the suite stays green. The compliant move always
   exists — build it through the framework's testing module, or a named factory
   where each dependency is bound by name.

2. A TEST WITH NO ASSERTION — an `it`/`test` block that asserts nothing. It cannot
   fail except by throwing, so it reports a criterion as covered while covering
   nothing.

WHAT IS DELIBERATELY NOT HERE: "the test mocks the risk it claims to prove" — the
`jest.fn()` counter standing in for an atomic `$inc`, which is the most damaging
shape of all. Two designs were built and measured against 92 real test files.
Block-scoped detection missed every true positive, because the fake is nearly
always built in a `makeX()` factory OUTSIDE the block that relies on it.
File-scoped detection reached roughly half false positives, because the claim lives
in English: "a unique payer+amount candidate" and "resolves the chain exactly once
across two polls" are in-process statements wearing the same words as a store
guarantee, and a fake that THROWS is the only way to reach a driver error like
E11000 at all. Deciding this needs the subject read next to the test, so it is
enforced by `code-reviewer` and stated in `conventions.md` instead of guessed at
here.

Scope: files that look like tests (`*.spec.*`, `*.test.*`, `test_*.py`, `*_test.go`,
or anything under `tests/`/`__tests__/`), outside `.dev-workflow/`. Both checks are
JS/TS-shaped and only run there.

Deny is safe here the way it is for `comment_guard`, and for the same reason: every
check leaves a compliant action available, so this can never trap a turn and needs
no refusal budget.

Escape hatches, for the project that genuinely disagrees:
  DEV_WORKFLOW_TEST_GUARD=off        (env)
  .dev-workflow/test-guard.json      {"enabled": false}
                                     {"checks": {"fakes": false, "assertions": false}}
                                     {"max_empty_args": 3}
                                     {"allow": ["<regex>", ...]}
"""
import json
import os
import re
import sys

STATE_DIR = ".dev-workflow"
CONFIG_NAME = "test-guard.json"

JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
BLOCK_EXTS = JS_EXTS  # where the brace scanner can find a test block

# How many empty positional placeholders in ONE constructor call is too many.
# Calibrated against real suites: binding one or two unused dependencies by
# position is how a focused unit test stays short, and denying that would be the
# false positive that gets the guard turned off. At three the call has stopped
# being readable as an interface and is just a slot count to keep in sync by hand.
MAX_EMPTY_ARGS = 3

# `{} as any`, `null as unknown as Foo`, `undefined as any` — a placeholder whose
# only job is to fill a position.
EMPTY_ARG = re.compile(
    r"(?:\{\s*\}|\[\s*\]|null|undefined)\s+as\s+(?:any\b|unknown\b)")
NEW_CALL = re.compile(r"\bnew\s+([A-Z]\w*)\s*\(")

# Prefix-matched (`expectNetwork(...)`) because extracting a shared assertion into a
# named helper is good practice, and reading those blocks as empty would punish it.
ASSERTION = re.compile(
    r"\b(?:expect|assert|verify|should)\w*(?:\.\w+)*\s*\(|\.rejects\b|"
    r"\.resolves\b|\btoMatchSnapshot\s*\(|\bfail\s*\(")
HELPER_DEF = re.compile(
    r"(?:function\s+(\w+)\s*\(|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?[\(<])")

TEST_BLOCK = re.compile(r"\b(?:it|test)(?:\.(?:only|skip|each|concurrent|failing))?"
                        r"\s*(?:\([^)]*\))?\s*\(\s*(['\"`])(.*?)\1", re.DOTALL)

TEST_NAME = re.compile(r"(\.spec\.|\.test\.|^test_|_test\.(py|go|rb|ts|js)$)")


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return None


def load_config(root):
    """{'enabled', 'checks', 'max_empty_args', 'allow'} — defaults on any problem.
    A malformed config must not disable the guard silently, nor crash the edit."""
    cfg = {"enabled": True,
           "checks": {"fakes": True, "assertions": True},
           "max_empty_args": MAX_EMPTY_ARGS,
           "allow": []}
    if (os.environ.get("DEV_WORKFLOW_TEST_GUARD") or "").strip().lower() in (
            "off", "0", "false", "no"):
        cfg["enabled"] = False
        return cfg
    raw = read(os.path.join(root, STATE_DIR, CONFIG_NAME))
    if not raw:
        return cfg
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return cfg
    except Exception:
        return cfg
    if obj.get("enabled") is False:
        cfg["enabled"] = False
    checks = obj.get("checks")
    if isinstance(checks, dict):
        for k in cfg["checks"]:
            if checks.get(k) is False:
                cfg["checks"][k] = False
    try:
        cfg["max_empty_args"] = max(1, int(obj.get("max_empty_args",
                                                   MAX_EMPTY_ARGS)))
    except Exception:
        pass
    for pat in obj.get("allow") or []:
        try:
            cfg["allow"].append(re.compile(pat, re.IGNORECASE))
        except Exception:
            pass  # one bad regex must not void the rest of the allowlist
    return cfg


# --- source scanning --------------------------------------------------------

def blank_noncode(text):
    """`text` with string, template and comment contents replaced by spaces.

    Every check below counts brackets or matches keywords, and both go wrong on
    punctuation that lives inside a string — a test title containing `)` would end
    a call early and a `//` inside a URL would swallow the rest of the line. Length
    and line structure are preserved so offsets still index into the original."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "'\"`":
            quote = c
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    break
                if text[j] != "\n":
                    out[j] = " "
                j += 1
            i = j + 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if text[k] != "\n":
                    out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out)


def call_span(blanked, open_paren):
    """End offset of the call whose `(` is at `open_paren`, or None if unbalanced.

    Unbalanced means the edit handed us a fragment that cuts the call in half; there
    is nothing to judge, so every caller treats None as "skip"."""
    depth = 0
    for i in range(open_paren, len(blanked)):
        c = blanked[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return i
    return None


def test_blocks(text, blanked):
    """Yield (title, body) for each `it(...)`/`test(...)` in the text.

    The title comes from the ORIGINAL text (it is a string, so `blanked` erased it);
    the body is bounded by scanning `blanked`, where punctuation inside strings and
    comments can no longer throw the bracket count off."""
    for m in TEST_BLOCK.finditer(text):
        open_paren = text.rfind("(", m.start(), m.start(1))
        if open_paren == -1:
            continue
        end = call_span(blanked, open_paren)
        if end is None:
            continue  # truncated fragment — not ours to judge
        yield m.group(2), blanked[open_paren:end + 1]


def added_text(new_text, old_text):
    """The lines of `new_text` that are not already somewhere in `old_text`.

    Same rule as the comment guard: an edit that merely carries existing code
    through its context must not be blamed for it, or there is no compliant move
    left. Returned as a line-preserving string so offsets stay meaningful."""
    if not old_text:
        return new_text
    old = {l.strip() for l in old_text.splitlines() if l.strip()}
    kept = [("" if l.strip() and l.strip() in old else l)
            for l in new_text.splitlines()]
    return "\n".join(kept)


# --- checks -----------------------------------------------------------------

def find_empty_fakes(blanked, limit):
    """-> (class_name, count) for the first constructor call built out of `limit`
    or more empty positional placeholders."""
    for m in NEW_CALL.finditer(blanked):
        open_paren = m.end() - 1
        end = call_span(blanked, open_paren)
        if end is None:
            continue
        count = len(EMPTY_ARG.findall(blanked[open_paren:end + 1]))
        if count >= limit:
            return m.group(1), count
    return None, 0


def assertion_names(blanked):
    """Helpers defined in this file whose own body asserts — calls to them count as
    assertions wherever they appear, whatever the helper is called."""
    names = set()
    for m in HELPER_DEF.finditer(blanked):
        name = m.group(1) or m.group(2)
        if name and ASSERTION.search(blanked[m.end():m.end() + 600]):
            names.add(name)
    return names


def find_assertionless(text, blanked):
    """-> title of the first test block that asserts nothing."""
    helpers = assertion_names(blanked)
    for title, body in test_blocks(text, blanked):
        if ASSERTION.search(body):
            continue
        if any(re.search(r"\b" + re.escape(h) + r"\s*\(", body) for h in helpers):
            continue
        return title
    return None


# --- payload ----------------------------------------------------------------

def chunks(tool, tool_input, path):
    """The (new_text, old_text) pieces an edit writes."""
    if tool == "Write":
        return [(tool_input.get("content") or "", read(path) or "")]
    if tool == "Edit":
        return [(tool_input.get("new_string") or "",
                 tool_input.get("old_string") or "")]
    if tool == "MultiEdit":
        return [(e.get("new_string") or "", e.get("old_string") or "")
                for e in (tool_input.get("edits") or []) if isinstance(e, dict)]
    return []


def is_test_file(path):
    name = os.path.basename(path).lower()
    if TEST_NAME.search(name):
        return True
    parts = {p.lower() for p in os.path.normpath(path).split(os.sep)}
    return bool(parts & {"tests", "__tests__", "spec", "test"})


def in_state_dir(path, root):
    try:
        state = os.path.abspath(os.path.join(root, STATE_DIR))
        return os.path.commonpath([state, os.path.abspath(path)]) == state
    except Exception:
        return False


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # unparseable -> fail open, like every other hook here

    if not isinstance(payload, dict):
        sys.exit(0)

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if not path or not is_test_file(path):
        sys.exit(0)

    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    if in_state_dir(path, root):
        sys.exit(0)

    cfg = load_config(root)
    if not cfg["enabled"]:
        sys.exit(0)

    ext = os.path.splitext(path)[1].lower()
    try:
        pieces = chunks(tool, tool_input, path)
    except Exception:
        sys.exit(0)

    name = os.path.basename(path)
    for new_text, old_text in pieces:
        if not new_text.strip():
            continue
        text = added_text(new_text, old_text)
        if not text.strip():
            continue
        if any(a.search(text) for a in cfg["allow"]):
            continue
        blanked = blank_noncode(text)

        if cfg["checks"]["fakes"] and ext in JS_EXTS:
            cls, count = find_empty_fakes(blanked, cfg["max_empty_args"])
            if cls:
                deny(
                    f"Positional empty fakes in {name}: `new {cls}(...)` is built "
                    f"from {count} empty `as any` placeholders.\n\n"
                    "A provider assembled by position out of blanks stops testing "
                    "the code the moment someone reorders or inserts a constructor "
                    "parameter — the wrong object lands in the slot and the suite "
                    "stays green, which is worse than having no test.\n"
                    "Bind the dependencies by NAME instead: the framework's testing "
                    "module (`Test.createTestingModule({providers:[...]})` in Nest), "
                    "or a small factory in this file that names each one. If the "
                    "subject genuinely needs that many dependencies to exercise one "
                    "behaviour, that is a signal about the subject — say so rather "
                    "than working around this."
                )

        if cfg["checks"]["assertions"] and ext in BLOCK_EXTS:
            title = find_assertionless(text, blanked)
            if title:
                deny(
                    f"Test in {name} asserts nothing:\n"
                    f"    it('{title[:120]}')\n\n"
                    "A block with no assertion passes unless something throws, so "
                    "it reports a behaviour as covered while covering nothing. Add "
                    "the assertion that would fail if the behaviour broke — or "
                    "delete the test, which is the right answer when the behaviour "
                    "has nothing worth asserting about it."
                )


if __name__ == "__main__":
    main()
