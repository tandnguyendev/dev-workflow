#!/usr/bin/env python3
"""PreToolUse approval gate for the dev-workflow plugin.

Two protections:
1. The model may NEVER modify `.approval-gate` itself — not via
   Edit/Write/MultiEdit, and not via Bash (redirection, tee, mv, cp, sed -i,
   Set-Content, ...). Only the user changes it from their own shell
   (`! echo UNLOCKED > .approval-gate`), which is not a Claude tool call and is
   therefore not intercepted. This makes the gate a real barrier.
2. While `.approval-gate` says LOCKED, block Edit/Write/MultiEdit on source
   files so an unapproved phase cannot advance. Working docs
   (spec.md / plan.md / phase-log.md) stay editable so the log can be maintained.

Gate states (first non-empty line of `.approval-gate`, case-insensitive):
  LOCKED    -> block source edits
  UNLOCKED  -> allow
  (absent)  -> allow (the gate is opt-in; create the file to activate it)
"""
import json
import os
import re
import sys

# Docs (spec/plan/log) remain editable even when locked.
ALWAYS_ALLOWED = {"spec.md", "plan.md", "phase-log.md"}
GATE_NAME = ".approval-gate"

# Bash constructs that could write to / replace a file.
_BASH_WRITE = re.compile(
    r"(>>?|\btee\b|\bsed\b\s+-i|\bmv\b|\bcp\b|\btruncate\b|\bdd\b|"
    r"Set-Content|Out-File|Add-Content)",
    re.IGNORECASE,
)

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
    """True if a shell command appears to write to the gate file."""
    if GATE_NAME not in command:
        return False
    return bool(_BASH_WRITE.search(command))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # can't parse -> fail open (don't wedge the session)

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

    # Locked: still allow the working docs so the log can be updated.
    fp = tool_input.get("file_path", "")
    if fp and os.path.basename(fp) in ALWAYS_ALLOWED:
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
