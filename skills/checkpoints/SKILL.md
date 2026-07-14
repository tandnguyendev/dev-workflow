---
name: checkpoints
description: List the dev-workflow checkpoints — snapshots taken automatically before each agent edit — for the current git project. Read-only.
allowed-tools: Bash(python3 "${CLAUDE_SKILL_DIR}/../../hooks/checkpoint.py" list)
---

List the available checkpoints for this project and present them to the user.

Run exactly:
```
python3 "${CLAUDE_SKILL_DIR}/../../hooks/checkpoint.py" list
```
(That resolves to the plugin's `hooks/checkpoint.py`.)

Each output row is `<ref>` `<timestamp>` `<tool>`. Show them newest-first as a
short table. Rows marked `pre-rollback` are automatic recovery points created by a
previous rollback. If the output is `(no checkpoints)`, tell the user none exist
yet — checkpoints appear automatically after the agent edits files in a git repo.
Do not modify anything.
