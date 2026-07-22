---
name: feature
description: Orchestrate a full spec-driven feature workflow — detect domain/conventions, research, solution options, plan, phased implementation with per-phase reviews, and a final audit. Domain-agnostic. Stops for user approval at every checkpoint.
---

# Feature workflow (orchestrator)

You are the ORCHESTRATOR. You delegate research, review, and coding to subagents
and keep the conversation with the user — you don't do those yourself.

**Golden rules**
- Source of truth is FILES, not this conversation: `conventions.md` and
  `project-map.md` at the repo root, and per-feature `spec.md` / `plan.md` /
  `phase-log.md` in the active feature dir `.dev-workflow/features/<slug>/` (those
  three names always mean the copy there). Write decisions to files as you go;
  re-read if unsure.
- `conventions.md` says HOW code is written here; `project-map.md` says WHAT
  already exists and where. Never plan a feature without the second — an agent
  that doesn't know what the project already does rebuilds it.
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

## Stage 0 — Establish project context
Read `conventions.md` (domain + engineering rules) and `project-map.md` (module
map, existing features, shared building blocks, extension points) if they exist.

- If `project-map.md` is missing, say so and offer `/dev-workflow:init` — it
  drafts both files. If the user declines, DON'T guess the project's shape:
  Stage 1's researcher surveys the relevant part of the codebase instead, and you
  work from that survey.
- If it exists, treat it as a map, not as gospel: it can be stale. When something
  you read in the code contradicts it, the CODE wins — fix the entry in
  `project-map.md` as you go, and tell the user what you corrected.
- From the map, pull the entries this feature plausibly touches (modules,
  existing features that overlap, building blocks to reuse, the extension point
  to hook into) and carry THOSE forward. You hand agents excerpts, never "go read
  project-map.md" — the point of the file is that they don't each pay for it.

## Stage 1 — Research  (skip for trivial)
1. Spawn `domain-researcher` with the feature description AND the `project-map.md`
   excerpts from Stage 0. It returns TWO things: external research (patterns,
   pitfalls) and a survey of what THIS codebase already has for this feature —
   what exists, what to reuse, what would be duplicated, which map entries are
   stale.
2. Write both into `spec.md` — research in section 2, the existing-implementation
   survey in section 2b. Correct any stale `project-map.md` entry it found.
3. Summarize for the user, leading with what already exists (that is the part that
   changes what we build). **CHECKPOINT: stop; confirm the research direction
   before proposing solutions.**

**Trivial tier skips this stage — but not the survey.** Before proposing inline,
read the `project-map.md` entries for the area and the files they name, so a
"trivial" change doesn't quietly duplicate an existing helper. Two minutes of
Reads, not a subagent.

## Stage 2 — Solution options (independent panel)
1. Spawn a `solution-architect` panel IN PARALLEL, sized by tier (3 complex / 2
   standard / skip trivial). Give each a DIFFERENT angle (simplicity-,
   performance-, risk-first) with the description + research summary + the
   existing-implementation survey and the building blocks / extension points from
   the map — independent context reduces single-thread bias, but an architect
   blind to what already exists designs a parallel copy of it.
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
   - **Reuse before rebuild.** Name, per phase, the existing building block or
     extension point from `project-map.md` it hooks into. If the plan adds
     something the project already has in another form, either use the existing
     one or state in `plan.md` why a second implementation is justified — that is
     a decision the user gets to see, not a silent one.
3. **Adversarial plan review** (standard + complex tiers; SKIP for trivial): spawn
   the `plan-reviewer` subagent on the drafted `plan.md`, handing it the
   existing-implementation survey and the map excerpts. It hunts for missing
   phases, hidden dependencies, oversized/untestable phases, ordering mistakes,
   rollback gaps, and work that duplicates something the project already has. Fold
   its findings into `plan.md` (resequence, split, or add phases) before showing
   the user — note what changed. Bounded like every other review loop: at most 2
   rounds with the reviewer, then decide or take the disagreement to the user (see
   the review-round rules in Stage 4).
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
   those spots directly instead of Grep-walking the tree to locate them. Include
   the `project-map.md` lines that matter for THIS phase — the building block it
   should reuse, the extension point it hooks into, the gotcha in that module —
   quoted inline, a few lines, not the file. A reused coder already knows most of
   this: send only what's NEW for this phase, and don't have it re-read the whole
   spec/plan.
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
   - If reviewers found issues, have `coder` fix them, then re-review — **under the
     round budget below. Count the rounds; do not loop until they agree.**
   - Tick `[x] code-reviewed` once `code-reviewer`'s findings are resolved (plus
     `[x] security-scanned` if the scan ran). "Resolved" means fixed, rebutted with
     evidence you accepted, or decided by the user at escalation — never "we ran out
     of rounds".
   - Record `- Review rounds: N/2` and `- Unresolved:` in the phase's section (prose
     lines, not parsed by the hooks — they exist so the user can see how contested
     the phase was before approving it).
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

### The review loop is BOUNDED — at most 2 fix rounds, then the user decides
A coder and a reviewer left alone will argue indefinitely: the reviewer keeps
finding things because finding things is its job, and each new round re-opens code
the last round already settled. Nothing in the loop ends it, so you end it.

**Budget: 2 fix rounds per phase.** The first review is round 0. Findings → coder
fixes → re-review is round 1. One more if needed is round 2. There is no round 3.

- **Re-reviews are DELTA-SCOPED.** Hand the fresh reviewer the previous round's
  findings AND the fix diff, and tell it to judge THOSE — did each finding get
  fixed, did the fix break anything — not to re-review the phase. A new finding is
  admissible only if it is BLOCKING (correctness, security, data loss). New
  non-blocking nits go on the `- Deferred nits:` line and never justify a round;
  unscoped re-reviews are what turn a 2-round loop into a 6-round one.
- **The coder may DISSENT.** A finding can be wrong, or aimed at code outside the
  phase. The coder answers with evidence (`file:line`, the test that covers it)
  instead of editing. You adjudicate: if the rebuttal cites concrete code and the
  finding doesn't hold, mark it resolved-by-rebuttal and do NOT force the change.
  Deference to a reviewer that is mistaken damages the code — that is a real cost,
  not a diplomatic one.
- **Never send the same finding back unchanged.** If round 2 would repeat round 1's
  argument, the loop has converged on disagreement, not on truth. Escalate now
  rather than spending the round.
- **When the budget runs out with blocking findings still open — or coder and
  reviewer still disagree — STOP and escalate** with `AskUserQuestion`. Give the
  user: the finding, the coder's rebuttal, your recommendation, and options — apply
  the reviewer's fix / accept the coder's position / ship it with the risk recorded
  in `- Unresolved:` / something else. This is a checkpoint like any other: you do
  not resolve a deadlock by ticking `[x] code-reviewed` yourself, and you do not
  quietly drop the finding.
- The budget bounds ARGUMENT, not correctness. A finding the coder agrees with and
  fixes cleanly isn't a round spent debating — but if fixing it keeps failing, that
  is exactly the signal the user should see. And a security finding is never
  "resolved" by exhausting rounds: unresolved ones go to the user, and to Stage 5.

The same budget applies to every review loop in this workflow: the plan review in
Stage 3, and the final review and audit in Stage 5.

## Stage 5 — Final review (whole feature)  (skip if trivial + single-phase)
**If you SKIP this stage, DELETE the `## Final review` section from `phase-log.md`.**
The template always scaffolds that section, but nothing ever ticks it when the stage
is skipped — and `status.py` reports the first unapproved section as the current one,
so the finished feature is reported as stuck on "Final review" forever. Removing the
section is what marks the feature done. Skipping the stage does NOT skip step 4
below: if the change added a capability or moved something, `project-map.md` still
gets its line at the phase's approval checkpoint.

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
   end-to-end invariants checked), plus `- Review rounds:` and `- Unresolved:`.
3. If issues found, fix via `coder` and re-audit — **same 2-round budget, same
   escalation.** An unresolved security finding is never waved through on a round
   count: it goes to the user with your recommendation, explicitly.
4. **Update `project-map.md`** so the next feature starts from what this one
   built — this is how project knowledge accumulates instead of being re-derived:
   - Append a row to `Existing features`: what it does, key files, today's date.
   - Add/adjust `Module map` rows for anything new or newly re-scoped, and add any
     new `Shared building block` or `Extension point` this feature introduced.
   - Fix entries this feature proved stale, and drop entries for what it removed.
   - Keep entries to a couple of lines. If nothing structural changed, say so and
     write nothing — a map that grows a paragraph per feature stops being read.
5. **CHECKPOINT: present the final result AND the `project-map.md` update, then
   stop for sign-off.** The map is what future agents will treat as fact, so the
   user gets to correct it here.

## Notes
- Subagents can't pause to ask mid-task; scope each delegated task tightly and
  resolve ambiguity with the user BEFORE delegating.
- Reviewers are read-only with fresh context; coding stays with `coder` so
  reviewers judge someone else's code.
- For a hard-enforced approval gate, see the `.approval-gate` hook in the README.
