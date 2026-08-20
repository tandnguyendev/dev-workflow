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
- **Default to NO comment.** The code is the documentation. When you feel the urge
  to explain a line, the fix is almost always in the code — a clearer name, a
  smaller function, an early return, a named constant instead of a literal — and
  reaching for the comment instead leaves both the confusing code and a line that
  will go stale. Write the comment only after the code-level fix genuinely isn't
  available.
- A comment is an EXCEPTION that has to earn its line, and only three things do:
  a constraint the code cannot state (an external contract, a protocol quirk, a
  hardware or vendor behaviour), a reason the obvious implementation is wrong
  *here*, or a caveat with real consequences for whoever edits next. A pointer to
  the issue or spec behind a workaround counts as the second. If you have to think
  about whether it qualifies, it does not.
- Never narrate the next line, explain where a change came from, or argue that it
  is correct: that is talk for the reviewer, and it is noise the moment the PR
  merges. Never docstring a file whose functions have none. Keep the few comments
  that exist accurate, or delete them.
- Enforced by `hooks/comment_guard.py`, which denies the edit outright: a
  comment-free file grants ONE comment line, and anything beyond that has to be
  earned from the file's own density — see its docstring for the exact shapes and
  the escape hatches.
- Let the formatter own whitespace/quotes/semicolons — don't hand-format.
- Tests cover the new behavior plus at least one edge/failure case.
