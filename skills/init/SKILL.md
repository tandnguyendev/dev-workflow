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
   - Note existing coding conventions (lint/format config, test setup, error
     patterns) and architecture/module boundaries.
   - If a `CLAUDE.md` already exists, read it and reuse its content — do not
     duplicate or overwrite it; complement it.
2. Draft `conventions.md` using the section structure from the plugin template
   (Domain / Tech stack / Architecture / Coding conventions / Domain-specific
   correctness rules / Security focus / Workflow files). Fill each section from
   what you observed; mark anything uncertain as an assumption.
3. **CHECKPOINT: show the draft to the user and ask them to confirm or correct
   it before writing.** Only write `conventions.md` after they approve.

## Rules
- Be concrete and specific to THIS project — no generic filler.
- Do not modify source code. The only file you create/update is `conventions.md`.
- If the project is empty/greenfield, ask the user a few targeted questions about
  the intended domain and stack, then draft from their answers.
