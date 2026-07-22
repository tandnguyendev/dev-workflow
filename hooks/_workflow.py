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
import json
import os
import re

# The single source of truth for the phase-log structure.
#
# The HEADING match is case-insensitive on purpose: it decides whether a phase
# exists at all, and a heading it misses does not error — its body is silently
# absorbed into the phase above it, so a `[x] USER APPROVED` under a missed
# `## Final Review` (capital R) marked the WRONG phase approved and switched the
# evidence gate off for the rest of the feature. A human writing `Final Review` for
# `Final review` should not trip that. Kept to `##` (the template's depth) and
# anchored with `\b` so it matches structural headings, not `## Final reviewer notes`
# or a `Phased plan` line.
PHASE_HEADING = re.compile(
    r"^##\s+(Phase\b[^\n]*|Final\s+review\b[^\n]*)$", re.MULTILINE | re.IGNORECASE)
# APPROVED stays CASE-SENSITIVE. It gates whether a phase is done, so its failure
# must be safe: an unrecognized tick leaves the phase UNapproved (the gate keeps
# protecting it), which is the harmless direction. Case-insensitive would do the
# opposite — an incidental lowercase "user approved" in prose would wave an
# unproven phase through, exactly the fail-open the hooks exist to prevent.
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


# --- field values -----------------------------------------------------------
# Both guards ask the same question of these documents: "is this `- Field:` line
# actually filled in, or still the template's placeholder?" One implementation, so
# a fix to the tricky part (where a field ENDS) can't land in one hook and not the
# other.

def field_text(body, name):
    """The raw text of a `- <name>:` field, or None when the field is absent.

    Captures up to the next TOP-LEVEL field bullet (`- Word:` at column 0) or a
    heading, so a value written as indented sub-bullets is part of the field. The
    terminator must NOT match an indented bullet: listing several artifacts under a
    field is the natural way to write one, and ending the field at its own
    sub-bullets made real content read as empty."""
    m = re.search(
        r"-[ \t]*" + re.escape(name) + r":[ \t]*(.*?)(?=\n-[ \t]*[A-Za-z][\w -]*:|\n#{1,4}\s|\Z)",
        body, re.DOTALL)
    return m.group(1) if m else None


def is_unfilled(val, min_len=1):
    """True when a field value is missing, still the template placeholder, or too
    short to be a real answer. `<...>` is how every template marks a blank."""
    if val is None:
        return True
    # Drop leading bullet dashes so "- `pytest` passed" counts as content.
    val = re.sub(r"^[ \t]*-[ \t]*", "", val, flags=re.MULTILINE)
    val = re.sub(r"\s+", " ", val).strip()
    if not val or val.startswith("<"):
        return True
    return len(val) < min_len


# --- refusal counters -------------------------------------------------------
# A Stop hook that can refuse forever traps the turn, which is worse than the hole
# it closes. Both guards bound their refusals with the same per-key counter, kept
# here so the bookkeeping (and its failure mode) exists once.
_MAX_KEYS = 64  # bound the file; far more than any plausible number of live phases


def _counter_path(root, fname):
    return os.path.join(root, STATE_DIR, fname)


def _load_all(root, fname):
    """The whole {key: count} map, or {} if missing/corrupt."""
    data = read(_counter_path(root, fname))
    if not data:
        return {}
    try:
        obj = json.loads(data)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}  # corrupt -> start over rather than fail shut


def load_counter(root, fname, key):
    """Consecutive refusals already issued for `key`."""
    try:
        return int(_load_all(root, fname).get(key, 0))
    except Exception:
        return 0


def save_counter(root, fname, key, count):
    """Persist `count` for `key`. Returns True on success, False if it could not be
    written. The caller must NOT assume the write succeeded: a read-only or full
    `.dev-workflow/` would otherwise pin every load at 0, so the count could never
    grow to the give-up bound and the guard would block forever — the exact hard-lock
    the bound exists to prevent. On a False return the caller falls back to a signal
    that does not depend on this file."""
    try:
        os.makedirs(os.path.join(root, STATE_DIR), exist_ok=True)
        allc = _load_all(root, fname)
        allc[key] = count
        if len(allc) > _MAX_KEYS:  # keep the most-recently-written keys
            allc = dict(list(allc.items())[-_MAX_KEYS:])
        with open(_counter_path(root, fname), "w", encoding="utf-8") as fh:
            json.dump(allc, fh)
        return True
    except Exception:
        return False


def clear_counter(root, fname, key):
    """Drop just this key's budget (it advanced or got satisfied); leave the rest."""
    try:
        allc = _load_all(root, fname)
        if key in allc:
            del allc[key]
            with open(_counter_path(root, fname), "w", encoding="utf-8") as fh:
                json.dump(allc, fh)
    except Exception:
        pass
