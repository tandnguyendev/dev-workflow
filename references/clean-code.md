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
- Write for a human reading it cold, not for the machine: code that is correct but
  has to be decoded is a defect.
- Intent-revealing names in full words; consistent; no non-standard
  abbreviations; never one name for two things in a scope; booleans read as
  questions.
- One idea per line: name intermediate values instead of chaining; no nested
  ternaries, no arithmetic on booleans, no clever sort/reduce tricks.
- No hidden encodings: no string-glued keys, never `null` and `undefined` meaning
  two different things, no magic numbers, no empty `catch`.
- At most three parameters on a function you define (else one named object);
  injected constructors and framework-dictated signatures are exempt.
- Small, single-purpose functions; control flow nested at most two levels
  (prefer early returns); the entry function reads top to bottom as the story,
  details below it in private functions that name each step.
- Don't repeat yourself — but don't over-abstract before a real third use.
- Handle errors explicitly where they can actually occur; fail loudly on invalid
  untrusted input, never swallow silently.
- No dead code, commented-out blocks, or unused symbols.
- Keep public surfaces small; expose the minimum needed.
- **Write NO comments.** The code is the documentation. When you feel the urge to
  explain a line, fix the code — a clearer name, a smaller function, an early
  return, a named constant. Why a design choice was made belongs in the commit
  message, never in the file, where it goes stale. Tool directives
  (`eslint-disable`, `noqa`) are not comments. Enforced by
  `hooks/comment_guard.py`, which denies the edit outright: a comment-free or new
  file grants zero comment lines, and no added block may run past two lines — see
  its docstring for the escape hatches.
- Build only what the request states: no business rule, limit, cache, config or
  guard it did not ask for, and no handling for cases the types rule out.
- Let the formatter own whitespace/quotes/semicolons — don't hand-format.
- Test logic that can actually break (real branching, a bug's regression, store
  behaviour against the real store) — not every branch, not declarations, not
  wiring.
