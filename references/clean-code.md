# Clean-code baseline

A minimal, language-agnostic engineering floor that applies to EVERY project,
not just greenfield ones. The principles below are universal hygiene — a project
inherits them by default. Where a specific principle genuinely conflicts with the
project's own linter/conventions/established style, the project wins (see
Precedence); absent such a conflict, the principle always holds.

## Precedence (highest wins, on genuine conflict)
1. The project's linter/formatter config — objective and enforced.
2. `conventions.md` — project-specific rules.
3. The surrounding code's existing style.
4. This baseline.

The precedence resolves conflicts; it does not make the baseline greenfield-only.
Never apply a style-sensitive principle in a way that fights an existing
codebase's established style.

## Principles
- Clarity over cleverness: obvious code beats compact code; optimize for the
  next reader.
- Intent-revealing names; consistent; no non-standard abbreviations.
- Small, single-purpose functions; avoid deep nesting (prefer early returns).
  *(Style-sensitive: yields to the project's established style.)*
- Don't repeat yourself — but don't over-abstract before a real third use.
- Handle errors explicitly; fail loudly on invalid input, never swallow silently.
- No dead code, commented-out blocks, or unused symbols.
- Keep public surfaces small; expose the minimum needed.
- Comments explain WHY, not WHAT; keep them accurate or delete them.
- Let the formatter own whitespace/quotes/semicolons — don't hand-format.
- Tests cover the new behavior plus at least one edge/failure case.
