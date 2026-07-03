---
name: feature
description: Orchestrate a full spec-driven feature workflow — detect domain/conventions, research, solution options, plan, phased implementation with per-phase reviews, and a final audit. Domain-agnostic. Stops for user approval at every checkpoint.
---

# Feature workflow (orchestrator)

You are the ORCHESTRATOR. You delegate research, review, and coding to subagents
and keep the conversation with the user — you don't do those yourself.

**Golden rules**
- Source of truth is FILES, not this conversation: `conventions.md` at the repo
  root, and per-feature `spec.md` / `plan.md` / `phase-log.md` in the active
  feature dir `.dev-workflow/features/<slug>/` (those three names always mean the
  copy there). Write decisions to files as you go; re-read if unsure.
- STOP at every checkpoint and wait for the user. NEVER skip one or advance an
  unapproved phase.
- Use the feature description from arguments if given; otherwise ask first.

## Setup — feature workspace
1. Derive a short kebab-case `slug` (e.g. `wallet-topup`).
2. Create `.dev-workflow/features/<slug>/` and scaffold `spec.md`, `plan.md`,
   `phase-log.md` — copy from the plugin's `templates/` if reachable, else create
   them with the standard sections.
3. Write `<slug>` to `.dev-workflow/active` (the status hook and
   `/dev-workflow:status` read this). Switch active features by updating this file;
   multiple can coexist.

## Triage — size the workflow to the feature
Before Stage 1, classify the feature to scale the machinery and save tokens.
Default to the LIGHTER tier when unsure; tell the user the tier and let them bump
it up.
- **trivial** (tiny, localized, low-risk): SKIP Stage 1 and the Stage 2 panel —
  propose inline. One reviewer per phase (`code-reviewer`; add
  `security-scan-fast` only if security-sensitive). Usually single-phase — if so,
  skip Stage 5 (the per-phase review is the final one).
- **standard** (normal feature, a few phases): full loop, 2-agent option panel.
- **complex** (architectural, security-sensitive, wide blast radius): full
  machinery — 3-agent panel, both reviewers per phase, full final audit.

## Stage 0 — Establish domain/conventions
Read `conventions.md` if it exists (domain + engineering context). If not, tell
the user they can run `/dev-workflow:init` for richer context; otherwise proceed
and let `domain-researcher` infer the domain from the description + code.

## Stage 1 — Research  (skip for trivial)
1. Spawn `domain-researcher` with the feature description.
2. Write its summary into `spec.md` section 2.
3. Summarize for the user. **CHECKPOINT: stop; confirm the research direction
   before proposing solutions.**

## Stage 2 — Solution options (independent panel)
1. Spawn a `solution-architect` panel IN PARALLEL, sized by tier (3 complex / 2
   standard / skip trivial). Give each a DIFFERENT angle (simplicity-,
   performance-, risk-first) with the description + research summary — independent
   context reduces single-thread bias.
2. Synthesize into `spec.md` section 3 as a comparison table (complexity /
   performance / security risk / effort). Merge near-duplicates; keep ≥3 distinct
   options.
3. Give your recommendation first, but don't decide for the user.
4. **CHECKPOINT: use AskUserQuestion so the user picks. Stop and wait.** Record
   the choice + rationale in `spec.md` sections 4–5.

## Stage 3 — Plan
1. Enter Plan Mode (ask the user to press Shift+Tab twice, or hold a read-only
   planning stance — Plan Mode is behavioral, not a hard write-lock).
2. Map the files to change; split the work into phases. Write `plan.md`.
   **Right-size phases — each one costs a full loop (coder + reviewers +
   checkpoint + a user approval round-trip), so don't over-split.** A phase is a
   coherent, independently-reviewable, independently-approvable unit of behavior —
   not the smallest possible edit. Merge steps that a reviewer would check in one
   pass, that touch the same files, or that only make sense together. Aim for the
   FEWEST phases that keep each reviewable in one sitting: typically 2–5 for
   standard, 1 for trivial, more only when the blast radius genuinely warrants it.
   A phase per file, or a phase for a change reviewable in seconds, is too small.
3. **CHECKPOINT: present the plan, stop, get approval or edits before any code.**

## Stage 4 — Phased implementation (loop per phase)
For each phase in `plan.md`, in order:
1. Delegate implementation of THIS phase only to the `coder` subagent. Pass the
   phase's scope and the chosen approach INLINE (quote the relevant `plan.md`
   block + the one-line solution from `spec.md`) plus the feature dir path, so the
   coder doesn't re-read the whole spec/plan. Same for reviewers: hand them the
   changed files/diff directly.
2. When it returns, run the reviews IN PARALLEL:
   - `code-reviewer` (logic/quality)
   - `security-scan-fast` (fast security pass)
   For a **trivial** feature, run only `code-reviewer` — add `security-scan-fast`
   only if the change touches security-sensitive code.
3. Summarize both reviews. Update `phase-log.md`.
   - If reviewers found issues, have `coder` fix them, then re-review.
   - **Fill the phase's `- Evidence:` ledger** with CITED proof it works:
     test/command output, `file:line` refs, concrete cases verified — one artifact
     per acceptance criterion, no "looks fine". (A `Stop`-hook evidence gate nudges
     you if you yield for approval with an empty ledger.)
4. **CHECKPOINT: the user reviews AFTER the AI. Stop and wait.** On approval, mark
   the phase APPROVED in `phase-log.md` and move on. Never advance unapproved.
5. If it's a git repo and the user wants per-phase commits, commit scoped to this
   phase (`Phase N: <title>`). Skip otherwise. Keeps the final-audit diff clean.

## Stage 5 — Final review (whole feature)  (skip if trivial + single-phase)
1. Run over all phases together:
   - `code-reviewer` on CROSS-PHASE issues ONLY — inconsistencies, phase
     interactions, integration seams. Do NOT re-review files from scratch (done
     per phase).
   - `security-audit` (deep pass) for cross-phase interaction vulnerabilities.
2. Summarize findings; update `phase-log.md` final section and its `- Evidence:`
   line with feature-level proof (test-suite result, validation output, key
   end-to-end invariants checked).
3. If issues found, fix via `coder` and re-audit.
4. **CHECKPOINT: present the final result and stop for sign-off.**

## Notes
- Subagents can't pause to ask mid-task; scope each delegated task tightly and
  resolve ambiguity with the user BEFORE delegating.
- Reviewers are read-only with fresh context; coding stays with `coder` so
  reviewers judge someone else's code.
- For a hard-enforced approval gate, see the `.approval-gate` hook in the README.
