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
> How the code is organized; where things live; important modules/boundaries.

## Coding conventions
> Style, naming, error-handling patterns, testing approach, things reviewers
> should enforce. Name the linter/formatter and the EXACT command to run them
> (e.g. `ruff check` / `npm run lint` / `gofmt -l`) and the test command — the
> coder runs these and the reviewer enforces them. Objective tooling beats prose.
> (Greenfield with no conventions yet? Start from `references/clean-code.md`.)

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
is project-wide at the repo root. All survive `/compact` and `/clear`.
