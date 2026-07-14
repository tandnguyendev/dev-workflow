#!/usr/bin/env python3
"""Stop hook: pre-approval gate for the dev-workflow plugin.

Before the orchestrator yields to the user for phase approval, three things must
hold. Each is a REALITY check — the prose rules in the agent prompts ask for all
three, but prose is not enforcement, so the ones that can be checked mechanically
are checked here:

1. Evidence — the phase's `- Evidence:` ledger in phase-log.md carries cited proof.
2. Verify  — the lint/test commands the project declared in conventions.md
             actually RUN and PASS. Without this, "ran tests, all pass" in the
             ledger satisfies check 1 while nothing was ever run.
3. Scope   — the files actually changed stay within the `- Files:` the phase
             declared in plan.md. Out-of-scope edits are the main source of both
             accidental complexity and unreviewed surface.

All three run together and block ONCE with every failure listed, rather than
making the model discover them one stop at a time. They share one trigger: the
current phase is marked reviewed but not yet approved.

Safety: fail-open on any error; nudges at most once per stop (honors
stop_hook_active) so it can never hard-lock a turn; stays silent unless a
dev-workflow phase-log is active and a phase is in that reviewed-but-unproven
state. Only gates the main turn (Stop), never subagents.

NOTE on check 2: this executes commands declared in the project's own
conventions.md, in the project directory. That is the point — the alternative is
trusting the coder's word. It also means the workflow should only be run in a
repository you trust, the same way `npm test` or `make` would be.
"""
import json
import os
import re
import subprocess
import sys

from _workflow import docs_dir, iter_phases, read

REVIEW_DONE = re.compile(r"\[[xX]\]\s*(?:code-reviewed|full code review)")
# The machine-readable command block in conventions.md (see templates/conventions.md).
VERIFY_FENCE = re.compile(r"```verify\s*\n(.*?)```", re.DOTALL)
VERIFY_LINE = re.compile(r"^[ \t]*(lint|test):[ \t]*(\S.*?)[ \t]*$", re.MULTILINE)
# `### Phase 2 — title` in plan.md; matched to the phase-log section by "Phase N".
PLAN_HEADING = re.compile(r"^#{2,3}\s+(Phase\s+\d+)[^\n]*$", re.MULTILINE)
FILES_FIELD = re.compile(r"^[ \t]*-[ \t]*Files:[ \t]*(.*)$", re.MULTILINE)
# Paths in a `- Files:` line: backticked first, else bare tokens with a / or a dot.
BACKTICKED = re.compile(r"`([^`]+)`")
BARE_PATH = re.compile(r"[\w./\-]*[/.][\w./\-]+")

CMD_TIMEOUT = 300
# Workflow bookkeeping the coder is expected to touch — never a scope violation.
ALWAYS_IN_SCOPE = ("spec.md", "plan.md", "phase-log.md", "conventions.md")


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


def verify_commands(root):
    """The project's declared lint/test commands -> {name: command}.

    Empty when conventions.md has no ```verify block, which makes the check
    opt-in: a project that never declares commands is never gated on them."""
    conv = read(os.path.join(root, "conventions.md"))
    if not conv:
        return {}
    fence = VERIFY_FENCE.search(conv)
    if not fence:
        return {}
    # `<exact command, e.g. ...>` is the unfilled template placeholder — never run it.
    return {m.group(1): m.group(2) for m in VERIFY_LINE.finditer(fence.group(1))
            if not m.group(2).startswith("<")}


def run_verify(root):
    """Run each declared command; return a failure line per command that failed."""
    failures = []
    for name, cmd in sorted(verify_commands(root).items()):
        try:
            proc = subprocess.run(
                cmd, shell=True, cwd=root, timeout=CMD_TIMEOUT,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except Exception:
            continue  # can't run it -> fail open rather than block on our own bug
        if proc.returncode != 0:
            tail = (proc.stdout or "").strip().splitlines()[-15:]
            failures.append(
                "  %s: `%s` FAILED (exit %d)\n%s"
                % (name, cmd, proc.returncode,
                   "\n".join("    " + l for l in tail) or "    (no output)"))
    return failures


def declared_files(root, title):
    """Paths the phase declared in plan.md's `- Files:` line, or None if the phase
    (or plan.md) isn't found — None means "unknown", which never blocks."""
    plan = read(os.path.join(docs_dir(root)[0], "plan.md"))
    if not plan:
        return None
    key = re.match(r"(Phase\s+\d+)", title)
    if not key:
        return None  # the final-review section has no phase scope
    heads = list(PLAN_HEADING.finditer(plan))
    for i, h in enumerate(heads):
        if h.group(1) != key.group(1):
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(plan)
        m = FILES_FIELD.search(plan[h.end():end])
        if not m or m.group(1).strip().startswith("<"):
            return None  # unfilled template placeholder
        line = m.group(1)
        paths = BACKTICKED.findall(line) or BARE_PATH.findall(line)
        return [p.strip().lstrip("./") for p in paths if p.strip()]
    return None


def changed_files(root):
    """Files modified vs HEAD, plus untracked ones. Empty outside a git repo."""
    out = []
    for cmd in (["git", "diff", "--name-only", "HEAD"],
                ["git", "ls-files", "--others", "--exclude-standard"]):
        try:
            proc = subprocess.run(cmd, cwd=root, timeout=30, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except Exception:
            return []
        if proc.returncode != 0:
            return []
        out += [l.strip() for l in proc.stdout.splitlines() if l.strip()]
    return out


def scope_violations(root, title):
    """Changed files the phase never declared it would touch."""
    declared = declared_files(root, title)
    if not declared:
        return []  # nothing declared -> nothing to enforce
    stray = []
    for f in changed_files(root):
        if os.path.basename(f) in ALWAYS_IN_SCOPE or f.startswith(".dev-workflow/"):
            continue
        # A declared directory or file prefix covers everything beneath it.
        if any(f == d or f.startswith(d.rstrip("/") + "/") for d in declared):
            continue
        stray.append(f)
    return stray


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
        if not REVIEW_DONE.search(body):
            break  # not reviewed yet -> too early to gate
        problems = []
        if evidence_empty(body):
            problems.append(
                "- EVIDENCE: the `- Evidence:` ledger is empty. Fill it with CITED "
                "proof — test/command output, file:line, the concrete cases verified "
                "— mapping to each acceptance criterion (not \"looks fine\").")
        # Snapshot the diff BEFORE running the commands: a test run drops build
        # artifacts (__pycache__, coverage files) that would otherwise be read back
        # as out-of-scope edits the coder never made.
        stray = scope_violations(root, title)
        failures = run_verify(root)
        if failures:
            problems.append(
                "- VERIFY: the project's own declared commands do not pass. Fix the "
                "code (do not edit the commands to make them pass):\n"
                + "\n".join(failures))
        if stray:
            problems.append(
                "- SCOPE: this phase changed files it never declared in plan.md's "
                "`- Files:`:\n"
                + "\n".join("    " + f for f in stray)
                + "\n  Revert what the phase does not need. If a file genuinely "
                  "belongs to this phase, add it to plan.md's `- Files:` and say why "
                  "in phase-log.md — an unplanned edit is unreviewed surface.")
        if problems:
            block(
                "[dev-workflow pre-approval gate] '" + title + "' is marked reviewed "
                "but is not ready for the user's approval:\n\n"
                + "\n".join(problems)
                + "\n\nResolve these, then end your turn again.")
        break  # only the current section is gated
    sys.exit(0)  # fail open / nothing to gate


if __name__ == "__main__":
    main()
