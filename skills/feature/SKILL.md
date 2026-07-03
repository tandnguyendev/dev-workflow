---
name: feature
description: Orchestrate a full spec-driven feature workflow — detect domain/conventions, research, solution options, plan, phased implementation with per-phase reviews, and a final audit. Domain-agnostic. Stops for user approval at every checkpoint.
---

# Feature workflow (orchestrator)

You are the ORCHESTRATOR for building a new feature. You do not do research or
review yourself — you delegate those to subagents and keep the conversation with
the user. Coding is delegated to the `coder` subagent.

**Golden rules**
- The source of truth is FILES, not this conversation: project-wide
  `conventions.md` at the repo root, and per-feature `spec.md` / `plan.md` /
  `phase-log.md` inside the active feature dir `.dev-workflow/features/<slug>/`.
  Every mention of those three files below means the copy in the active feature
  dir. Write decisions to files as you go; re-read them if unsure.
- STOP at every checkpoint below and wait for the user. NEVER skip a checkpoint
  or proceed without explicit approval. An unapproved phase must never advance.
- If the user gave the feature description as arguments, use it; otherwise ask
  for it first.

## Setup — feature workspace
1. Derive a short kebab-case `slug` from the feature description (e.g.
   `wallet-topup`).
2. Create `.dev-workflow/features/<slug>/` and scaffold `spec.md`, `plan.md`,
   `phase-log.md` there — copy from the plugin's `templates/` if reachable,
   otherwise create them with the standard sections.
3. Record the active feature: write `<slug>` to `.dev-workflow/active`. The
   SessionStart status hook and `/dev-workflow:status` read this.
4. Multiple features can coexist under `.dev-workflow/features/`; switch the
   active one by updating `.dev-workflow/active`.

## Triage — size the workflow to the feature
Before Stage 1, classify the feature and scale the machinery to save tokens on
small work. Tell the user the tier you picked; they can override it.
- **trivial** (tiny, localized, low-risk — e.g. a copy tweak, one field, a small
  fix): SKIP Stage 1 research and the Stage 2 panel — propose the approach inline.
  Usually a single phase; if so, the per-phase review IS the final review — skip
  Stage 5.
- **standard** (a normal feature, a few phases): full loop, but a 2-agent option
  panel instead of 3.
- **complex** (architectural, security-sensitive, or wide blast radius): full
  machinery — 3-agent panel, full final audit.
The tier scales research and option-panel depth. It does NOT decide security
coverage: `code-reviewer` runs every phase in every tier, and `security-scan-fast`
runs whenever a phase touches a security-sensitive surface (see Stage 4) — trivial
or complex alike.
When unsure, pick the lighter tier and let the user bump it up.

## Stage 0 — Establish domain/conventions
- If `conventions.md` exists, read it — that is the domain + engineering context.
- If it does NOT exist, tell the user they can run `/dev-workflow:init` first for
  richer context; otherwise proceed, and rely on `domain-researcher` inferring
  the domain from the feature description and the code.

## Stage 1 — Research  (skip for trivial)
1. Spawn the `domain-researcher` subagent with the feature description.
2. Write its summary into `spec.md` section 2.
3. Present a short summary to the user. **CHECKPOINT: stop, ask if the research
   direction looks right before proposing solutions.**

## Stage 2 — Solution options (independent panel)
1. Spawn a `solution-architect` panel IN PARALLEL sized by tier — 3 agents for
   complex, 2 for standard, and SKIP the panel for trivial (propose inline).
   Give each a DIFFERENT angle (simplicity-first, performance-first, risk-first),
   passing the feature description and the research summary. Independent context
   per agent reduces single-thread bias.
2. Synthesize their returned options into `spec.md` section 3 as a comparison
   table (complexity / performance / security risk / effort). Merge near-
   duplicates but keep at least 3 distinct options.
3. Give your recommendation (put it first), but do not decide for the user.
4. **CHECKPOINT: use AskUserQuestion (or a plain question) so the user picks an
   option. Stop and wait.** Then record the choice + rationale in `spec.md`
   sections 4–5.

## Stage 3 — Plan
1. Enter Plan Mode (ask the user to press Shift+Tab twice, or reason in a
   read-only planning stance — Plan Mode is behavioral, not a hard write-lock).
2. Map the files to change and break the work into small phases. Write `plan.md`.
   Follow these planning rules:
   - **One reviewable diff per phase.** If a phase is too big to review in one
     sitting or bundles unrelated changes, split it.
   - **Order by dependency, then by risk.** A phase must not depend on something a
     later phase builds. Among independent phases, schedule the risky or uncertain
     ones EARLY so the plan fails fast, not late.
   - **Each phase independently testable.** Every phase names how it will be
     proven to work — the test/command/output that becomes its `- Evidence:`
     ledger in Stage 4. A phase with no way to verify it is a planning bug.
   - **Each phase has a rollback point.** Note where the checkpoint sits so a bad
     phase can be reverted cleanly (ties into the checkpoint/rollback machinery).
3. **Adversarial plan review** (standard + complex tiers; SKIP for trivial):
   spawn the `plan-reviewer` subagent on the drafted `plan.md`. It hunts for
   missing phases, hidden dependencies, oversized/untestable phases, ordering
   mistakes, and rollback gaps. Fold its findings into `plan.md` (resequence,
   split, or add phases) before showing the user — note what changed.
4. **CHECKPOINT: present the plan, stop, and get the user to approve or edit it
   before any code is written.**

## Stage 4 — Phased implementation (loop per phase)
For each phase in `plan.md`, in order:
1. Delegate implementation of THIS phase only to the `coder` subagent.
2. When it returns, run the reviews IN PARALLEL:
   - `code-reviewer` (logic/quality) — ALWAYS, every phase, every tier.
   - `security-scan-fast` (fast security pass) — ONLY when this phase touches a
     security-sensitive surface: auth/authz, input handling/parsing, crypto or
     secrets, data access (queries, serialization/deserialization), or external
     I/O (network, filesystem, subprocess). This gate is by the phase's SURFACE,
     not the tier — a copy tweak or rename in a complex feature does not need a
     scan; a new endpoint in a trivial one does. When unsure, run it.
   Rationale: the per-phase scan catches LOCAL, compounding bugs early (injection,
   hardcoded secrets, missing authz on a new endpoint) when they are cheap to fix.
   EMERGENT, cross-phase vulnerabilities are NOT this scan's job — the Stage 5
   `security-audit` owns those, so skipping the scan on non-sensitive phases loses
   nothing there.
3. Summarize the review(s) that ran for the user. Update `phase-log.md`.
   - If reviewers found issues, have `coder` fix them, then re-review.
   - **Fill the phase's `- Evidence:` ledger** with CITED proof that the phase
     works: test/command output, `file:line` references, the concrete cases
     verified — one artifact per acceptance criterion. No "looks fine" without an
     artifact. (A `Stop`-hook evidence gate will nudge you if you try to yield for
     approval with an empty ledger.)
4. **CHECKPOINT: the user reviews AFTER the AI. Stop and wait for approval.**
   Only when the user approves, mark the phase APPROVED in `phase-log.md` and
   move to the next phase. Never advance an unapproved phase.
5. After approval, if the project is a git repository and the user wants
   per-phase commits, create a commit scoped to this phase with a message
   derived from the phase title and its `phase-log.md` summary (e.g.
   `Phase N: <title>`). Skip if not a git repo or the user prefers one final
   commit. This keeps the final-audit diff clean and ties phases to history.

## Stage 5 — Final review (whole feature)  (skip if trivial + single-phase)
1. Run over the full feature (all phases together):
   - `code-reviewer` focused on CROSS-PHASE issues only — inconsistencies and
     interactions between phases, integration seams, and anything a per-phase
     review could not see. Do NOT re-review each file from scratch; that was
     already done per phase.
   - `security-audit` (deep pass) — owns EMERGENT, cross-phase interaction
     vulnerabilities (auth flows spanning phases, data-flow and trust-boundary
     analysis). It must ALSO give a full pass to any security-sensitive surface
     whose per-phase `security-scan-fast` was gated out in Stage 4, so nothing
     ships unscanned. Do NOT re-review clean, non-sensitive phases from scratch.
2. Summarize findings, update `phase-log.md` final section, and fill its
   `- Evidence:` line with feature-level proof (test-suite result, the validation
   command output, the key end-to-end invariants checked).
3. If issues found, fix via `coder` and re-audit.
4. **CHECKPOINT: present the final result and stop for the user's sign-off.**

## Notes
- Subagents cannot pause to ask the user mid-task; keep each delegated task
  well-scoped from the files. If a phase is ambiguous, resolve it with the user
  BEFORE delegating.
- Reviewers are read-only and objective (fresh context). Coding stays with the
  `coder` agent so reviewers judge someone else's code.
- For a hard-enforced approval gate, see the `.approval-gate` hook in the README.
