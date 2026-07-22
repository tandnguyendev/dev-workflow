---
name: feature
description: Orchestrate a full spec-driven feature workflow — establish project context, clarify the request into acceptance criteria, size the work, research, solution options, plan, phased implementation with per-phase reviews, and a final audit. Machinery scales to the size of the change. Domain-agnostic. Stops for user approval at every checkpoint.
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
  already exists and where. Never plan a feature without knowing what the project
  already does — from the map, or from the survey when there is no map. An agent
  that doesn't know rebuilds it.
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

## `plan.md` has a machine-checked contract too

The plan guard (`hooks/plan_guard.py`, a `Stop` hook) refuses to let a turn end
while any of these is missing. It cannot judge whether a reason is GOOD — that is
the user's call at the plan checkpoint — only whether you made the choice silently.

| Field | Where | Why it is enforced |
|---|---|---|
| `## Size estimate` | `plan.md`, once any phase's `- Scope:` is filled | It is what makes an over-built plan visible at the checkpoint. A plan that hides its size hides the thing the user needs to reject it. |
| `- Why separate:` | every phase AFTER the first | Each extra phase costs the user an implement-review-approve round-trip. Splitting stays allowed; splitting without naming why does not. |
| `- Unresolved:` | any `phase-log.md` phase whose `- Review rounds:` exceeds 2 | Going past the budget means coder and reviewer did not converge — that is a decision for the USER, and the extra rounds must not pass silently. |
| `- Project map updated:` | the LAST section of a finished feature, when the project has a `project-map.md` | Stage 5 is what maintains the map — and single-phase features skip Stage 5, which is now most of them. `"no structural change"` is a complete answer; saying nothing is not. |

Until a phase has a real `- Scope:`, the plan is still the untouched scaffold and
the guard stays silent — Stages 0.5–2 legitimately end turns with no plan written.

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

## Stage 0.5 — Clarify the request (this part is yours; you are the analyst)
**You are the only party in this workflow who can talk to the user.** Subagents
cannot stop to ask — they will silently pick an interpretation and build it, and a
plan built on a wrong reading survives every review in this workflow, because
reviewers check whether the code matches the plan, not whether the plan matches what
was wanted. So requirements work happens HERE, before anything is delegated, and it
is never delegated itself.

1. **Restate the request** in your own words, concretely: what the user wants, who or
   what will use it, and what visibly changes for them when it ships. A restatement
   the user corrects in one line has already paid for the whole stage.
2. **Write acceptance criteria** into `spec.md` section 1b — concrete and checkable,
   each one something you could later point an artifact at ("a request with no
   `page` param returns the first 20 orders"), not a goal ("pagination works").
   These are what Stage 4's Evidence ledger cites one artifact per, and what
   `plan.md`'s per-phase `Done when:` lines come from. Two to five is normal; a
   trivial change may have one.
3. **Surface conflicts with what exists** — from the map and the survey. "The orders
   endpoint already caps at 50; do you want pagination on top of that cap or
   replacing it?" is the kind of question only someone who read the code can ask,
   and it is the highest-value thing you do in this stage.
4. **Ask only what changes what gets built**, and batch it: ONE `AskUserQuestion`
   round, at most 3–4 questions, the ones whose answers actually fork the design.
   For everything else **state an assumption instead of asking** — an assumption in
   writing is faster for the user than a question, because vetoing takes one word and
   silence means yes. Record them in `spec.md` section 1c.
   Do NOT ask: implementation details the user has no stake in, anything the code
   already answers (go read it), or ceremonial questions ("should I add tests?" —
   yes). An interrogation is a worse failure than a wrong assumption you stated,
   because the user can catch the assumption.
5. **CHECKPOINT — only if you actually asked something.** If the restatement,
   criteria and assumptions raise no real fork, say them and keep going; do not
   manufacture a stop. A trivial change is usually one line of restatement, one
   criterion, and straight on.

Scale this like everything else: trivial changes get a sentence, complex features get
the full conversation. And this stage does not close — if an ambiguity appears later,
at planning or mid-implementation, YOU resolve it with the user then. Never guess, and
never hand the guess to a subagent to make for you.

## Stage 0.8 — Size it: the machinery must be proportional to the change
**The user pays for this workflow in wall-clock time and approval round-trips.** A
20-line change that runs a research agent, an architect panel, three phases and five
checkpoints is not thoroughness — it is a workflow failure, and it is the failure
this stage exists to prevent. Every stage you run must be one you could justify to
someone waiting on a 20-line fix.

**First, estimate the diff.** You could not do this before Stage 0.5 — you cannot
size a request you have not pinned down. Use the `project-map.md` excerpts and a
quick read of the files involved: how many files, roughly how many lines, one
subsystem or several. Say the estimate out loud to the user along with the tier. An
estimate you refuse to make is how a small change ends up on the heavy path.

**A feature is TRIVIAL by default.** Moving up a tier requires you to NAME the signal
that puts it there. "It feels like a real feature" is not a signal — most requests
feel like real features and most of them are twenty lines.

| Tier | It is this tier only if you can name one of these | What actually runs |
|---|---|---|
| **trivial** | *(default)* one subsystem, one reviewable diff, no new interface, no new dependency, no new persistent state — a validation rule, an added field, a config value, a bug fix, a new parameter with a default | codebase survey (map excerpts + read the files) → propose inline → **1 phase** → `code-reviewer` (+ `security-scan-fast` if the surface warrants) → your approval. **No researcher, no panel, no plan-reviewer, no Stage 5.** |
| **standard** | a new interface others will call (endpoint, command, screen, public function), OR new persistent state/schema, OR several files across one subsystem | survey, plus external research **only if there is a real external question** → 2-architect panel → plan + `plan-reviewer` → phases → Stage 5 only if the plan ended up with more than one phase |
| **complex** | crosses a subsystem or trust boundary, OR changes a data model other code depends on, OR the design itself is security-sensitive, OR wide blast radius | full machinery — 3-architect panel, full final audit |

**Re-check the tier after the plan is drafted, and DOWNGRADE without ceremony.** This
estimate is a guess; the plan is when you actually know. If the work turned out to be
one small diff, collapse it: drop the remaining phases into one, skip Stage 5, and
tell the user you scaled it down and why. Downgrading needs no permission. Upgrading
does: name the signal and tell the user before you spend their time on it.

The tier scales research and option-panel depth — NOT security coverage:
`code-reviewer` runs every phase in every tier, and `security-scan-fast` runs
whenever a phase touches a security-sensitive surface (see Stage 4), trivial or
complex alike. Nor does it scale the approval checkpoints: a cheaper tier means less
machinery between the checkpoints, never fewer of them.

## Stage 1 — Research  (skip for trivial)
**Two switches, not one.** The codebase survey is almost always worth it — it is
cheap, targeted, and it is what stops us rebuilding something. External research is
NOT: it is only worth a subagent and a web round-trip when there is a real external
question — an unfamiliar protocol/format, a domain rule with a standard answer, a
library choice, a known-pitfall area (auth, money, time zones, concurrency). Adding
a field to a response has no external question. When there isn't one, tell the
researcher to skip the web work and return the survey only, and say so to the user.

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
   performance-, risk-first) with the description + the acceptance criteria from
   `spec.md` 1b (an option is only valid if it satisfies them) + research summary + the
   existing-implementation survey and the building blocks / extension points from
   the map — independent context reduces single-thread bias, but an architect
   blind to what already exists designs a parallel copy of it. **Tell every
   architect your diff estimate and that the option must be proportional to it**
   — an angle is a lens, not a licence to grow the change. Left unanchored, a
   performance-first architect will invent a cache for a fifteen-line fix, and the
   synthesis then lands somewhere between "what was asked" and "what was invented".
2. Synthesize into `spec.md` section 3 as a comparison table (**size — files and
   rough lines** / complexity / performance / security risk / effort). The size
   column is the point: it makes an over-built option visible to the user at the
   checkpoint instead of three phases later. Merge near-duplicates. Present the
   options the panel ACTUALLY returned — one per architect, minus merges. Do NOT
   invent an extra option to hit a count: a synthesized option you wrote yourself
   carries the single-thread bias the panel exists to remove. If you think the
   panel missed an angle, say so to the user and offer to spawn another architect
   for it; don't quietly fill the gap.
3. Give your recommendation first, but don't decide for the user. If the smallest
   option satisfies the request, recommend it and say plainly what the larger ones
   buy — "handles 100× the traffic we have" is a cost, not a feature. The
   Simplicity contract in `conventions.md` binds this stage: no speculative
   options, config, or abstraction for imagined future needs.
4. **CHECKPOINT: use AskUserQuestion so the user picks. Stop and wait.** Record
   the choice + rationale in `spec.md` sections 4–5.

## Stage 3 — Plan
1. Enter Plan Mode (ask the user to press Shift+Tab twice, or hold a read-only
   planning stance — Plan Mode is behavioral, not a hard write-lock).
2. Map the files to change; split the work into phases. Write `plan.md`, following
   these rules:
   - **Start from ONE phase and justify every additional one — in writing, on a
     `- Why separate:` line the plan guard enforces.** A phase costs a full loop —
     coder, reviewers, an evidence ledger and a user approval round-trip — so the
     count is the single biggest lever on how long this feels to the user. Add a
     second phase only when you can NAME the reason: it crosses a subsystem
     boundary, it needs its own rollback point because the step is risky, or it is
     genuinely too big to review in one sitting. "It has three
     logical steps" is not a reason — steps a reviewer checks in one pass, that
     touch the same files, or that only make sense together are ONE phase.
     (Deliberately no target count: a range here reads as a quota to fill, and the
     plan comes back with the number rather than the work. If the honest answer is
     one phase for a standard feature, that is the plan.) The failure in the other
     direction is real too — a phase too big to review in one sitting hides bugs —
     but it is far rarer than over-splitting, and the reviewer will catch it.
   - **Order by dependency, then risk.** No phase depends on something a later
     phase builds; among independent phases, schedule the risky or uncertain ones
     EARLY so the plan fails fast, not late.
   - **Each phase independently testable.** Name how it will be proven — the
     test/command/output that becomes its `- Evidence:` ledger in Stage 4. A phase
     with no way to verify it is a planning bug. Its `Done when:` comes from the
     acceptance criteria in `spec.md` section 1b; between them, the phases must
     cover every criterion, and a criterion no phase delivers is a missing phase.
   - **Each phase has a rollback point.** Note where the checkpoint sits so a bad
     phase can be reverted cleanly (ties into the checkpoint/rollback machinery).
   - **Reuse before rebuild.** Name, per phase, the existing building block or
     extension point from `project-map.md` it hooks into. If the plan adds
     something the project already has in another form, either use the existing
     one or state in `plan.md` why a second implementation is justified — that is
     a decision the user gets to see, not a silent one.
   - **Plan the change, not a project.** Only what the request and the chosen
     option require. Migrations, config, flags, docs, monitoring, refactors of code
     you happened to read — none of these get a phase unless the feature genuinely
     cannot work without them. Things that are merely a good idea go to the user as
     a suggestion, or into `spec.md` section 5 as a non-goal. They do not get
     planned in silently.
3. **Re-check the tier now.** The plan is the first point where the size is real
   rather than guessed. If it came out smaller than the Stage 0.8 estimate,
   collapse the phases and drop the machinery the lighter tier doesn't run — then
   tell the user you scaled it down. This is the cheapest correction available in
   the whole workflow, and it is the one most often skipped.
4. **Adversarial plan review** (standard + complex tiers; SKIP for trivial): spawn
   the `plan-reviewer` subagent on the drafted `plan.md`, handing it the
   existing-implementation survey, the map excerpts, and your diff estimate. It
   hunts in BOTH directions — missing phases, hidden dependencies, untestable
   phases, ordering mistakes, rollback gaps and duplicated work, but equally
   over-engineering, unnecessary phases, and a plan too heavy for the change it
   delivers. Fold its findings into `plan.md` (resequence, split, MERGE, add or
   DELETE phases) before showing the user — note what changed. Bounded like every
   other review loop: at most 2 rounds with the reviewer, then decide or take the
   disagreement to the user (see the review-round rules in Stage 4).
5. **CHECKPOINT: present the plan, stop, get approval or edits before any code.**
   Lead with the shape — tier, phase count, estimated files/lines — so the user can
   say "that's too much machinery for this" BEFORE paying for it. If you cut the
   plan down in step 3, say what you cut.

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
   from the phase's `plan.md` block (including its `Done when:` — that is what the
   coder's Evidence has to prove) plus the one-line solution from `spec.md`, and
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
   - Record `- Review rounds: N/2`, `- Unresolved:` and `- Deferred nits:` in the
     phase's section (prose lines, not parsed by the hooks — they exist so the user
     can see how contested the phase was, and what was consciously let go, before
     approving it).
   - **Augment the `- Evidence:` ledger** so it carries CITED proof it works:
     test/command output, `file:line` refs, concrete cases verified — one artifact
     per acceptance criterion this phase delivers (`spec.md` section 1b), no
     "looks fine". Ticking `[x] code-reviewed` arms the
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

## Stage 5 — Final review (whole feature)  (skip when the feature is ONE phase)
**Skip condition: a single-phase feature, in any tier** — there is nothing
"cross-phase" to review, and the per-phase review already was the whole review. A
trivial feature is single-phase by definition; a standard one often ends up there
after the Stage 3 re-check, and it skips this stage too.

**If you SKIP this stage, DELETE the `## Final review` section from `phase-log.md`.**
The template always scaffolds that section, but nothing ever ticks it when the stage
is skipped — and `status.py` reports the first unapproved section as the current one,
so the finished feature is reported as stuck on "Final review" forever. Removing the
section is what marks the feature done. Skipping the stage does NOT skip step 4
below: if the change added a capability or moved something, `project-map.md` still
gets its line at the phase's approval checkpoint — and since you are deleting the
Final review section that normally carries `- Project map updated:`, write that line
on the LAST PHASE instead. The plan guard requires it there.

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
  resolve ambiguity with the user BEFORE delegating — that is what Stage 0.5 is
  for, and why the analyst role is yours and can never be delegated to a subagent.
- Reviewers are read-only with fresh context; coding stays with `coder` so
  reviewers judge someone else's code.
- For a hard-enforced approval gate, see the `.approval-gate` hook in the README.
