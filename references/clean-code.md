# Clean-code baseline

A minimal, language-agnostic baseline used ONLY as a tie-breaker when a project
has no stated convention (e.g. a greenfield repo). It is deliberately generic.

## Precedence (highest wins)
1. The project's linter/formatter config — objective and enforced.
2. `conventions.md` — project-specific rules.
3. The surrounding code's existing style.
4. This baseline — only when 1–3 are silent.

Never apply this baseline in a way that fights an existing codebase's style.

## Principles
- Clarity over cleverness: obvious code beats compact code; optimize for the
  next reader.
- Intent-revealing names; consistent; no non-standard abbreviations.
- Small, single-purpose functions; avoid deep nesting (prefer early returns).
- Don't repeat yourself — but don't over-abstract before a real second use.
- Handle errors explicitly; fail loudly on invalid input, never swallow silently.
- No dead code, commented-out blocks, or unused symbols.
- Keep public surfaces small; expose the minimum needed.
- Comments explain WHY, not WHAT; keep them accurate or delete them.
- Let the formatter own whitespace/quotes/semicolons — don't hand-format.
- Tests cover the new behavior plus at least one edge/failure case.
