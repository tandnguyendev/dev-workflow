#!/usr/bin/env python3
"""Shared parsing for the dev-workflow hooks.

The phase-log.md structure is load-bearing for three consumers — the SessionStart
status readout (status.py), the Stop evidence gate (evidence_guard.py), and the
feature skill's own accounting. Keeping the format's parsing in ONE place stops
those from drifting apart (e.g. a tweak to the heading regex silently disabling
the evidence gate, which fails open and so hides the breakage).

Import-safe: defines only constants and pure functions, no side effects. Hooks are
launched as `python .../hooks/<name>.py`, so this module's directory is on
sys.path[0] and `import _workflow` resolves without any extra setup.
"""
import os
import re

# The single source of truth for the phase-log structure.
PHASE_HEADING = re.compile(r"^##\s+(Phase[^\n]*|Final review[^\n]*)$", re.MULTILINE)
APPROVED = re.compile(r"\[[xX]\]\s*USER APPROVED")

STATE_DIR = ".dev-workflow"


def read(path):
    """File contents, or None if missing/unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def docs_dir(root):
    """Resolve the active feature's doc dir -> (dir, slug_or_None).

    Reads `.dev-workflow/active` for the slug; falls back to the project root for
    the legacy single-feature layout (slug None)."""
    active = read(os.path.join(root, STATE_DIR, "active"))
    if active:
        slug = next((l.strip() for l in active.splitlines() if l.strip()), "")
        d = os.path.join(root, STATE_DIR, "features", slug)
        if slug and os.path.isdir(d):
            return d, slug
    return root, None


def iter_phases(log):
    """Yield (title, body, approved) for each phase / final-review section in a
    phase-log, in document order. `body` is the text from the heading up to the
    next section heading (or end of file)."""
    heads = list(PHASE_HEADING.finditer(log))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(log)
        body = log[h.end():end]
        yield h.group(1).strip(), body, bool(APPROVED.search(body))
