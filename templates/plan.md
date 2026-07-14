# Plan: <feature name>

> Source of truth for HOW. Derived from spec.md. Approved in Plan Mode before any
> code is written. Right-size phases: each is a coherent, independently-reviewable
> unit — small enough to review in one pass, but not smaller. Each phase costs a
> full coder+review+approval loop, so merge steps that belong together rather than
> splitting per file. Typically 2–5 phases (1 if trivial).

## Files expected to change
- `path/to/file` — <what changes>

## Phases
> Order by dependency, then risk (uncertain phases early). One reviewable diff
> each. Every phase must be independently verifiable and have a rollback point.

### Phase 1 — <title>
- Scope: <what this phase does>
- Files: <exact paths + the function/symbol or line range to touch where known — so
  the coder Reads the spot directly instead of searching for it>
- Done when: <acceptance criteria>
- Verify: <test/command/output that proves it — becomes the Evidence ledger>
- Rollback: <checkpoint / how to revert this phase cleanly>

### Phase 2 — <title>
- Scope:
- Files:
- Done when:
- Verify:
- Rollback:

### Phase 3 — <title>
- Scope:
- Files:
- Done when:
- Verify:
- Rollback:

## Open questions for the user
<Anything ambiguous that must be resolved before/during implementation.>
