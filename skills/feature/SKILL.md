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

## Model routing — per-agent, user-overridable
Each agent has a sensible default model in its `agents/*.md` frontmatter (cheap
models scout/review, Opus writes code). If `.dev-workflow/models.json` exists, read
it ONCE now: it maps agent name → model (aliases `opus`/`sonnet`/`haiku`/`fable`, a
full model ID, or `inherit`; keys starting with `_` are ignored). When you spawn an
agent named there, pass that model as the spawn-time model override; for any agent
NOT listed, use its frontmatter default. If the file is absent or unparseable,
every agent keeps its default — never block on this.
Before Stage 1, classify the feature to scale the machinery and save tokens.
Default to the LIGHTER tier when unsure; tell the user the tier and let them bump
it up.
- **trivial** (tiny, localized, low-risk): SKIP Stage 1 and the Stage 2 panel —
  propose inline. Usually single-phase — if so, skip Stage 5 (the per-phase review
  is the final one).
- **standard** (normal feature, a few phases): full loop, 2-agent option panel.
- **complex** (architectural, security-sensitive, wide blast radius): full
  machinery — 3-agent panel, full final audit.
The tier scales research and option-panel depth — NOT security coverage:
`code-reviewer` runs every phase in every tier, and `security-scan-fast` runs
whenever a phase touches a security-sensitive surface (see Stage 4), trivial or
complex alike.

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
2. Map the files to change; split the work into phases. Write `plan.md`, following
   these rules:
   - **Right-size phases — each costs a full loop** (coder + reviewers + checkpoint
     + a user approval round-trip), so don't over-split. A phase is a coherent,
     independently-reviewable, independently-approvable unit of behavior — not the
     smallest possible edit. Merge steps a reviewer would check in one pass, that
     touch the same files, or that only make sense together. Aim for the FEWEST
     reviewable phases: typically 2–5 for standard, 1 for trivial, more only when
     the blast radius genuinely warrants it. A phase per file, or one reviewable in
     seconds, is too small; a phase too big to review in one sitting is too big —
     split it.
   - **Order by dependency, then risk.** No phase depends on something a later
     phase builds; among independent phases, schedule the risky or uncertain ones
     EARLY so the plan fails fast, not late.
   - **Each phase independently testable.** Name how it will be proven — the
     test/command/output that becomes its `- Evidence:` ledger in Stage 4. A phase
     with no way to verify it is a planning bug.
   - **Each phase has a rollback point.** Note where the checkpoint sits so a bad
     phase can be reverted cleanly (ties into the checkpoint/rollback machinery).
3. **Adversarial plan review** (standard + complex tiers; SKIP for trivial): spawn
   the `plan-reviewer` subagent on the drafted `plan.md`. It hunts for missing
   phases, hidden dependencies, oversized/untestable phases, ordering mistakes, and
   rollback gaps. Fold its findings into `plan.md` (resequence, split, or add
   phases) before showing the user — note what changed.
4. **CHECKPOINT: present the plan, stop, get approval or edits before any code.**

## Stage 4 — Phased implementation (loop per phase)
**Reuse ONE coder across the phases — don't respawn each phase.** Spawn the `coder`
for Phase 1; for every later phase, CONTINUE that same coder (via SendMessage)
rather than a fresh Task. It keeps its warm context — the files it already opened,
the conventions, and what earlier phases did — so you pay the codebase-intake cost
ONCE instead of per phase. Respawn a fresh coder only when a phase moves to an
unrelated subsystem (its warm context stops helping and just bloats its window) or
after the user made large manual changes it hasn't seen — brief a reused coder on
any such changes. Reviewers are the opposite: ALWAYS freshly spawned per phase —
their value is objective fresh eyes on code they didn't write.

For each phase in `plan.md`, in order:
1. Give the coder THIS phase only — its scope + the chosen approach, quoted INLINE
   from the phase's `plan.md` block plus the one-line solution from `spec.md`, and
   the feature dir path. Hand it the EXACT files to touch as paths — and the
   function/symbol or line range when `plan.md`'s `Files:` names them — so it Reads
   those spots directly instead of Grep-walking the tree to locate them. A reused
   coder already knows most of this: send only what's NEW for this phase, and don't
   have it re-read the whole spec/plan.
2. When it returns, run the reviews IN PARALLEL (freshly spawned) — hand each the
   changed files/diff and exact paths directly, never make them re-scan to find the
   change:
   - `code-reviewer` (logic/quality) — ALWAYS, every phase, every tier.
   - `security-scan-fast` (fast security pass) — ONLY when this phase touches a
     security-sensitive surface: auth/authz, input handling/parsing, crypto or
     secrets, data access (queries, serialization/deserialization), or external
     I/O (network, filesystem, subprocess). Gated by the phase's SURFACE, not the
     tier — a copy tweak or rename in a complex feature needs no scan; a new
     endpoint in a trivial one does. When unsure, run it.
   Rationale: the per-phase scan catches LOCAL, compounding bugs early (injection,
   hardcoded secrets, missing authz on a new endpoint) when they are cheap to fix.
   EMERGENT, cross-phase vulnerabilities are the Stage 5 `security-audit`'s job, so
   skipping the scan on non-sensitive phases loses nothing there.
3. Summarize the review(s) that ran for the user. Update `phase-log.md`.
   - If reviewers found issues, have `coder` fix them, then re-review.
   - **Fill the phase's `- Evidence:` ledger** with CITED proof it works:
     test/command output, `file:line` refs, concrete cases verified — one artifact
     per acceptance criterion, no "looks fine".
   A `Stop`-hook pre-approval gate independently checks all three before you can
   yield: the ledger is filled, the `verify` commands from `conventions.md` actually
   pass (it RUNS them — a claimed pass you didn't get will be caught), and the changed
   files stay inside the phase's declared `Files:` in `plan.md`. If it blocks, fix the
   code or the plan — never the commands, and never by widening `Files:` to cover an
   edit the phase didn't need.
4. **CHECKPOINT: the user reviews AFTER the AI. Stop and wait.** On approval, mark
   the phase APPROVED in `phase-log.md` and move on. Never advance unapproved.
5. If it's a git repo and the user wants per-phase commits, commit scoped to this
   phase (`Phase N: <title>`). Skip otherwise. Keeps the final-audit diff clean.

## Stage 5 — Final review (whole feature)  (skip if trivial + single-phase)
1. Run over all phases together:
   - `code-reviewer` on CROSS-PHASE issues ONLY — inconsistencies, phase
     interactions, integration seams. Do NOT re-review files from scratch (done
     per phase).
   - `security-audit` (deep pass) — owns EMERGENT, cross-phase interaction
     vulnerabilities (auth flows spanning phases, data-flow and trust-boundary
     analysis). It must ALSO give a full pass to any security-sensitive surface
     whose per-phase `security-scan-fast` was gated out in Stage 4, so nothing
     ships unscanned. Do NOT re-review clean, non-sensitive phases from scratch.
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
