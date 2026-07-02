# finance-workflow — a Claude Code plugin

A spec-driven feature workflow for finance/fintech projects. It runs a feature
through: **research → 3+ solution options → phased plan → phased implementation
(each phase code-reviewed + security-scanned) → final cross-phase audit**, and
stops for your approval at every checkpoint.

## What's inside

| Component | Type | Model | Purpose |
|-----------|------|-------|---------|
| `/finance-workflow:feature` | skill (orchestrator) | session model | Drives the whole workflow |
| `domain-researcher` | agent | inherit | Read-only + web research of domain best practices |
| `coder` | agent | Opus 4.8 | Implements one planned phase |
| `code-reviewer` | agent | inherit | Logic/quality review, read-only |
| `security-scan-fast` | agent | Fable 5 | Fast per-phase security scan |
| `security-audit` | agent | Opus 4.8 | Deep final cross-phase security audit |

## Install

```shell
# 1. Add this repo as a marketplace (GitHub shorthand: owner/repo)
/plugin marketplace add tandnguyendev/claude-finance-workflow

# 2. Install the plugin
/plugin install finance-workflow@finance-workflow-marketplace
```

Update later with `/plugin marketplace update finance-workflow-marketplace`.

## One required manual step: domain context

Claude Code plugins **cannot** ship a `CLAUDE.md` (project memory is always
project-local). After installing, copy the domain conventions into the project
where you'll use the workflow:

```shell
# from your project root
cp <path-to-cloned-repo>/templates/CLAUDE.md ./CLAUDE.md
cp <path-to-cloned-repo>/templates/{spec,plan,phase-log}.md ./
```

The agents and the `feature` skill read `CLAUDE.md`, `spec.md`, `plan.md`, and
`phase-log.md` from your project — they are the source of truth that survives
`/compact` and `/clear`.

## Usage

```shell
/finance-workflow:feature add a wallet top-up endpoint
```

The orchestrator will pause for your approval at each stage. You review AFTER
the AI reviewers at every phase; nothing advances unapproved.

## Hard approval gate (PreToolUse hook)

The workflow's checkpoints are behavioral (Claude is instructed to stop). For a
**hard, enforced** gate — important when real money is involved — this plugin
ships a `PreToolUse` hook (`hooks/gate.py`) that blocks `Edit`/`Write`/`MultiEdit`
on source code whenever a `.approval-gate` file at your project root says
`LOCKED`.

- The gate is **opt-in**: it does nothing until you create `.approval-gate`.
- Working docs (`spec.md`, `plan.md`, `phase-log.md`) stay editable while locked.
- **Only you can unlock**, from your own shell — Claude cannot, because its own
  write to the gate file is blocked too:

```shell
# activate + lock (once, at project root)
! echo LOCKED > .approval-gate

# after you approve a phase, unlock so coding can proceed
! echo UNLOCKED > .approval-gate

# re-lock before the next phase to force the next approval
! echo LOCKED > .approval-gate
```

(The `!` prefix runs the command in your shell, not as a Claude tool, so it is
not intercepted by the hook.) Requires Python on PATH (`python`/`python3`).

## Notes

- Money conventions (integer minor units, idempotency, audit logging) live in
  `templates/CLAUDE.md` and are echoed in the agent prompts.
