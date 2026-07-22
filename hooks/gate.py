#!/usr/bin/env python3
"""PreToolUse approval gate for the dev-workflow plugin.

Two protections:
1. The model may NEVER modify `.approval-gate` itself — not via Edit/Write/
   MultiEdit, and not via Bash. Only the user changes it from their own shell
   (`! echo UNLOCKED > .approval-gate`), which is not a Claude tool call and is
   therefore not intercepted.
2. While `.approval-gate` says LOCKED, block BOTH the edit tools on source files
   AND Bash entirely, so an unapproved phase cannot advance. Workflow working docs
   stay editable so the log can be maintained: anything under `.dev-workflow/` plus
   the doc basenames spec.md / plan.md / phase-log.md / conventions.md /
   project-map.md.

Why LOCKED denies Bash outright, rather than trying to spot the writes:
`coder` has Bash, and a denylist of write constructs cannot be closed — `>`, tee,
`sed -i`, here-docs, `patch`, `install`, `git checkout`, and any interpreter with
a `-c`/`-e` flag all write files, and no list of them is ever complete. Gating Bash
on "does this command look like a write?" therefore cannot hold, so we do not try:
while LOCKED, Bash is denied. The cost is nil, because LOCKED means "stop and wait
for the user to approve this phase" — there is nothing legitimate to run. The coder
does its work, tests and lint included, while UNLOCKED.

The same unclosable-denylist problem applies to protection 1, which matches the
gate's FILENAME. We normalize away shell quoting first (`.approval-gat"e"` is the
same file to the shell) but this stays best-effort by nature. It is not what makes
the gate hold: while LOCKED, no Bash runs at all, so the gate cannot be rewritten.
While UNLOCKED it is a guardrail against the model disabling the gate for the next
phase (`rm .approval-gate`), not a barrier against a determined attacker — and a
model that is already unlocked gains no privilege by writing UNLOCKED.

Gate states (first non-empty line of `.approval-gate`, case-insensitive):
  LOCKED    -> block source edits and all Bash
  UNLOCKED  -> allow
  (absent)  -> allow (the gate is opt-in; create the file to activate it)
"""
import json
import os
import re
import sys

# Doc basenames that are always workflow docs, wherever they live.
WORKING_DOC_NAMES = {"spec.md", "plan.md", "phase-log.md", "conventions.md",
                     "project-map.md"}
STATE_DIR = ".dev-workflow"
GATE_NAME = ".approval-gate"

GATE_EDIT_MSG = (
    "Only you can change the approval gate. Run it in YOUR shell so it is not a "
    "Claude tool call:\n"
    "    ! echo UNLOCKED > .approval-gate   (to allow the next phase)\n"
    "    ! echo LOCKED > .approval-gate     (to re-lock)"
)

BASH_LOCKED_MSG = (
    "Bash is blocked while the approval gate is LOCKED.\n"
    "LOCKED means the current phase is waiting on YOUR review — Claude should not be "
    "running anything, and Bash can write source (`sed -i`, here-docs, `python -c`), "
    "which would advance the phase behind the gate.\n"
    "Review the phase, then unlock from YOUR shell (Claude cannot do this):\n"
    "    ! echo UNLOCKED > .approval-gate\n"
    "Re-lock before the next phase with:\n"
    "    ! echo LOCKED > .approval-gate"
)

# Shell quoting can split the filename into pieces that are the same file to the
# shell but a different string to us (`.approval-gat"e"`), so strip quotes and
# escapes before matching.
_SHELL_QUOTES = re.compile(r"""['"\\]""")


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def bash_touches_gate(command):
    # Deny-by-default: any Bash command that so much as references the gate file is
    # blocked — the model has no legitimate need to touch the gate via Bash. Match
    # the raw command AND a quote-stripped form, so the shell's own quoting cannot
    # smuggle the name past a plain substring test.
    return GATE_NAME in command or GATE_NAME in _SHELL_QUOTES.sub("", command)


def is_working_doc(fp, project_dir):
    """True if the path is a workflow doc (safe to edit even when locked)."""
    if not fp:
        return False
    if os.path.basename(fp) in WORKING_DOC_NAMES:
        return True
    try:
        state = os.path.abspath(os.path.join(project_dir, STATE_DIR))
        return os.path.commonpath([state, os.path.abspath(fp)]) == state
    except Exception:
        return False


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # can't parse -> fail open

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    # --- Protection 1: the model may never modify the gate file. ---
    if tool in ("Edit", "Write", "MultiEdit"):
        fp = tool_input.get("file_path", "")
        if fp and os.path.basename(fp) == GATE_NAME:
            deny(GATE_EDIT_MSG)
    elif tool == "Bash":
        if bash_touches_gate(tool_input.get("command", "")):
            deny(GATE_EDIT_MSG)
        # NB: no early exit. Bash must fall through to the LOCKED check below —
        # returning here is what let a here-doc write source while LOCKED.

    # --- Protection 2: LOCKED blocks source edits AND all Bash. ---
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    gate_path = os.path.join(project_dir, GATE_NAME)
    if not os.path.isfile(gate_path):
        sys.exit(0)  # gate not activated

    try:
        with open(gate_path, "r", encoding="utf-8") as fh:
            state = ""
            for line in fh:
                if line.strip():
                    state = line.strip().upper()
                    break
    except Exception:
        sys.exit(0)  # unreadable -> fail open

    if state != "LOCKED":
        sys.exit(0)  # UNLOCKED or anything else -> allow

    # Locked: Bash can write source in too many ways to filter, so none of it runs.
    if tool == "Bash":
        deny(BASH_LOCKED_MSG)

    # Locked: still allow workflow docs so the log can be updated.
    if is_working_doc(tool_input.get("file_path", ""), project_dir):
        sys.exit(0)

    deny(
        "Coding is LOCKED pending your approval of the current phase.\n"
        "Review the phase, then unlock from YOUR shell (Claude cannot do this):\n"
        "    ! echo UNLOCKED > .approval-gate\n"
        "Re-lock before the next phase with:\n"
        "    ! echo LOCKED > .approval-gate"
    )


if __name__ == "__main__":
    main()
