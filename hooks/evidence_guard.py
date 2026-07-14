#!/usr/bin/env python3
"""Stop hook: evidence gate for the dev-workflow plugin.

Enforces "evidence-gated completion": when the orchestrator ends its turn with
the current phase marked reviewed but its Evidence ledger in phase-log.md still
empty, block ONCE and ask it to fill cited proof before yielding to the user for
approval.

Safety: fail-open on any error; nudges at most once per stop (honors
stop_hook_active) so it can never hard-lock a turn; stays silent unless a
dev-workflow phase-log is active and a phase is in the specific
reviewed-but-unproven state. Only gates the main turn (Stop), never subagents.
"""
import json
import os
import re
import sys

from _workflow import docs_dir, iter_phases, read

REVIEW_DONE = re.compile(r"\[[xX]\]\s*(?:code-reviewed|full code review)")


def evidence_empty(body):
    """True if the section's `- Evidence:` field is missing, a placeholder, or
    too short to be real cited proof. Captures everything from the `- Evidence:`
    field up to the next field bullet (`- Word:`) or `##` heading, so proof
    written either inline OR as following bullets both count."""
    m = re.search(
        r"-[ \t]*Evidence:[ \t]*(.*?)(?=\n[ \t]*-[ \t]*[A-Za-z][\w -]*:|\n##|\Z)",
        body, re.DOTALL)
    if not m:
        return True
    # Drop leading bullet dashes so "- `pytest` passed" counts as content.
    val = re.sub(r"^[ \t]*-[ \t]*", "", m.group(1), flags=re.MULTILINE)
    val = re.sub(r"\s+", " ", val).strip()
    if not val or val.startswith("<"):
        return True
    return len(val) < 15


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # can't parse -> fail open

    # Loop guard: if we already blocked this stop, let the turn end.
    if payload.get("stop_hook_active"):
        sys.exit(0)

    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    log = read(os.path.join(docs_dir(root)[0], "phase-log.md"))
    if not log:
        sys.exit(0)  # no active workflow

    for title, body, approved in iter_phases(log):
        if approved:
            continue  # this phase is done; look at the next
        # First UNAPPROVED section = the current one. Gate only this one.
        if REVIEW_DONE.search(body) and evidence_empty(body):
            block(
                "[dev-workflow evidence gate] '" + title + "' is marked "
                "reviewed but its Evidence ledger in phase-log.md is empty. Before "
                "yielding for the user's approval, fill this phase's `- Evidence:` line "
                "with CITED proof — test/command output, file:line, the concrete cases "
                "verified — mapping to each acceptance criterion (not \"looks fine\"). "
                "Then end your turn again."
            )
        break  # only the current section is gated
    sys.exit(0)  # fail open / nothing to gate


if __name__ == "__main__":
    main()
