#!/usr/bin/env python3
"""PreToolUse approval gate for the dev-workflow plugin.

Two protections:
1. The model may NEVER modify `.approval-gate` itself — not via
   Edit/Write/MultiEdit, and not via Bash. For Bash this is deny-by-default:
   ANY command that references `.approval-gate` is blocked, because a denylist of
   write constructs (`>`, tee, sed -i, ...) cannot enclose every way to write a
   file (e.g. `python -c "open('.approval-gate','w')..."`). Only the user changes
   it from their own shell (`! echo UNLOCKED > .approval-gate`), which is not a
   Claude tool call and is therefore not intercepted. This makes the gate a real
   barrier.
2. While `.approval-gate` says LOCKED, block Edit/Write/MultiEdit on source
   files so an unapproved phase cannot advance. Workflow working docs stay
   editable so the log can be maintained: anything under `.dev-workflow/` plus
   the doc basenames spec.md / plan.md / phase-log.md / conventions.md.

Gate states (first non-empty line of `.approval-gate`, case-insensitive):
  LOCKED    -> block source edits
  UNLOCKED  -> allow
  (absent)  -> allow (the gate is opt-in; create the file to activate it)
"""
import json
import os
import sys

# Doc basenames that are always workflow docs, wherever they live.
WORKING_DOC_NAMES = {"spec.md", "plan.md", "phase-log.md", "conventions.md"}
STATE_DIR = ".dev-workflow"
GATE_NAME = ".approval-gate"

GATE_EDIT_MSG = (
    "Only you can change the approval gate. Run it in YOUR shell so it is not a "
    "Claude tool call:\n"
    "    ! echo UNLOCKED > .approval-gate   (to allow the next phase)\n"
    "    ! echo LOCKED > .approval-gate     (to re-lock)"
)


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
    # Deny-by-default: any Bash command that so much as references the gate file
    # is blocked. A denylist of write constructs cannot cover every way to write
    # a file (interpreters with -c/-e, here-docs, install, patch, ...), so we do
    # not try — the model has no legitimate need to touch the gate via Bash.
    return GATE_NAME in command


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
        sys.exit(0)  # other Bash commands are not gated by the lock

    # --- Protection 2: LOCKED blocks source edits (edit tools only). ---
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
