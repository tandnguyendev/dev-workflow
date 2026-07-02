#!/usr/bin/env python3
"""SessionStart hook for the dev-workflow plugin.

Re-surfaces the workflow's file-based source of truth into context at the start
of every session (including resume and post-compact), so the current phase and
approval state are not lost to context rot. Prints a short status block to
stdout (which SessionStart injects into context). Stays SILENT when no workflow
is active (no phase-log.md), so it never adds noise to unrelated sessions.
"""
import json
import os
import re
import sys

# Ensure UTF-8 output regardless of the host locale (Windows pipes default to
# cp1252, which mangles em dashes and other non-ASCII in feature names).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def read_input():
    """Return (project_dir, source). `source` is the SessionStart trigger —
    "startup" | "resume" | "clear" | "compact" — used to tailor the reminder."""
    raw = ""
    try:
        raw = sys.stdin.read()
    except Exception:
        pass
    source = ""
    cwd = ""
    if raw.strip():
        try:
            data = json.loads(raw) or {}
            source = data.get("source", "") or ""
            cwd = data.get("cwd", "") or ""
        except Exception:
            pass
    root = os.environ.get("CLAUDE_PROJECT_DIR") or cwd or os.getcwd()
    return root, source


def read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def docs_dir(root):
    """Resolve the active feature's doc dir. Falls back to the project root for
    the legacy single-feature layout. Returns (dir, slug_or_None)."""
    active = read(os.path.join(root, ".dev-workflow", "active"))
    if active:
        slug = next((l.strip() for l in active.splitlines() if l.strip()), "")
        d = os.path.join(root, ".dev-workflow", "features", slug)
        if slug and os.path.isdir(d):
            return d, slug
    return root, None


def title_from(text, prefix):
    if not text:
        return None
    m = re.search(r"^#\s*" + re.escape(prefix) + r"\s*(.+)$", text, re.MULTILINE)
    if m:
        name = m.group(1).strip()
        return None if name.startswith("<") else name
    return None


def main():
    root, source = read_input()
    ddir, slug = docs_dir(root)
    log = read(os.path.join(ddir, "phase-log.md"))
    if not log:
        sys.exit(0)  # no active workflow -> stay silent

    feature = (title_from(log, "Phase log:")
               or title_from(read(os.path.join(ddir, "spec.md")) or "", "Spec:")
               or slug or "(unnamed)")

    # Phase headings (and the Final review section) and their approval state.
    phases = []
    for m in re.finditer(r"^##\s+(Phase[^\n]*|Final review[^\n]*)$", log, re.MULTILINE):
        block = log[m.end():]
        nxt = re.search(r"^##\s+", block, re.MULTILINE)
        block = block[:nxt.start()] if nxt else block
        approved = bool(re.search(r"\[[xX]\]\s*USER APPROVED", block))
        phases.append((m.group(1).strip(), approved))

    current = next((name for name, ok in phases if not ok), None)

    gate = read(os.path.join(root, ".approval-gate"))
    if gate is None:
        gate_state = "no gate file"
    else:
        first = next((l.strip() for l in gate.splitlines() if l.strip()), "")
        gate_state = first.upper() or "empty"

    lines = []
    if source == "compact":
        # Context was just compacted; the summary may have dropped workflow state.
        lines.append("[dev-workflow] Context was just compacted — summarized memory "
                     "may have lost workflow state. The files below are the source of "
                     "truth; re-read them before acting.")
    lines.append("[dev-workflow] Active feature: " + feature)
    if phases:
        done = sum(1 for _, ok in phases if ok)
        lines.append(f"  Phases: {done}/{len(phases)} approved"
                     + (f"; current -> {current}" if current else "; all approved"))
    lines.append(f"  Approval gate: {gate_state}")
    lines.append("  Source of truth: spec.md / plan.md / phase-log.md "
                 "(re-read these, not conversation memory).")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
