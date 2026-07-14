#!/usr/bin/env python3
"""Stop hook: evidence gate for the dev-workflow plugin.

Enforces "evidence-gated completion": when the orchestrator ends its turn with
the current phase marked reviewed but its Evidence ledger in phase-log.md still
empty, block and ask it to fill cited proof before yielding to the user for
approval — and KEEP blocking while the ledger stays empty.

Why not `stop_hook_active`: Claude Code sets that flag on any Stop that happens
*because* a stop hook blocked the previous one. Exiting on it meant the gate could
be defeated by simply stopping twice — block, change nothing, stop again, and the
phase sailed through with an empty ledger. That made the gate advisory. Instead we
count consecutive refusals for the current phase in our own state file, so
"unchanged" is met with another refusal.

The counter exists to bound the loop, not to be an escape hatch: a Stop hook that
can refuse forever can trap a turn with no way out, which is worse than the hole it
closes. So after MAX_BLOCKS refusals the gate yields — but says loudly that it is
giving up on an unproven phase, so this can never happen SILENTLY.

Safety: fail-open on any error; stays silent unless a dev-workflow phase-log is
active and a phase is in the specific reviewed-but-unproven state. Only gates the
main turn (Stop), never subagents.
"""
import json
import os
import re
import sys

from _workflow import STATE_DIR, docs_dir, iter_phases, read

REVIEW_DONE = re.compile(r"\[[xX]\]\s*(?:code-reviewed|full code review)")

# Consecutive refusals allowed for one phase before the gate yields to avoid
# trapping the turn. Enough to outlast a model that stops reflexively; small
# enough that a genuinely stuck turn escapes in seconds.
MAX_BLOCKS = 3
COUNTER_FILE = "evidence-gate.json"
_MAX_KEYS = 64  # bound the file; far more than any plausible number of live phases


def _counter_path(root):
    return os.path.join(root, STATE_DIR, COUNTER_FILE)


def _load_all(root):
    """The whole {key: count} map, or {} if missing/corrupt."""
    data = read(_counter_path(root))
    if not data:
        return {}
    try:
        obj = json.loads(data)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}  # corrupt -> start over rather than fail shut


def load_counter(root, key):
    """Consecutive refusals already issued for `key`. Keyed PER phase (and per
    feature), so two concurrent features never reset each other's budget."""
    try:
        return int(_load_all(root).get(key, 0))
    except Exception:
        return 0


def save_counter(root, key, count):
    """Persist `count` for `key`. Returns True on success, False if it could not be
    written. The caller must NOT assume the write succeeded: a read-only or full
    `.dev-workflow/` would otherwise pin every load at 0, so the count could never
    grow to the give-up bound and the gate would block forever — the exact hard-lock
    the bound exists to prevent. On a False return the caller falls back to a signal
    that does not depend on this file."""
    try:
        os.makedirs(os.path.join(root, STATE_DIR), exist_ok=True)
        allc = _load_all(root)
        allc[key] = count
        if len(allc) > _MAX_KEYS:  # keep the most-recently-written keys
            allc = dict(list(allc.items())[-_MAX_KEYS:])
        with open(_counter_path(root), "w", encoding="utf-8") as fh:
            json.dump(allc, fh)
        return True
    except Exception:
        return False


def clear_counter(root, key):
    """Drop just this phase's budget (it advanced or got proven); leave any other
    feature's counts intact."""
    try:
        allc = _load_all(root)
        if key in allc:
            del allc[key]
            with open(_counter_path(root), "w", encoding="utf-8") as fh:
                json.dump(allc, fh)
    except Exception:
        pass


def evidence_empty(body):
    """True if the section's `- Evidence:` field is missing, a placeholder, or
    too short to be real cited proof. Captures everything from the `- Evidence:`
    field up to the next TOP-LEVEL field bullet (`- Word:` at column 0) or `##`
    heading, so proof written either inline OR as indented sub-bullets both count.

    The terminator must not match an indented bullet: listing artifacts under the
    field is the most natural way to cite several of them, and allowing indentation
    here meant the ledger's own sub-bullets ended it — so real, cited proof read as
    EMPTY and was refused, while the same text on one line passed.
    """
    m = re.search(
        r"-[ \t]*Evidence:[ \t]*(.*?)(?=\n-[ \t]*[A-Za-z][\w -]*:|\n#{1,4}\s|\Z)",
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

    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    ddir, slug = docs_dir(root)
    log = read(os.path.join(ddir, "phase-log.md"))
    if not log:
        sys.exit(0)  # no active workflow

    current_key = None
    for title, body, approved in iter_phases(log):
        if approved:
            continue  # this phase is done; look at the next
        # First UNAPPROVED section = the current one. Gate only this one.
        current_key = f"{slug or ''}::{title}"
        if REVIEW_DONE.search(body) and evidence_empty(body):
            count = load_counter(root, current_key) + 1
            # Persist BEFORE deciding, including past the limit: forgetting the
            # count on give-up would re-arm the gate on the next stop, so it would
            # oscillate (block, block, block, pass, block...) instead of staying
            # given up — and the give-up warning would never survive to be seen.
            saved = save_counter(root, current_key, count)

            # Give up when the count reaches the bound — OR when we could not even
            # persist the count AND have already blocked once this turn (the flag
            # Claude Code sets on a stop that a hook blocked). The second clause is
            # the backstop: if `.dev-workflow/` is read-only or full, `count` is
            # pinned at 1 forever, so without it the gate would block on every stop
            # and trap the turn. It bounds a broken counter at one block.
            unproven_msg = json.dumps({"systemMessage":
                "[dev-workflow evidence gate] GAVE UP: '" + title + "' is marked "
                "reviewed but its Evidence ledger is still empty. Letting the turn "
                "end so it cannot be trapped — but this phase is UNPROVEN. Do not "
                "approve it on the strength of the summary alone."})
            if count > MAX_BLOCKS or (not saved and payload.get("stop_hook_active")):
                print(unproven_msg)
                sys.exit(0)

            block(
                "[dev-workflow evidence gate] '" + title + "' is marked "
                "reviewed but its Evidence ledger in phase-log.md is empty. Before "
                "yielding for the user's approval, fill this phase's `- Evidence:` line "
                "with CITED proof — test/command output, file:line, the concrete cases "
                "verified — mapping to each acceptance criterion (not \"looks fine\"). "
                "Run the tests and paste what they actually printed; if you cannot prove "
                "it, say so to the user instead of ending the turn. "
                f"(Refusal {count} of {MAX_BLOCKS}; stopping again without filling the "
                "ledger will simply be refused again.)"
            )
        break  # only the current section is gated

    # Reached only when the current phase is proven (or the feature is done): clear
    # just this phase's budget so a later re-emptying gets a fresh one.
    if current_key:
        clear_counter(root, current_key)
    sys.exit(0)  # fail open


if __name__ == "__main__":
    main()
