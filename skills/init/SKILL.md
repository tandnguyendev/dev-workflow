---
name: init
description: Inspect the current project and draft conventions.md — its domain, tech stack, architecture, coding conventions, and security focus — so the feature workflow has accurate project context. Read-heavy; writes only conventions.md after user review.
---

# Init — learn this project, draft conventions.md

Your job is to produce a `conventions.md` at the project root that captures this
project's domain and engineering context, for the `/dev-workflow:feature`
workflow to rely on.

## Steps
1. Inspect the project (read-only first):
   - Detect the tech stack from manifests (`package.json`, `go.mod`,
     `pyproject.toml`/`requirements.txt`, `Cargo.toml`, `pom.xml`, `Gemfile`,
     etc.), framework imports, and the directory layout.
   - Infer the DOMAIN from names, models/entities, routes, and any existing docs
     (README, docs/). Examples: fintech, healthcare, e-commerce, dev tooling.
   - Note existing coding conventions and architecture/module boundaries. In
     particular, detect the linter/formatter and record the EXACT command to run
     them (e.g. `ruff check`, `npm run lint`, `gofmt -l`, `cargo fmt`) plus the
     test command, and any naming/error-handling patterns the code already
     follows. These are what the coder runs and the reviewer enforces.
   - If a `CLAUDE.md` already exists, read it and reuse its content — do not
     duplicate or overwrite it; complement it.
2. Draft `conventions.md` using the section structure from the plugin template
   (Domain / Tech stack / Architecture / Coding conventions / Simplicity contract
   / Domain-specific correctness rules / Security focus / Workflow files). Fill
   each section from what you observed; mark anything uncertain as an assumption.
   Copy the **Simplicity contract** section verbatim from the template in BOTH
   paths (observed project conventions and greenfield default) — it is a standing
   constraint, not a fallback baseline. Never rephrase, soften, or drop it.
3. **CHECKPOINT: show the draft to the user and ask them to confirm or correct
   it before writing.** Only write `conventions.md` after they approve.

## Rules
- Be concrete and specific to THIS project — no generic filler.
- Do not modify source code. The only file you create/update is `conventions.md`.
- The clean-code baseline (`references/clean-code.md`) applies to EVERY project,
  not just greenfield — the coder and reviewer enforce it always, subordinate to
  the project's own linter/conventions/style on a genuine conflict. So the Coding
  conventions section should capture what is SPECIFIC to this project (linter/test
  commands, real naming/error patterns); don't re-list the generic baseline.
- If the project is empty/greenfield, ask the user a few targeted questions about
  the intended domain and stack, then draft from their answers. For the Coding
  conventions section, if there's nothing project-specific yet, point to the
  baseline as the starting default to refine — do not leave it blank.
