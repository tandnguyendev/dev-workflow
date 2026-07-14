# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
