# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
