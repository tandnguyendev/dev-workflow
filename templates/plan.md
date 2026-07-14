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
>
> Write each phase for the coder who will BUILD it, not for the reviewer who
> shaped it. State the constraint; never record where it came from ("plan review
> flagged...", "as confirmed above") — that is provenance, and it is noise to the
> only reader who matters. What DOES earn its length: a trap the coder would
> otherwise walk into (a falsy-looking value that is truthy, a field already
> scaled, an index that won't build in prod, a guardrail that doesn't guard) and
> anything that REMOVES work (a middleware that already covers this).

### Phase 1 — <title>
- Scope: <what this phase does>
- Files: <every path this phase may touch, INCLUDING new files and test/spec files —
  real paths only (`src/foo.service.spec.ts`, never "specs" or "tests"). The
  pre-approval gate flags any changed file not listed here, so an unlisted spec file
  reads as scope creep. Anchor to the SYMBOL to touch (`updateParams`,
  `CONFIG_PROJECTION`), not a line range — earlier phases shift line numbers, and a
  stale range sends the coder to the wrong place confident it is the right one.>
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
