#!/usr/bin/env python3
"""PreToolUse comment guard for the dev-workflow plugin.

The comment rule ("comment only what the code cannot say itself; never narrate the
change or justify it to the reviewer; match the file's existing comment density")
shipped in four places as PROSE — `references/clean-code.md`, `agents/coder.md`,
`agents/code-reviewer.md`, `templates/conventions.md` — and prose is the one
enforcement layer a model can talk itself past. Every other load-bearing rule in
this plugin has a hook behind it (gate.py, evidence_guard.py, plan_guard.py); this
one did not, so it drifted: comments that cite acceptance criteria, quote the plan,
or argue the change's correctness at the reviewer kept landing in shipped code.

Two deterministic checks, both applied ONLY to comment lines the edit ADDS:

1. NOISE PATTERNS — a comment that references a workflow artifact (AC-2, `plan.md`,
   "Phase 3:"), narrates the diff ("we now...", "Added a helper..."), or addresses
   the reviewer ("as requested", "this ensures...") is denied outright. The pattern
   list is deliberately narrow: it catches the mechanical, unambiguous shapes and
   leaves every judgement call ("does this comment earn its line?") to
   `code-reviewer`. A guard that cries wolf gets configured off, and then guards
   nothing.

2. DENSITY — the number of comment lines added is capped by the file's OWN existing
   comment density. This is the only check that can enforce "match the file's
   existing comment density" at all, and it is self-calibrating: a heavily-commented
   file (this one, say) grants a generous budget, a terse file grants almost none.
   No fixed ratio could do that without being wrong for one of the two.

Scope: files whose extension has a known comment syntax (so .md/.json/.yaml and
every data format are untouched), outside `.dev-workflow/`. Pre-existing comment
lines the edit merely carries through are never counted or flagged — the coder is
told to keep changes minimal, so denying it for a comment it did not write would
leave no compliant move.

Deny is safe here in a way a Stop hook's refusal is not: there is ALWAYS a
compliant action available (delete the comment, or rewrite it as a technical
reason), so this cannot trap a turn and needs no refusal budget.

Escape hatches, for the project that genuinely disagrees:
  DEV_WORKFLOW_COMMENT_GUARD=off        (env)
  .dev-workflow/comment-guard.json      {"enabled": false}
                                        {"allow": ["<regex>", ...]}
                                        {"density": {"floor": 3, "min_ratio": 0.25}}
"""
import json
import math
import os
import re
import sys

STATE_DIR = ".dev-workflow"
CONFIG_NAME = "comment-guard.json"

# --- comment syntax ---------------------------------------------------------
# Extension -> (line-comment prefixes, block-comment (open, close) pairs).
# An extension absent from this table is not checked AT ALL, which is how every
# data/doc format stays out of the guard's way without an explicit denylist.
_C_LINE, _C_BLOCK = ("//",), (("/*", "*/"),)
_HASH = ("#",)
_LANGS = {
    _HASH: (".py", ".pyi", ".rb", ".sh", ".bash", ".zsh", ".fish", ".pl", ".pm",
            ".r", ".jl", ".tf", ".tfvars", ".nim", ".cr", ".ex", ".exs", ".gd",
            ".rake", ".gemspec", ".mk"),
    _C_LINE: (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java", ".c", ".h",
              ".cpp", ".cxx", ".cc", ".hpp", ".hh", ".cs", ".go", ".rs", ".swift",
              ".kt", ".kts", ".scala", ".php", ".dart", ".proto", ".sol", ".m",
              ".mm", ".zig", ".groovy", ".gradle", ".css", ".scss", ".less"),
    ("--",): (".sql", ".hs", ".lua", ".elm", ".adb", ".ads"),
    (";",): (".lisp", ".clj", ".cljs", ".cljc", ".el", ".scm", ".rkt", ".asm"),
}
SYNTAX = {}
for _prefixes, _exts in _LANGS.items():
    for _e in _exts:
        SYNTAX[_e] = (_prefixes, _C_BLOCK if _prefixes is _C_LINE else ())
# Python's docstrings ARE its comment surface — a file whose functions all grew a
# fresh docstring is precisely the noise this guard exists to stop, so the triple
# quotes have to count. See scan()'s unterminated-block rule for why this does not
# swallow ordinary multi-line strings.
SYNTAX[".py"] = (_HASH, (('"""', '"""'), ("'''", "'''")))
SYNTAX[".pyi"] = SYNTAX[".py"]
# Markup and the mixed single-file component formats carry both syntaxes.
for _e in (".html", ".htm", ".xml", ".vue", ".svelte", ".svg", ".astro"):
    SYNTAX[_e] = (_C_LINE, (("<!--", "-->"), ("/*", "*/")))

# --- noise patterns ---------------------------------------------------------
# Matched case-insensitively against the comment's TEXT (markers stripped). `^`
# therefore anchors to the start of the comment, not the start of the line — a
# deliberate precision lever: "Phase 2: wire the parser" is workflow narration,
# while "...during phase 2 of the TLS handshake" is domain language, and only the
# anchor tells them apart.
NOISE = [
    # (a) workflow artifacts leaking into source. Acceptance criteria, plan and
    # spec references are meaningful for exactly as long as the feature branch
    # lives; in the merged file they point at a document the reader cannot open.
    (r"\bAC[-_ ]?\d", "cites an acceptance criterion"),
    (r"\bacceptance criteri", "cites acceptance criteria"),
    (r"\b(spec|plan|phase-log)\.md\b", "points at a workflow document"),
    # A LABEL ("Phase 2: wire the retry budget"), not the word. "phase 2 of the TLS
    # handshake" is domain language, and anchoring alone does not separate them —
    # the trailing punctuation of a label does.
    (r"^phase\s+\d+\s*[:.\-–—]", "labels the change with its plan phase"),
    (r"\b(in|for) this phase\b|\bthis phase (only|adds|implements|delivers|covers)\b",
     "refers to the workflow's phase"),
    (r"\bper the (spec|plan|requirements?)\b", "defers to the spec/plan"),
    (r"\bas (specified|required|described) (in|by) the (spec|plan|ac|ticket)\b",
     "defers to the spec/plan"),
    (r"\brequirements?\s*#?\d+\b", "cites a numbered requirement"),
    (r"\bdone when\b", "quotes the phase's acceptance line"),

    # (b) narrating the diff. True the day it is written, misleading forever after:
    # once merged there is no "previously", and "we now" describes a state that is
    # simply the state.
    (r"^(this|the) (change|commit|pr|patch|fix|refactor|edit|diff|update)\b",
     "narrates the change instead of the code"),
    (r"^(we|i) (now|no longer|added|removed|changed|replaced|updated|introduced"
     r"|moved|renamed)\b", "narrates the change instead of the code"),
    (r"^(added|removed|changed|updated|renamed|moved|replaced|introduced|extracted)"
     r"\s+(a|an|the|this|new|helper|method|function|class|field|param|check|guard)\b",
     "narrates the change instead of the code"),
    (r"^(new|old):\s", "narrates the change instead of the code"),
    (r"\bpreviously (this|we|the code|it)\b", "describes the code's history"),
    (r"\binstead of the (old|previous|original)\b", "describes the code's history"),

    # (c) talk aimed at the reviewer. It is a message, not documentation, and it is
    # delivered the moment the review happens — everything after that is dead text.
    (r"^this (ensures|guarantees|makes sure|is correct|is safe)\b",
     "argues the code is correct rather than saying why it is written this way"),
    (r"\bfor (the )?reviewers?\b", "addresses the reviewer"),
    (r"\bnotes? (to|for) (the )?reviewer\b", "addresses the reviewer"),
    (r"\bas (requested|discussed|agreed)\b", "addresses the reviewer"),
    (r"\bper (your|the) (review|feedback|request)\b", "addresses the reviewer"),
    (r"\baddress(es|ing)? (the )?(review )?(finding|comment|feedback)\b",
     "addresses a review finding"),
    (r"\bto satisfy (the )?(ac\b|acceptance|requirement|spec\b|criteri)",
     "justifies the code against the spec"),
    (r"\breview (finding|round)\s*#?\d", "addresses a review finding"),
]
NOISE = [(re.compile(p, re.IGNORECASE), why) for p, why in NOISE]

# --- density defaults -------------------------------------------------------
# FLOOR: comment lines any edit may add regardless of ratio. Set to the length of
# one honest WHY paragraph, because on a small edit the ratio term is tiny and the
# floor is the whole budget — at 3, a four-line explanation of something genuinely
# subtle was denied on a five-line change, which is the kind of false positive that
# gets a guard configured off. Bulk noise is what density is for; single misplaced
# comments are the pattern check's job.
FLOOR = 4
# MIN_RATIO: the allowance a comment-FREE file still grants. Without it, density
# would be a total ban on the first comment in a bare file.
MIN_RATIO = 0.25
# Below this many real lines a file's own density is noise, not a style signal
# (a 4-line file with 1 comment does not "have" a 25% convention).
MIN_BASELINE = 20
MAX_SIBLINGS = 5  # sampled to give a NEW file a density to match


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
    """{'enabled', 'allow' (compiled), 'floor', 'min_ratio'} — defaults on any
    problem. A malformed config must not disable the guard silently, but it must
    not crash the edit either, so unreadable/invalid falls back to defaults."""
    cfg = {"enabled": True, "allow": [], "floor": FLOOR, "min_ratio": MIN_RATIO}
    if (os.environ.get("DEV_WORKFLOW_COMMENT_GUARD") or "").strip().lower() in (
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
    for pat in obj.get("allow") or []:
        try:
            cfg["allow"].append(re.compile(pat, re.IGNORECASE))
        except Exception:
            pass  # one bad regex must not void the rest of the allowlist
    dens = obj.get("density")
    if isinstance(dens, dict):
        try:
            cfg["floor"] = max(0, int(dens.get("floor", FLOOR)))
            cfg["min_ratio"] = min(1.0, max(0.0, float(dens.get("min_ratio", MIN_RATIO))))
        except Exception:
            pass
    return cfg


# --- scanning ---------------------------------------------------------------

def scan(lines, syntax):
    """Per-line comment flags for a chunk of source.

    Block handling has one rule worth stating: a block that OPENS but never closes
    inside the chunk is not treated as a comment at all. That is what keeps the
    Python config safe — the closing line of

        sql = \"\"\"
        SELECT ...
        \"\"\"

    starts with a triple quote and would otherwise open a block that swallows the
    rest of the file, turning every following line of code into a "comment"."""
    prefixes, blocks = syntax
    flags = [False] * len(lines)
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        opener = next(((o, c) for o, c in blocks if s.startswith(o)), None)
        if opener:
            o, c = opener
            if c in s[len(o):]:  # opens and closes on one line
                flags[i] = True
                i += 1
                continue
            end = next((j for j in range(i + 1, len(lines)) if c in lines[j]), None)
            if end is None:
                i += 1  # unterminated -> ordinary code (see docstring)
                continue
            for k in range(i, end + 1):
                flags[k] = True
            i = end + 1
            continue
        if any(s.startswith(p) for p in prefixes):
            flags[i] = True
        i += 1
    return flags


def comment_text(line, syntax):
    """A comment line with its markers stripped, for pattern matching."""
    prefixes, blocks = syntax
    s = line.strip()
    for o, c in blocks:
        if s.startswith(o):
            s = s[len(o):]
            if c and s.endswith(c):
                s = s[:-len(c)]
            break
    else:
        for p in prefixes:
            if s.startswith(p):
                s = s[len(p):]
                break
    return s.strip(" \t*!/-")


def density(text, syntax):
    """Comment lines PER CODE LINE for a whole file, or None when the file is too
    small for its ratio to mean anything.

    Per code line, not per total line: the budget is spent against the code an edit
    ADDS, so the baseline has to be measured in the same units. Mixing the two
    (comments/total measured, comments/code applied) understated every file's real
    habit by a third and denied edits that matched their file exactly."""
    lines = text.splitlines()
    flags = scan(lines, syntax)
    comments = sum(1 for f in flags if f)
    code = sum(1 for l, f in zip(lines, flags) if l.strip() and not f)
    if comments + code < MIN_BASELINE or code == 0:
        return None
    return comments / code


def baseline(path, old_text, syntax):
    """The comment density this edit should match: the file's own, or — for a file
    too small or not yet written — the density of its siblings, which is what
    "match the surrounding code" means for a brand-new file."""
    if old_text:
        d = density(old_text, syntax)
        if d is not None:
            return d
    ext = os.path.splitext(path)[1].lower()
    try:
        directory = os.path.dirname(os.path.abspath(path))
        names = sorted(n for n in os.listdir(directory)
                       if n.lower().endswith(ext) and n != os.path.basename(path))
    except Exception:
        return None
    ratios = []
    for name in names:
        if len(ratios) >= MAX_SIBLINGS:
            break
        body = read(os.path.join(directory, name))
        if body:
            d = density(body, syntax)
            if d is not None:
                ratios.append(d)
    return sum(ratios) / len(ratios) if ratios else None


def leading_comment_run(flags):
    """Length of the comment block a file OPENS with. Module docstrings, licence
    headers and this very file's preamble are conventional and are not what the
    density cap is aimed at, so a full-file Write is not charged for its header."""
    n = 0
    for f in flags:
        if not f:
            break
        n += 1
    return n


def added_comments(new_text, old_text, syntax, charge_header):
    """-> (list of (index, comment_text), added_code_line_count).

    "Added" means the stripped line is not already somewhere in `old_text`. An edit
    that merely carries a pre-existing comment through its context must not be
    blamed for it — the coder is told to keep the change minimal, so there would be
    no compliant move left."""
    lines = new_text.splitlines()
    flags = scan(lines, syntax)
    old = {l.strip() for l in (old_text or "").splitlines() if l.strip()}
    skip = 0 if charge_header else leading_comment_run(flags)
    comments, code = [], 0
    for i, (line, is_comment) in enumerate(zip(lines, flags)):
        s = line.strip()
        if not s or s in old:
            continue
        if is_comment:
            if i >= skip:
                comments.append((i, comment_text(line, syntax)))
        else:
            code += 1
    return comments, code


# --- payload ----------------------------------------------------------------

def chunks(tool, tool_input, path):
    """The (new_text, old_text, charge_header) pieces an edit writes.

    `charge_header` is False only for a whole-file Write, the one case where the
    text legitimately begins with a file header."""
    if tool == "Write":
        return [(tool_input.get("content") or "", read(path) or "", False)]
    if tool == "Edit":
        return [(tool_input.get("new_string") or "", tool_input.get("old_string") or "", True)]
    if tool == "MultiEdit":
        return [(e.get("new_string") or "", e.get("old_string") or "", True)
                for e in (tool_input.get("edits") or []) if isinstance(e, dict)]
    if tool == "NotebookEdit":
        if (tool_input.get("cell_type") or "code") != "code":
            return []  # a markdown cell is prose, not source
        return [(tool_input.get("new_source") or "", "", True)]
    return []


def syntax_for(tool, path):
    """The comment syntax to apply, or None when this file is out of scope."""
    if tool == "NotebookEdit":
        return SYNTAX[".py"]  # notebook code cells, overwhelmingly Python
    return SYNTAX.get(os.path.splitext(path)[1].lower())


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

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not path:
        sys.exit(0)

    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    if in_state_dir(path, root):
        sys.exit(0)

    syntax = syntax_for(tool, path)
    if syntax is None:
        sys.exit(0)

    cfg = load_config(root)
    if not cfg["enabled"]:
        sys.exit(0)

    try:
        pieces = chunks(tool, tool_input, path)
    except Exception:
        sys.exit(0)

    name = os.path.basename(path)
    total_comments, total_code = 0, 0
    for new_text, old_text, charge_header in pieces:
        if not new_text.strip():
            continue
        comments, code = added_comments(new_text, old_text, syntax, charge_header)
        total_comments += len(comments)
        total_code += code
        for _, text in comments:
            if any(a.search(text) for a in cfg["allow"]):
                continue
            for pattern, why in NOISE:
                if pattern.search(text):
                    deny(
                        f"Comment noise in {name} — this comment {why}:\n"
                        f"    {text}\n\n"
                        "A comment earns its line only by saying something the code "
                        "cannot: a constraint, a non-obvious reason, a caveat. Talk "
                        "about the change — which criterion it satisfies, what it "
                        "used to do, why it is correct — belongs in your return "
                        "message to the orchestrator and in phase-log.md, not in the "
                        "file, where it goes stale the moment the PR merges.\n"
                        "Delete it, or rewrite it as the technical reason the code "
                        "is written this way, and retry the edit."
                    )

    if total_comments <= cfg["floor"]:
        sys.exit(0)

    # Always the file as it stands ON DISK: an Edit's `old_string` is a fragment,
    # and the density of a fragment is not the density of the file.
    base = baseline(path, read(path) or "", syntax)
    ratio = max(base if base is not None else 0.0, cfg["min_ratio"])
    allowance = max(cfg["floor"], math.ceil(total_code * ratio))
    if total_comments <= allowance:
        sys.exit(0)

    if base is None:
        observed = "no comment density to compare against (new or small file)"
    else:
        observed = f"{name} currently sits at {round(base * 100)}%"
    deny(
        f"Too many comments for this edit: it adds {total_comments} comment lines "
        f"to {total_code} lines of code, and {observed}. The budget here is "
        f"{allowance}.\n\n"
        "Match the file's existing comment density — a comment is worth its line "
        "only when it says what the code cannot (a constraint, a non-obvious "
        "reason, a caveat). Drop the ones that restate the code or explain the "
        "change, keep the few that carry real information, and retry.\n"
        "If this file genuinely warrants heavier commenting than its neighbours, "
        "say so in your return message rather than working around this."
    )


if __name__ == "__main__":
    main()
