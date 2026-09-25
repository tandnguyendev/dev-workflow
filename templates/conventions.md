# Project conventions

*Keep this file lean — every research/coding/review subagent re-reads it in full,
every phase, so each line is paid for many times over. Aim for under ~50 lines;
push long detail into dedicated files (a `references/` doc, an ADR) that agents
open only when a task needs them. (This note stays; the guidance blockquotes go.)*

> This is the domain + engineering context for THIS project. It is the source of
> truth the workflow reads before researching, coding, and reviewing.
>
> Fill it in one of two ways:
> - Run `/dev-workflow:init` — it inspects the project (stack, structure, existing
>   patterns) and drafts this file for you to review.
> - Or leave it; each feature will infer the relevant domain from your feature
>   description and the surrounding code.
>
> Delete the guidance blockquotes once filled.

## Domain
> What kind of software is this (e.g. fintech payments, healthcare records,
> e-commerce, dev tooling, gaming)? What domain rules/regulations apply?

## Tech stack
> Languages, frameworks, datastores, key libraries, runtime/target.

## Architecture & structure
> The shape of the system in a few lines: the layers/services and how they talk.
> Keep it to what every agent needs on every phase. The detailed map — module
> table, existing features, shared building blocks, extension points — lives in
> `project-map.md`, which is read only when a task needs it; point there instead
> of inlining it here.

## Coding conventions
> Style, naming, error-handling patterns, testing approach, things reviewers
> should enforce. Name the linter/formatter and the EXACT command to run them
> (e.g. `ruff check` / `npm run lint` / `gofmt -l`) and the test command — the
> coder runs these and the reviewer enforces them. Objective tooling beats prose.
> (Greenfield with no conventions yet? Start from `references/clean-code.md`.)

## Testing
> The EXACT test command, and the harness for proving store/external behaviour for
> real (an in-memory server, a container, a fixture DB) — name it even if nothing
> uses it yet, because an agent that cannot see it will mock instead. Then how a
> subject is built in a test (a testing module, a named factory — never positional
> `as any` blanks). Anything else this project wants enforced.

## Testing contract (always applies)
*This section stays verbatim — it is not project-specific and is not a fallback.*
- Test at the boundary where the risk lives. Correctness that depends on the store
  or an external system — atomicity, uniqueness, indexes, transactions, real filter
  semantics — is proven against the real thing, not a mock of it. A fake that
  stands in for the risky call proves nothing about it and reports it as covered.
  Faking a collaborator to INJECT an otherwise unreachable failure is fine.
- Pure logic gets a plain unit test: no DI, no mocks.
- Nothing else gets a test. A behaviour that is a declaration — a validator
  annotation, a schema field, a config constant, a type — is already enforced by
  the type-checker, the linter or the framework; a test restating it cannot fail.
- Few tests: extend the module's existing spec rather than add a file; never a
  test per defensive branch, a wiring/DI test, or a test of generated code.
  Probe/smoke scripts are scratch — run them, paste the output, don't commit them.
- Build the subject by NAME, never positionally out of empty placeholders.
  (The last two shapes are enforced by a hook. Turn it off for this project with
  `.dev-workflow/test-guard.json` -> `{"enabled": false}`.)

## Simplicity contract (always applies)
*This section stays verbatim — it is not project-specific and is not a
fallback. It applies on top of the conventions above, in every project.*
- Build only what the task requires — no speculative options, config, or
  abstraction for imagined future needs.
- No new abstraction until a real third use; prefer a function over a class,
  a literal over a config system, straight-line code over a framework.
- Match existing patterns; don't add libraries or layers the codebase doesn't
  already use.
- No business rule the request did not state — no extra limit, quota, status,
  permission, cache or abuse guard. Suggest it; don't build it.
- Handle only errors that can actually occur here; validate only untrusted input,
  at the boundary. No checks for cases the types or callers rule out.
- Write NO comments. When a line needs explaining, fix the code (a clearer name, a
  smaller function, a named constant); the reason for a design choice goes in the
  commit message, not the file.
  (Enforced by a hook, which denies the edit: a comment-free or new file grants
  zero comment lines, a commented file only its own ratio, and no added block may
  run past two lines. Tool directives like `eslint-disable` are exempt. Loosen it
  with `.dev-workflow/comment-guard.json` -> `{"density": {"floor": 1}}`, exempt a
  phrase with `{"allow": ["<regex>"]}`, or turn it off with `{"enabled": false}`.)
- Before adding anything beyond the literal request, STOP and ask — default to less.

## Readability contract (always applies)
*This section stays verbatim — it is not project-specific and is not a fallback.*
- Code is written for a teammate reading it cold, without the spec or comments.
  Correct code that has to be decoded is a defect.
- Names in full words that say what the value is; never one name for two things;
  booleans read as questions.
- One idea per line: named intermediates over dense chains; no nested ternaries,
  no arithmetic on booleans, no clever tricks.
- No hidden encodings: no string-glued keys, never `null` and `undefined` meaning
  two different things, no magic numbers, no empty `catch`.
- At most three parameters on a function you define (injected constructors and
  framework-dictated signatures are exempt); control flow nested at most two
  levels; the entry function reads top to bottom, details below it in private
  functions that name each step.

## Domain-specific correctness rules
> Invariants that MUST hold for this domain. Examples by domain:
> - Fintech: money as integer minor units / decimal (never float); idempotency
>   keys on money writes; audit logging; atomic balance updates.
> - Healthcare: PHI handling, access control, audit trails.
> - E-commerce: inventory consistency, price/tax rounding rules.
> Replace with YOUR project's rules.

## Security focus for this project
> Beyond the generic checklist (injection, auth bypass, secrets, insecure crypto,
> unsafe deserialization, SSRF), what are the high-value risks specific to this
> domain? These are what the security reviewers prioritize.

## Workflow files
Per-feature `spec.md` / `plan.md` / `phase-log.md` live under
`.dev-workflow/features/<slug>/` (active slug in `.dev-workflow/active`); this file
and `project-map.md` (what exists and where) are project-wide at the repo root. All
survive `/compact` and `/clear`.
