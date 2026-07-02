# dev-workflow — a Claude Code plugin

A **general, domain-agnostic** spec-driven software development workflow. It runs
a feature through: **detect domain/conventions → research → 3+ solution options →
phased plan → phased implementation (each phase code-reviewed + security-scanned)
→ final cross-phase audit**, stopping for your approval at every checkpoint.

The domain is not hardcoded. It is read from the project's `conventions.md` (run
`/dev-workflow:init` once to generate it) or inferred per-feature from your
feature description and the surrounding code.

## What's inside

| Component | Type | Model | Purpose |
|-----------|------|-------|---------|
| `/dev-workflow:init` | skill | session model | Inspect the project, draft `conventions.md` |
| `/dev-workflow:feature` | skill (orchestrator) | session model | Drive the whole feature workflow |
| `/dev-workflow:status` | command | session model | On-demand readout of the active feature/phase/gate |
| `/dev-workflow:checkpoints` | skill | session model | List auto-snapshots taken before agent edits |
| `/dev-workflow:rollback` | skill | session model | Restore the working tree to a checkpoint (safe, reversible) |
| `domain-researcher` | agent | Haiku 4.5 | Read-only + web research of domain/stack best practices |
| `solution-architect` | agent | Haiku 4.5 | Produce one solution option from an assigned angle (panel) |
| `coder` | agent | Opus 4.8 | Implement one planned phase |
| `code-reviewer` | agent | inherit | Logic/quality review, read-only |
| `security-scan-fast` | agent | Fable 5 | Fast per-phase security scan |
| `security-audit` | agent | Opus 4.8 | Deep final cross-phase security audit |

Model routing is a sensible default: cheap models for research/option-sketching
(Haiku) and per-phase security scan (Fable), Opus reserved for coding and the
final audit. Edit the `model:` field in any `agents/*.md` to change.

**Token efficiency.** The `feature` skill triages each feature (trivial /
standard / complex) and scales the machinery: trivial work skips research and the
option panel and uses a single reviewer; standard uses a 2-agent panel; only
complex work runs the full 3-agent panel + both reviewers every phase + a full
final audit. The final review is cross-phase focused, not a full re-review.

## Install

```shell
/plugin marketplace add tandnguyendev/dev-workflow
/plugin install dev-workflow@dev-workflow-marketplace
```

Update later: `/plugin marketplace update dev-workflow-marketplace`.

## Getting started in a project

```shell
# 1. (optional but recommended) let the workflow learn your project
/dev-workflow:init            # inspects the repo, drafts conventions.md

# 2. run a feature — it scaffolds .dev-workflow/features/<slug>/{spec,plan,phase-log}.md
/dev-workflow:feature add pagination to the orders list endpoint

# 3. check where you are at any time (also injected automatically each session)
/dev-workflow:status
```

The workflow scaffolds its per-feature working docs automatically under
`.dev-workflow/features/<slug>/`; you no longer copy templates by hand. Several
features can be in flight at once — `.dev-workflow/active` names the current one.

The orchestrator pauses for your approval at each stage. You review AFTER the AI
reviewers at every phase; nothing advances unapproved.

## Domain context: how it's supplied

Plugins **cannot** ship a project's `CLAUDE.md` (project memory is always
project-local). So domain context is supplied per-project via `conventions.md`:

- **Init path**: `/dev-workflow:init` inspects the repo and drafts `conventions.md`
  (domain, stack, architecture, coding + security rules). You review and edit it.
- **Inference path**: if `conventions.md` is absent, `domain-researcher` infers
  the domain from your feature description plus a quick scan of the code, and the
  reviewers apply a generic security checklist.

## Coding conventions

The `coder` follows `conventions.md` and the surrounding code's style, and runs
the project's configured formatter/linter after each change; the `code-reviewer`
enforces the same. For greenfield code with no stated convention, both fall back
to a minimal, explicitly subordinate baseline in `references/clean-code.md`
(the linter and project conventions always win).

## Hard approval gate (PreToolUse hook)

The workflow's checkpoints are behavioral (Claude is instructed to stop). For a
**hard, enforced** gate, this plugin ships a `PreToolUse` hook (`hooks/gate.py`)
that blocks `Edit`/`Write`/`MultiEdit` on source code whenever a `.approval-gate`
file at your project root says `LOCKED`.

- Opt-in: does nothing until you create `.approval-gate`.
- Working docs (`spec.md`, `plan.md`, `phase-log.md`) stay editable while locked.
- **Only you can unlock**, from your own shell — Claude cannot. Editing the gate
  via `Edit`/`Write`/`MultiEdit` is blocked, and via Bash it is **deny-by-default**:
  any command that so much as references `.approval-gate` is refused (a denylist of
  write constructs can't cover every way to write a file — `python -c`, here-docs,
  `install`, ...). A rollback also cannot flip the gate — the live gate state is
  preserved across `/dev-workflow:rollback` and is never captured into a checkpoint.

```shell
! echo LOCKED > .approval-gate      # activate + lock
! echo UNLOCKED > .approval-gate    # after approving a phase
! echo LOCKED > .approval-gate      # re-lock before the next phase
```

The `!` prefix runs the command in your shell, not as a Claude tool, so it is not
intercepted by the hook. Requires Python on PATH (`python`/`python3`).

## Checkpoint / rollback

While you work in a git repo, a `PreToolUse` hook (`hooks/checkpoint.py`)
automatically snapshots the working tree before each mutating tool call to an
immutable shadow ref `refs/dev-workflow/checkpoints/<ts>`, using git plumbing on a
temporary index — it never touches your index, HEAD, branch, or working tree, and
never blocks or slows a tool call to a halt (it is fail-open with a timeout).

- `/dev-workflow:checkpoints` — list the snapshots (newest first).
- `/dev-workflow:rollback [ref]` — restore the working tree to a checkpoint
  (default: the most recent). It first saves your current state as a reversible
  `pre-rollback` checkpoint, so a subsequent `undo` reverses it; it never moves
  your branch and never hard-deletes anything from git.

**Safety.** Every restore is preceded by a durable snapshot, so uncommitted work
is always recoverable. Rollback restores tracked file *content*; files you created
since the checkpoint are left in place (they show in `git status`).

**v1 limitations (deliberately small surface):**
- Git repositories only — a silent no-op elsewhere.
- No retention/pruning yet: snapshot refs accumulate under
  `refs/dev-workflow/checkpoints/*`. They are local-only (not pushed by
  `git push`); prune with
  `git for-each-ref --format='delete %(refname)' refs/dev-workflow | git update-ref --stdin`.
- Snapshots capture non-gitignored files, so keep secrets in `.gitignore` (git
  respects it) — otherwise untracked secrets get recorded in the refs.
- Requires `python` on PATH (Windows: ensure `python`, not only `py`).
- Add `.dev-workflow/` to your project `.gitignore` (the feature workflow uses it).

## Context re-injection (survives /compact)

A `SessionStart` hook (`hooks/status.py`) re-surfaces the active feature, phase
progress, and gate state into context on every session start — **including after
a `/compact` or auto-compaction** (it fires with `source: "compact"` and adds a
stronger "context was just compacted — re-read the files" reminder). This keeps
the workflow's file-based source of truth (`spec.md` / `plan.md` / `phase-log.md`)
from being lost to context rot. It stays silent when no workflow is active.

## Evidence gate (proof, not "looks fine")

The workflow's completion checkpoints ask for *cited proof*, not assertions. Each
phase's `phase-log.md` has an `- Evidence:` ledger that must be filled with
concrete artifacts — test/command output, `file:line` references, the specific
cases verified — one per acceptance criterion. The review subagents are instructed
to back every verdict (pass or fail) with what they actually checked.

A `Stop` hook (`hooks/evidence_guard.py`) enforces this: if you end a turn with the
current phase marked reviewed but its Evidence ledger still empty, it blocks once
and asks you to fill cited proof before yielding for approval. It is fail-open and
nudges **at most once per stop** (it honors `stop_hook_active`), so it can never
hard-lock a turn, and stays silent unless a dev-workflow phase-log is active.
