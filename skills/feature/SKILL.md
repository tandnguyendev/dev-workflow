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

## The phase-log checkboxes are MACHINE-PARSED — write them literally

`phase-log.md` is not just prose for humans. The hooks parse it with regexes, and
the exact strings below are load-bearing. Keep every phase section in the shape
`templates/phase-log.md` defines; a phase you write up in freeform prose is a phase
the safety hooks cannot see, and they fail SILENTLY when they can't see it.

| String | Who writes it | When | What reads it |
|---|---|---|---|
| `## Phase N — <title>` | you | at scaffold | all hooks — a heading that doesn't start with `## Phase` or `## Final review` (case-insensitive) is not a section, and its content is absorbed into the phase above |
| `[x] coded` | the `coder` | when it finishes implementing | — |
| `- Evidence: <cited proof>` | the `coder` pre-fills what it RAN (test/command output); you AUGMENT with what the reviewers verified | coder on return, you after reviews, before yielding | the Stop evidence gate — an empty or placeholder ledger is refused |
| `[x] code-reviewed` (Final review uses `full code review`) | you | after `code-reviewer` returns AND its findings are resolved | **the Stop evidence gate** — ticking either string ARMS it: from here on, ending your turn with an empty `- Evidence:` line is blocked |
| `[x] security-scanned` | you | after `security-scan-fast` returns; leave unticked when the phase's surface didn't warrant a scan | — |
| `[x] USER APPROVED` | **you, but ONLY after the user actually said so** | at the approval checkpoint | `status.py`, and the evidence gate's "which phase is current" logic |

The `coder` owns `[x] coded` and the first draft of `- Evidence:` because it is the
one that ran the code. Everything a REVIEW or the USER attests to is yours: the
review boxes, the augmented evidence, and `USER APPROVED`. The coder must never tick
a review box or `USER APPROVED` — see `agents/coder.md`.

`[x] USER APPROVED` is the one box you must never tick on your own initiative. No
hook can tell your tick from the user's — writing it without an explicit approval
from the user forges their sign-off, advances the phase, and switches the evidence
gate to the NEXT phase. If you are unsure whether they approved, they did not: ask.

Tick each box as its step completes, not in a batch at the end — the gate can only
protect a phase it knows has been reviewed.

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
   performance / security risk / effort). Merge near-duplicates. Present the
   options the panel ACTUALLY returned — one per architect, minus merges. Do NOT
   invent an extra option to hit a count: a synthesized option you wrote yourself
   carries the single-thread bias the panel exists to remove. If you think the
   panel missed an angle, say so to the user and offer to spawn another architect
   for it; don't quietly fill the gap.
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
3. Summarize the review(s) that ran for the user. Update `phase-log.md` — using the
   LITERAL checkbox strings from the table above, which the hooks parse. The coder
   already ticked `[x] coded` and pre-filled `- Evidence:` with what it ran; your job
   here is the review boxes and evidence:
   - If reviewers found issues, have `coder` fix them, then re-review.
   - Tick `[x] code-reviewed` once `code-reviewer`'s findings are resolved (plus
     `[x] security-scanned` if the scan ran).
   - **Augment the `- Evidence:` ledger** so it carries CITED proof it works:
     test/command output, `file:line` refs, concrete cases verified — one artifact
     per acceptance criterion, no "looks fine". Ticking `[x] code-reviewed` arms the
     `Stop`-hook evidence gate: it will refuse to let you yield for approval while
     this line is still empty or a placeholder, and it will keep refusing.
4. **CHECKPOINT: the user reviews AFTER the AI. Stop and wait.** ONLY after the user
   has actually approved, tick `[x] USER APPROVED` in `phase-log.md` and move on.
   Never tick it yourself to advance; never advance unapproved.
5. If it's a git repo and the user wants per-phase commits, commit scoped to this
   phase (`Phase N: <title>`). Skip otherwise. Keeps the final-audit diff clean.

## Stage 5 — Final review (whole feature)  (skip if trivial + single-phase)
**If you SKIP this stage, DELETE the `## Final review` section from `phase-log.md`.**
The template always scaffolds that section, but nothing ever ticks it when the stage
is skipped — and `status.py` reports the first unapproved section as the current one,
so the finished feature is reported as stuck on "Final review" forever. Removing the
section is what marks the feature done.

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
