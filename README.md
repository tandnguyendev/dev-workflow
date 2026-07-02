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
- **Only you can unlock**, from your own shell — Claude cannot, because any
  attempt to modify the gate file is blocked whether it comes through the edit
  tools *or* Bash (redirection, `tee`, `mv`, `sed -i`, `Set-Content`, ...):

```shell
! echo LOCKED > .approval-gate      # activate + lock
! echo UNLOCKED > .approval-gate    # after approving a phase
! echo LOCKED > .approval-gate      # re-lock before the next phase
```

The `!` prefix runs the command in your shell, not as a Claude tool, so it is not
intercepted by the hook. Requires Python on PATH (`python`/`python3`).
