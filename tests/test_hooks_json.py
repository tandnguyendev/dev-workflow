"""hooks.json is the wiring that routes tool calls to the hooks — a tool missing
from a PreToolUse matcher bypasses the gate AND the checkpoint engine silently,
which is exactly how NotebookEdit escaped both. This drift-guard pins the wiring
to checkpoint.py's own MUTATING_TOOLS list so the two cannot disagree again."""
import json
import os
import re
import sys

from conftest import HOOKS

sys.path.insert(0, HOOKS)
import checkpoint  # noqa: E402


def load_pretooluse():
    with open(os.path.join(HOOKS, "hooks.json"), encoding="utf-8") as fh:
        return json.load(fh)["hooks"]["PreToolUse"]


def hooks_for(tool):
    """The hook commands hooks.json routes `tool` to (matchers are regexes)."""
    return [h["command"]
            for grp in load_pretooluse() if re.fullmatch(grp["matcher"], tool)
            for h in grp["hooks"]]


def test_every_mutating_tool_routes_to_gate_and_checkpoint():
    for tool in sorted(checkpoint.MUTATING_TOOLS):
        cmds = hooks_for(tool)
        assert any("gate.py" in c for c in cmds), f"{tool} bypasses the gate"
        assert any("checkpoint.py" in c for c in cmds), f"{tool} gets no checkpoint"


def test_read_only_tools_are_not_matched():
    # The matchers must stay scoped to mutating tools: running the checkpoint's
    # `git add -A` before every Read/Grep would tax every tool call for nothing.
    for tool in ("Read", "Grep", "Glob"):
        assert hooks_for(tool) == [], f"{tool} is matched as if it mutated files"
