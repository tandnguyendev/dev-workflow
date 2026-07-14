---
name: init
description: Inspect the current project and draft conventions.md — its domain, tech stack, architecture, coding conventions, and security focus — so the feature workflow has accurate project context. Read-heavy; after user review, writes conventions.md and imports it from CLAUDE.md.
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
   (Domain / Tech stack / Architecture / Coding conventions / Verify commands /
   Simplicity contract / Domain-specific correctness rules / Security focus /
   Workflow files). Fill each section from what you observed; mark anything
   uncertain as an assumption.
   **The `verify` block is the one that carries teeth**: the pre-approval gate
   RUNS those commands and blocks the phase if they fail. Put the EXACT lint and
   test commands there, verified against the project's own config (the script in
   `package.json`, the `Makefile` target, the `pyproject.toml` tool section) —
   not a guess. Drop a line the project genuinely doesn't have rather than
   inventing one; leave the placeholder in place if you cannot determine it, and
   say so — a placeholder is never executed. Prefer a fast command: a phase waits
   on it.
   Copy the **Simplicity contract** section verbatim from the template in BOTH
   paths (observed project conventions and greenfield default) — it is a standing
   constraint, not a fallback baseline. Never rephrase, soften, or drop it.
3. **CHECKPOINT: show the draft to the user and ask them to confirm or correct
   it before writing.** Only write `conventions.md` after they approve.
4. Make `conventions.md` visible to ordinary chat, not just this plugin. The
   plugin's own skills and subagents Read it directly, but a plain Claude Code
   session only auto-loads `CLAUDE.md` and the files it `@`-imports — so without
   an import line, everything you wrote is invisible outside `/dev-workflow:*`.
   After writing `conventions.md`, ensure `CLAUDE.md` at the project root imports
   it on its own line:

   ```markdown
   @conventions.md
   ```

   - If `CLAUDE.md` exists and already imports it, leave the file alone.
   - If `CLAUDE.md` exists without the import, append the line (plus a one-line
     lead-in such as `Project domain and conventions:`) — do not touch anything
     else in the file.
   - If there is no `CLAUDE.md`, ask the user whether to create a minimal one
     holding just that import. If they decline, tell them plain chat sessions
     won't see `conventions.md` and move on.

   Then tell the user that a session already running must be restarted to pick
   the import up — `CLAUDE.md` is loaded once at session start, not re-read each
   turn. (Subagents Read the file live, so they always see the latest.)
5. After writing, point the user to **model routing** (optional, one line each) so
   they can tune cost/quality before running a feature:
   - **Per-agent (recommended):** copy the plugin's `templates/models.json` to
     `.dev-workflow/models.json` and map any of the seven agents
     (`domain-researcher`, `solution-architect`, `plan-reviewer`, `coder`,
     `code-reviewer`, `security-scan-fast`, `security-audit`) to a model — an alias
     (`opus`/`sonnet`/`haiku`/`fable`), a full model ID, or `inherit`. Omitted
     agents keep their default; prompts are untouched.
   - **All agents at once:** set `CLAUDE_CODE_SUBAGENT_MODEL=<model>` before launching.
   - **Replace an agent entirely:** add `.claude/agents/<name>.md` to shadow the
     plugin's (changes the prompt too, not just the model).
   Mention it and move on — do NOT create `models.json` yourself; init writes
   `conventions.md` and the `CLAUDE.md` import line, nothing else.

## Rules
- Be concrete and specific to THIS project — no generic filler.
- Do not modify source code. The only files you create/update are
  `conventions.md` and — for the import line alone — `CLAUDE.md`.
- The clean-code baseline (`references/clean-code.md`) applies to EVERY project,
  not just greenfield — the coder and reviewer enforce it always, subordinate to
  the project's own linter/conventions/style on a genuine conflict. So the Coding
  conventions section should capture what is SPECIFIC to this project (linter/test
  commands, real naming/error patterns); don't re-list the generic baseline.
- If the project is empty/greenfield, ask the user a few targeted questions about
  the intended domain and stack, then draft from their answers. For the Coding
  conventions section, if there's nothing project-specific yet, point to the
  baseline as the starting default to refine — do not leave it blank.
