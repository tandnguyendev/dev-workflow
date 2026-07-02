---
name: feature
description: Orchestrate a full spec-driven feature workflow for the finance project — research, solution options, plan, phased implementation with per-phase reviews, and a final audit. Stops for user approval at every checkpoint.
---

# Feature workflow (orchestrator)

You are the ORCHESTRATOR for building a new feature. You do not do research or
review yourself — you delegate those to subagents and keep the conversation with
the user. Coding is delegated to the `coder` subagent (Model B).

**Golden rules**
- The source of truth is FILES (`spec.md`, `plan.md`, `phase-log.md`), not this
  conversation. Write decisions to files as you go; re-read them if unsure.
- STOP at every checkpoint below and wait for the user. NEVER skip a checkpoint
  or proceed without explicit approval. This is a finance project — an
  unapproved phase must never advance.
- If the user gave the feature description as arguments, use it; otherwise ask
  for it first.

Follow `CLAUDE.md` conventions throughout.

## Stage 1 — Research
1. Spawn the `domain-researcher` subagent with the feature description.
2. Write its summary into `spec.md` section 2.
3. Present a short summary to the user. **CHECKPOINT: stop, ask if the research
   direction looks right before proposing solutions.**

## Stage 2 — Solution options
1. Based on the research, produce AT LEAST 3 solution options with tradeoffs
   (complexity / performance / security risk / effort). Fill `spec.md` section 3.
2. Give your recommendation (first option), but do not decide for the user.
3. **CHECKPOINT: use AskUserQuestion (or plain question) so the user picks an
   option. Stop and wait.** Then record the choice + rationale in `spec.md`
   sections 4–5.

## Stage 3 — Plan
1. Enter Plan Mode (ask the user to press Shift+Tab twice, or reason in a
   read-only planning stance — remember Plan Mode is behavioral, not a hard
   write-lock).
2. Map the files to change and break the work into small phases. Write `plan.md`.
3. **CHECKPOINT: present the plan, stop, and get the user to approve or edit it
   before any code is written.**

## Stage 4 — Phased implementation (loop per phase)
For each phase in `plan.md`, in order:
1. Delegate implementation of THIS phase only to the `coder` subagent.
2. When it returns, run the reviews IN PARALLEL:
   - `code-reviewer` (logic/quality)
   - `security-scan-fast` (Fable 5, fast security pass)
3. Summarize both reviews for the user. Update `phase-log.md`.
   - If reviewers found issues, have `coder` fix them, then re-review.
4. **CHECKPOINT: the user reviews AFTER the AI. Stop and wait for approval.**
   Only when the user approves, mark the phase APPROVED in `phase-log.md` and
   move to the next phase. Never advance an unapproved phase.

## Stage 5 — Final review (whole feature)
1. Run over the FULL diff of all phases (not just the last):
   - `code-reviewer` on the full diff.
   - `security-audit` (Opus, deep pass) for cross-phase interaction bugs.
2. Summarize findings, update `phase-log.md` final section.
3. If issues found, fix via `coder` and re-audit.
4. **CHECKPOINT: present the final result and stop for the user's sign-off.**

## Notes
- Subagents cannot pause to ask the user mid-task; keep each delegated task
  well-scoped from the files. If a phase is ambiguous, resolve it with the user
  BEFORE delegating.
- Reviewers are read-only and objective (fresh context). Coding stays with
  `coder`/Opus so reviewers judge someone else's code.
