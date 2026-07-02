#!/usr/bin/env python3
"""PreToolUse approval gate for the dev-workflow plugin.

Blocks Edit/Write/MultiEdit on SOURCE files while the project's `.approval-gate`
file says LOCKED, so an unapproved phase can never advance. Working docs
(spec.md / plan.md / phase-log.md) stay editable so the workflow can keep its
file-based source of truth up to date even while locked.

Only the user can unlock, because unlocking is done from their own shell
(e.g. `! echo UNLOCKED > .approval-gate`), which is not a Claude tool call and
therefore is not intercepted by this hook. Claude's own attempt to write the
gate file is blocked, so the gate is a real barrier, not a suggestion.

Gate states (first non-empty line of `.approval-gate`, case-insensitive):
  LOCKED    -> block source edits
  UNLOCKED  -> allow
  (absent)  -> allow (the gate is opt-in; create the file to activate it)
"""
import json
import os
import sys

# Docs (spec/plan/log) remain editable even when locked.
ALWAYS_ALLOWED = {"spec.md", "plan.md", "phase-log.md"}


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # Can't parse input -> fail open (don't wedge the session).
        sys.exit(0)

    # Resolve the project root reliably (hook cwd is not guaranteed).
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    gate_path = os.path.join(project_dir, ".approval-gate")

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
    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if file_path and os.path.basename(file_path) in ALWAYS_ALLOWED:
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
