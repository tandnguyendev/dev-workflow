---
name: rollback
description: Undo an AI agent's changes by restoring the git working tree to a checkpoint. Safe and reversible — saves current state first, never moves your branch, never hard-deletes. Optionally pass a checkpoint ref; defaults to the most recent.
allowed-tools: Bash(python "${CLAUDE_SKILL_DIR}/../../hooks/checkpoint.py" *)
---

Restore the working tree to a checkpoint, undoing recent agent changes. This is
safe: it first saves the current state as a reversible `pre-rollback` checkpoint,
never moves your branch/HEAD, and never hard-deletes anything from git.

The CLI is `python "${CLAUDE_SKILL_DIR}/../../hooks/checkpoint.py" <cmd>` (this
resolves to the plugin's `hooks/checkpoint.py`).

Steps:
1. If the user did NOT name a checkpoint, first list them and show the user so
   they can confirm the target (default = most recent non-`pre-rollback`
   checkpoint):
   ```
   python "${CLAUDE_SKILL_DIR}/../../hooks/checkpoint.py" list
   ```
2. Perform the rollback (pass the chosen ref, or omit for the default):
   ```
   python "${CLAUDE_SKILL_DIR}/../../hooks/checkpoint.py" rollback [ref]
   ```
3. Relay the tool's output verbatim, including how to reverse it:
   ```
   python "${CLAUDE_SKILL_DIR}/../../hooks/checkpoint.py" undo
   ```
   Also note that files CREATED since the checkpoint are left in place (they show
   up in `git status`) and can be removed manually if unwanted.

Only meaningful in a git repository. If the CLI prints "not a git repository" or
"no checkpoints", relay that and stop. Do not attempt manual `git reset`/`checkout`
yourself — always go through the CLI so the operation stays safe and reversible.
