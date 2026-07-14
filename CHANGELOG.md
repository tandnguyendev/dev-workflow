# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-07-14

### Added
- **The evidence gate now checks reality, not prose length.** It only ever tested
  that the `- Evidence:` ledger held ≥15 characters of text — so `"ran tests, all
  pass"` passed the gate without anything having been run. Two mechanical checks
  join it in `hooks/evidence_guard.py`, blocking once with every failure listed:
  - **Verify** — the lint/test commands the project declares in a ```verify```
    block in `conventions.md` are actually EXECUTED, and the phase is blocked if
    they fail. `coder` was previously just *asked* to run the linter. Note this
    executes repo-declared commands, so run the workflow only in a repo you trust.
  - **Scope** — files changed outside the `- Files:` the phase declared in
    `plan.md` are flagged. Unplanned edits are unreviewed surface, and scope creep
    is the main source of accidental complexity.
  Both are opt-in by data: no ```verify``` block means no command gate, no
  `- Files:` means no scope gate. Both fail open, and the diff is snapshotted
  before the commands run so a test run's own build artifacts can't be read back
  as out-of-scope edits.

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
