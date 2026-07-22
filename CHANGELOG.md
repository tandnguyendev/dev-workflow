# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-07-22

Two complaints from running 0.7.0: the designs came back over-built, and small
changes ran the machinery of large ones. Same root cause — every role in the
workflow was rewarded for adding, and nobody was paid to cut.

### Added
- **Plan guard (`hooks/plan_guard.py`) — the anti-bloat rules are now ENFORCED, not
  just advised.** Everything above is prompt text, and prompt text kept losing to the
  model's instinct to split work and keep reviewing. A `Stop` hook now refuses to end
  a turn when a drafted `plan.md` leaves `## Size estimate` at the placeholder, when a
  phase after the first carries no `- Why separate:` reason, or when a phase-log
  records more than 2 review rounds with an empty `- Unresolved:`.
  No hook can judge whether four phases were warranted — a hook that tried would block
  good plans. It checks that the justification EXISTS: "because it is a separate step"
  passes. What it removes is the SILENT split and the silently-blown budget, which
  nobody can review. Silent until a phase has a real `- Scope:` (a scaffolded plan is
  not a plan, and Stages 0.5–2 legitimately write none), fail-open, and bounded like
  the evidence gate — it gives up loudly after 3 refusals rather than trap a turn.
- **The guard also keeps `project-map.md` alive.** Nothing forced the map to be
  updated — and the anti-bloat work above made that worse, not better: single-phase
  features skip Stage 5, Stage 5 is the only stage that maintains the map, and phases
  now have to earn themselves, so single-phase is the common case. The map would have
  rotted fastest on the commonest path. A finished feature (every section approved),
  in a project that has a map, must now carry a `- Project map updated:` line on its
  LAST section — anywhere else and an early phase could answer "no structural change"
  for work a later phase did. `"no structural change"` is a complete answer; silence
  is not. 25 tests, including the shipped templates passing their own guard both
  empty and filled.
- **Stage 0.5 — the requirements conversation, before anything is delegated.** The
  orchestrator now plays analyst: restate the request concretely, write acceptance
  criteria, surface conflicts with what the code already does, and ask — in ONE
  batched round — only the questions whose answers fork the design, stating
  assumptions in writing for everything else. Deliberately not a subagent: a
  subagent cannot stop to ask, so it would pick a reading silently, and a plan built
  on a wrong reading passes every review in this workflow, because reviewers check
  the code against the plan and never the plan against what was wanted.
- **Acceptance criteria actually exist now** (`spec.md` section 1b), plus a section
  1c recording what was asked, answered, and assumed. The evidence ledger already
  demanded "one artifact per acceptance criterion" and `plan.md` had a per-phase
  `Done when:` — but nothing in the workflow ever wrote the criteria down, so both
  pointed at nothing. They now flow from 1b into each phase's `Done when:`, into
  `plan-reviewer`'s new coverage check (a criterion no phase delivers is a missing
  phase; a phase serving no criterion is scope creep), and into the ledger.

### Changed
- **The machinery is now sized to the diff, not to the description.** The
  orchestrator estimates files and rough lines BEFORE picking a tier and says the
  estimate out loud; **a feature is trivial by default** and moving up a tier
  requires naming the signal that puts it there (a new interface, new persistent
  state, a boundary crossed). Each tier now states exactly what runs, so "standard"
  can't quietly mean "everything".
- **The tier is re-checked after the plan is drafted** — the first point where the
  size is real rather than guessed — and downgrading needs no permission: collapse
  the phases, drop the stages the lighter tier doesn't run, tell the user. Upgrading
  does need a named reason. The plan checkpoint now leads with tier, phase count and
  estimated size, so the user can reject the shape before paying for it.
- **Phase counts start at ONE and every extra phase must be justified** — it crosses
  a subsystem boundary, it needs its own rollback point, or it is too big to review
  in one sitting. The old "typically 2–5 phases for standard" guidance was an anchor
  that produced three phases for twenty-line changes; there is deliberately no target
  count now, because a range reads as a quota to fill.
- **`plan-reviewer` reviews in both directions.** It hunted only for what was
  missing, which made it a force for more work in a workflow that already had one.
  Over-engineering is now a first-class finding alongside missing work — speculative
  abstraction, config nobody will change, unrelated refactors and docs that crept in
  — and "merge these phases" / "this phase doesn't need to exist" / "this plan is too
  heavy for what it delivers" are recommendations it is expected to make. It checks
  the plan against the Simplicity contract, which binds the plan and not just code.
- **Architects must stay proportional and report size.** An angle is a lens, not a
  licence to grow the change: an option that solves a problem this project doesn't
  have is a losing option even from its own angle, and an architect with nothing to
  add at this size should say so rather than manufacture a difference. Every option
  now reports files + rough lines and how much of it is NEW structure, and that lands
  as a **Size column in the comparison table**, so bloat is visible at the moment the
  user chooses instead of three phases later.
- **External research is a separate switch from the codebase survey.** The survey is
  cheap and nearly always worth it; a web round-trip is only worth it when there is a
  real external question (unfamiliar protocol, domain rule with a standard answer,
  library choice, known-pitfall area). Adding a field to a response has none, and
  `domain-researcher` now returns survey-only when told to.
- **The templates stopped anchoring the plan up.** `plan.md` carried its own
  "typically 2–5 phases" line and scaffolded three empty phase blocks — the skill
  can say "start from one" all it likes while the file copied into every feature
  hands the model three slots to fill. It now scaffolds ONE phase, states the
  earn-your-phase rule, and carries a `Size estimate` section so an over-built plan
  is visible before approval. `phase-log.md` likewise scaffolds one phase section,
  not two.

### Fixed
- **Stage 5 was skipped on the wrong condition.** Its header said "trivial +
  single-phase" while the tier table said a standard feature that ends up one phase
  skips it too. A standard single-phase feature therefore either ran a cross-phase
  review with no cross-phase to review, or left an unticked `## Final review`
  section — which `status.py` reports as the current phase forever, so the feature
  never reads as done. One rule now, in the skill, the tier table and the template:
  **skip when the feature is a single phase, in any tier.**
- The sizing rules sat physically before the stage they depend on (you cannot size a
  request you have not pinned down), and are now Stage 0.8, after the clarify stage.
- Stage 4 now records `- Deferred nits:` — the field existed in the template with no
  instruction that ever filled it.
- `security-scan-fast` says whether each finding BLOCKS the phase, so its
  Critical/High/Medium/Low severities map onto the BLOCKING/NIT vocabulary the review
  round budget is actually spent on.
- **Plans cover the change, not a project.** Migrations, config, flags, docs,
  monitoring and refactors of code that happened to be read do not get a phase unless
  the feature cannot work without them — they go to the user as a suggestion or into
  `spec.md` non-goals.

## [0.7.0] - 2026-07-22

Two gaps that showed up in real runs: agents that didn't know what the project
already contained, and a review loop with no way to end.

### Added
- **`project-map.md` — the project's own knowledge file.** `conventions.md` says
  how code is written here; the map says what already EXISTS and where: module map,
  shipped features, shared building blocks, extension points, known gotchas,
  glossary. `/dev-workflow:init` drafts it alongside `conventions.md` (both go to
  the user for confirmation), `domain-researcher` verifies it against the code and
  reports stale entries — **the code wins when they disagree** — and Stage 5 appends
  each shipped feature, so project knowledge accumulates instead of being re-derived
  every feature. It is read LAZILY (orchestrator while researching/planning; the
  coder as inline excerpts for the module it touches), which is what keeps
  `conventions.md` free to stay under its ~50-line budget.
- **The existing-implementation survey.** `domain-researcher` now returns what this
  codebase already has for the requested feature — closest implementations at
  `path:line`, what to reuse, what would be duplicated — into `spec.md` section 2b.
  The architect panel, the plan and `plan-reviewer` all work from it, so "we already
  have this" surfaces before code is written, not in review. The trivial tier skips
  the researcher but not the survey.
- **`project-map.md` is a workflow doc to the approval gate**, so Stage 5's knowledge
  update isn't blocked at the one moment it is written — the final checkpoint, with
  the gate `LOCKED`.
- **Ordinary chat sees the map too.** `init` adds a pointer to `project-map.md` in
  `CLAUDE.md` — deliberately a pointer, not an `@`-import: importing it would load
  the whole map into every session (the standing cost the lazy-read design avoids)
  to answer a question most turns never ask. `conventions.md` stays `@`-imported,
  because rules apply to every turn and a map does not.

### Changed
- **Review loops are bounded at 2 fix rounds, then the user arbitrates.** The loop
  was "if reviewers found issues, have coder fix them, then re-review" — no exit
  condition, so coder and reviewer could argue until the context ran out. Now:
  re-reviews are delta-scoped to the previous findings plus the fix diff (not the
  phase again); findings are labelled BLOCKING or NIT and only BLOCKING ones can
  spend a round; the same finding is never sent back unchanged. Applies to the phase
  review, the Stage 3 plan review, and the Stage 5 audit.
- **The coder may dissent.** It answers a finding it believes is wrong with evidence
  (`file:line`, the covering test) instead of editing to make it go away, and returns
  FIXED / DISAGREE / NEEDS-DECISION per finding. Complying with a mistaken review
  puts a real defect in the code — that is the cost the round budget was hiding.
- **Deadlocks escalate to the user instead of being ticked away.** Budget exhausted
  with a blocking finding open → stop, present the finding, the rebuttal and a
  recommendation via `AskUserQuestion`. `[x] code-reviewed` now means resolved — by
  fix, by an accepted rebuttal, or by the user's explicit call — never "we ran out of
  rounds". An unresolved security finding always goes to the user, and to Stage 5.
- **`phase-log.md` records the argument**: `- Review rounds: N/2`, `- Unresolved:`,
  `- Deferred nits:`, and `- Project map updated:` in the final section. Prose lines,
  not parsed by the hooks — they exist so you can see how contested a phase was
  before approving it.

## [0.6.2] - 2026-07-14

Closes an independent audit of 0.6.1. Every finding was reproduced by running the
hooks (not by reading them) and each fix was reviewed by a fresh agent; the fixes
carry red-first tests. No behavior a correct 0.6.1 workflow relied on is removed.

### Fixed
- **The approval gate now blocks Bash while `LOCKED`.** `coder` has Bash, and a
  here-doc / `sed -i` / `python -c` wrote source behind the lock — the gate only
  covered the edit tools. A denylist of write constructs cannot be closed, so while
  `LOCKED` **all** Bash is denied (the coder runs tests/lint while `UNLOCKED`). Shell
  quoting like `.approval-gat"e"` can no longer smuggle the gate file past the check.
- **`rollback` no longer destroys `.dev-workflow/`.** A repo that commits its workflow
  docs lost its phase log — and the Evidence ledger written that phase — because
  `git read-tree --reset` deletes tracked paths absent from the snapshot, and
  snapshots exclude `.dev-workflow/`. It is now preserved across a rollback exactly as
  `.approval-gate` already was; `undo` recovers cleanly.
- **The evidence gate blocks more than once.** It trusted `stop_hook_active`, so
  block once → change nothing → stop again let an empty ledger through. It now refuses
  up to three times per phase, then yields **loudly** (never silently) so it can't trap
  a turn. The give-up bound survives a read-only `.dev-workflow/`, and the counter is
  per phase so concurrent features don't reset each other.
- **`## Final Review` (any capitalization) is parsed as a section.** The heading match
  was case-sensitive, so a capital `R` absorbed the section into the phase above it and
  marked the wrong phase approved. `USER APPROVED` stays case-sensitive on purpose, so
  incidental lowercase prose can't wave an unproven phase through.
- **Evidence written as sub-bullets counts.** The empty-ledger check mistook the
  ledger's own indented bullets for its terminator, so real cited proof read as empty.
- **Hooks invoke `python3`, not `python`.** On a stock Linux/macOS box there is no
  `python`, so every hook silently failed to launch — no gate, no checkpoints, no
  evidence gate. The plugin validator now fails if a hook ever names `python` again.
- The per-phase security scan is stated honestly as **surface-gated** (auth, input
  handling, crypto/secrets, data access, external I/O), not tier-gated; the README,
  `plugin.json`, and flow diagram no longer claim "security review at every step". The
  evidence gate is described as raising a floor, not verifying that the proof is true.
- The `code-reviewer` now carries the clean-code baseline inline instead of pointing at
  a plugin-relative path it cannot open from the user's project, so it and `coder`
  enforce the same baseline.
- `rollback`'s `undo` is no longer pre-approved in `allowed-tools` — it is itself a
  rollback that rewrites the working tree, so it gets the same confirmation.

### Changed
- The phase-log checkboxes are machine-parsed, so the feature skill, `coder`, and the
  template now state which literal strings the hooks read, who ticks each, and when —
  and that `coder` must never tick a review box or `USER APPROVED`.

**Updating** takes two steps — the first refreshes the catalog, the second pulls the
new code (the catalog refresh alone leaves your installed copy on 0.6.1):
```
/plugin marketplace update dev-workflow-marketplace
/plugin update dev-workflow@dev-workflow-marketplace
```

## [0.6.1] - 2026-07-14

### Removed
- **0.6.0 is withdrawn. This release reverts it to 0.5.0's behavior.** Do not run
  0.6.0. It added a Stop-hook "verify" check that executed the lint/test commands
  declared in the project's `conventions.md`, plus a "scope" check comparing the
  changed files against `plan.md`'s `- Files:`. An audit found three defects, two
  of them serious:
  - **Privilege escalation.** `hooks/gate.py` deliberately keeps `conventions.md`
    writable by the model even while the approval gate says `LOCKED`. The verify
    check shell-executed that same file's ```verify``` block — so the model could
    write `test: echo UNLOCKED > .approval-gate` and have another hook unlock the
    approval gate for it, with no tool call and no permission prompt. The same path
    gave arbitrary command execution outside Bash permissioning. The gate that only
    the user is supposed to be able to flip was flippable by the model.
  - **False blocks from Phase 2 onward.** The scope check diffed against `HEAD`,
    which is cumulative since the last commit — and per-phase commits are optional.
    So a phase that touched exactly the files it declared was still blocked over the
    previous, already-approved phase's uncommitted files, and the block message told
    the orchestrator to revert them. The test suite asserted this behavior as correct.
  - `lstrip("./")` is a character-set strip, so any dotfile declared in `- Files:`
    (`.github/workflows/ci.yml`, `.eslintrc.json`) lost its leading dot and was
    reported as scope creep.

  A verify gate is still the right idea — the evidence ledger is only a length check,
  so "ran tests, all pass" passes it today without anything having run. It will
  return reading its commands from a file the model cannot write.

## [0.5.0] - 2026-07-14

### Added
- **`conventions.md` now reaches ordinary chat, not just `/dev-workflow:*`.**
  Claude Code auto-loads only `CLAUDE.md` and its `@`-imports, so a plain chat
  session never saw `conventions.md` — only the plugin's skills and subagents,
  which Read it explicitly, did. `/dev-workflow:init` now also ensures
  `CLAUDE.md` imports it via an `@conventions.md` line (appending to an existing
  `CLAUDE.md`, or offering to create a minimal one), and tells you to restart any
  running session, since `CLAUDE.md` is loaded once at session start.

### Changed
- **Comment discipline is now enforceable, not just implied.** The baseline said
  only "comments explain WHY, not WHAT", which caught the wrong failure mode: it
  never stopped comments that narrate the diff, justify the change to the
  reviewer, or docstring every function in a file that has none. The
  `references/clean-code.md` rule now names those cases and requires matching the
  surrounding file's comment density; the same line ships verbatim in every
  project's Simplicity contract; and `code-reviewer` gained comment noise as an
  explicit focus area, so it actually gets flagged instead of falling through the
  generic "judge against the baseline" instruction.

## [0.4.0] - 2026-07-08

### Added
- **Simplicity contract in every project's `conventions.md`.** `/dev-workflow:init`
  now writes a fixed, always-on section of anti-over-engineering rules — build only
  what the task requires, no abstraction until a real third use, match existing
  patterns, handle only errors that can actually occur, and stop-and-ask before
  adding anything beyond the literal request. It ships verbatim in both the
  observed-project and greenfield paths and is never rephrased or softened.
- **`/dev-workflow:init` now surfaces model routing.** After writing
  `conventions.md`, init points you to the three ways to tune models — per-agent
  `.dev-workflow/models.json` (recommended), the `CLAUDE_CODE_SUBAGENT_MODEL` env
  var, or a full `.claude/agents/<name>.md` override — so routing is discoverable
  during setup, not just in the README. Init still writes only `conventions.md`.

### Changed
- **Clean-code principles now apply to every project, not just greenfield.** The
  `references/clean-code.md` baseline was reframed from a greenfield-only tie-breaker
  into an always-on engineering floor that the `coder` and `code-reviewer` enforce in
  every project. Precedence (linter/formatter > `conventions.md` > surrounding style >
  baseline) now resolves genuine conflicts rather than gating the baseline off
  entirely, so a project's established style still wins on the style-sensitive
  principles (function size, nesting) while universal hygiene applies everywhere.

## [0.3.0] - 2026-07-07

### Added
- **Per-agent model configuration.** Drop a `.dev-workflow/models.json` mapping each
  subagent to a model (`opus`/`sonnet`/`haiku`/`fable`, a full model ID, or
  `inherit`) and the orchestrator applies it at spawn time; omitted agents keep
  their default. `CLAUDE_CODE_SUBAGENT_MODEL` (all agents) and a `.claude/agents/`
  shadow (full replace) are documented as alternatives. See `templates/models.json`.
- **Adversarial plan review.** A `plan-reviewer` subagent breaks the drafted
  `plan.md` on paper before any code — hunting missing phases, hidden dependencies,
  oversized or untestable phases, ordering mistakes, and rollback gaps.
- **Automated hook test suite in CI.** 35 tests exercise the approval gate, evidence
  gate, checkpoint/rollback engine, and status readout exactly as Claude Code runs
  them, so the reliability backbone is regression-guarded.

### Changed
- **Lower token usage across the feature workflow.** One `coder` is reused across a
  feature's phases (continued, not respawned) so codebase intake is paid once, not
  per phase; the orchestrator hands the coder and reviewers the exact files/paths to
  touch instead of making them re-scan; and `conventions.md` is kept lean because
  every subagent re-reads it in full.
- **Per-phase security scan is gated by surface, not tier.** `security-scan-fast`
  runs whenever a phase touches a security-sensitive surface (auth/authz, input
  handling, crypto/secrets, data access, external I/O) in any tier — and is skipped
  for non-sensitive phases even in complex features.
- **Tighter Stage 3 planning.** Phases are right-sized (coherent, independently
  reviewable units), ordered by dependency then risk, and each names its evidence
  and a rollback point.
- README redesigned with a Mermaid flowchart, and the intro keyword-optimized for
  discoverability.
- _Internal:_ phase-log parsing consolidated into a single shared module so the
  SessionStart status hook and the Stop evidence gate can no longer drift apart.

### Fixed
- Checkpoints now work in a repository with no configured git identity (a fresh
  `git init` or a CI runner). Previously `git commit-tree` failed and the snapshot
  silently no-opped; the shadow-ref commits now carry a stable internal identity.

## [0.2.0] - 2026-07-02

### Added
- Checkpoint + rollback via git shadow refs (never touches your index/HEAD/branch),
  an evidence gate that requires cited proof before a phase is marked done, and
  workflow-state re-injection so the active feature/phase/gate survive `/compact`.
