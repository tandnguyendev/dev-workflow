# 🛠️ dev-workflow

**A Claude Code plugin for spec-driven development — research, plan, then build each feature in reviewed phases, with AI code review every phase, a security scan on every phase that touches a sensitive surface, and a final cross-phase security audit. Domain-agnostic, review-gated, safe by default.**

Every feature runs the same disciplined gauntlet — and *you* are the final boss at every gate:

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/tandnguyendev/dev-workflow/main/assets/flow-dark.svg">
    <img alt="The feature gauntlet: detect conventions → research → solution options panel → phased plan → per-phase loop (build → AI code review, plus a security scan when the phase touches a sensitive surface → you approve) → final cross-phase audit → ship it" src="https://raw.githubusercontent.com/tandnguyendev/dev-workflow/main/assets/flow-light.svg" width="460">
  </picture>
</p>

> Pair programming, except your pair is six robots who *actually read the spec* — and you still hold the almighty **“nope.”**

The domain isn't hardcoded — it's read from your `conventions.md` (via `/dev-workflow:init`) or inferred per feature from the code.

## Install

```shell
/plugin marketplace add tandnguyendev/dev-workflow
/plugin install dev-workflow@dev-workflow-marketplace
```

> Update later (two steps — refresh the catalog, then pull the new code):
> ```shell
> /plugin marketplace update dev-workflow-marketplace
> /plugin update dev-workflow@dev-workflow-marketplace
> ```
> See the [changelog](CHANGELOG.md) for what's new.

## Quick start

```shell
/dev-workflow:init                       # (optional) learn the repo → conventions.md
/dev-workflow:feature add pagination to the orders endpoint
/dev-workflow:status                     # where am I?  (also auto-injected each session)
```

Working docs scaffold automatically under `.dev-workflow/features/<slug>/`; multiple features can run at once (`.dev-workflow/active` names the current one).

## What's inside

**Commands & skills**

| Command | Purpose |
|---------|---------|
| `/dev-workflow:init` | Inspect the project, draft `conventions.md`, import it from `CLAUDE.md` |
| `/dev-workflow:feature` | Drive the whole feature workflow (orchestrator) |
| `/dev-workflow:status` | Readout of the active feature / phase / gate |
| `/dev-workflow:checkpoints` | List auto-snapshots |
| `/dev-workflow:rollback` | Restore to a checkpoint (safe, reversible) |

**Subagents** — model routing is tiered to save tokens: cheap models scout and review, Opus is reserved for writing code. These are **defaults you can override per agent** (see below).

| Agent | Default model | Role |
|-------|---------------|------|
| `domain-researcher` | Haiku 4.5 | Domain/stack research (read-only + web) |
| `solution-architect` | Haiku 4.5 | One solution option per angle (panel) |
| `plan-reviewer` | inherit | Adversarial plan review before coding |
| `coder` | Opus 4.8 | Implement one phase |
| `code-reviewer` | Sonnet 5 | Logic/quality review |
| `security-scan-fast` | Fable 5 | Fast per-phase security scan |
| `security-audit` | Sonnet 5 | Deep final cross-phase audit |

**Pick your own models** — three ways, no plugin edits (which get overwritten on update):

1. **Per agent** (recommended) — drop a `.dev-workflow/models.json` mapping agent → model; the orchestrator applies it at spawn time. Omitted agents keep their default. Copy the plugin's `templates/models.json` to start:
   ```json
   { "coder": "sonnet", "security-audit": "opus" }
   ```
   Values take aliases (`opus`/`sonnet`/`haiku`/`fable`), full model IDs, or `inherit` (use your session's model). This keeps each agent's tuned prompt — only the model changes. (`.dev-workflow/` is gitignored, so this is per-developer; un-ignore the file if you want to commit a team-wide policy.)
2. **All agents at once** — set `CLAUDE_CODE_SUBAGENT_MODEL=<model>` before launching; every subagent uses it. Blunt but zero-config.
3. **Fully replace an agent** — put a `.claude/agents/<name>.md` in your project (it shadows the plugin's). Use this to change the *prompt* too, not just the model — you take over its whole definition.

## Safety & reliability

Four hooks make the workflow *trustworthy*, not just well-behaved. All fail open — a hook that errors never blocks your work.

| | Gives you |
|---|---|
| 🔒 **Approval gate** | A `LOCKED` gate only *you* can flip: while locked, Claude cannot edit source or run Bash |
| 💾 **Checkpoints + rollback** | Auto git snapshots before every edit; safe reversible restore |
| 🧾 **Evidence gate** | "Done" must cite proof — an empty ledger is refused |
| ♻️ **Context re-injection** | Workflow state survives `/compact` |

Three of the four stay silent when no workflow is active. **Checkpoints are the exception**: in any git repo, the checkpoint hook snapshots before every `Edit`/`Write`/`MultiEdit`/`Bash` whether or not a dev-workflow feature is running. It writes only to its own shadow refs — never your index, HEAD, branch, or worktree — but it is not side-effect-free, and the refs are not pruned automatically (see the v1 limits below).

<details>
<summary><b>🔒 Approval gate</b> — how it works</summary>

<br>A `PreToolUse` hook (`hooks/gate.py`) blocks `Edit`/`Write`/`MultiEdit` on source code **and all of `Bash`** while a `.approval-gate` file at your project root says `LOCKED`. Opt-in — does nothing until the file exists.

- Working docs (`spec.md`, `plan.md`, `phase-log.md`, `conventions.md`, anything under `.dev-workflow/`) stay editable while locked, so the log can still be maintained.
- **Bash is denied outright while locked** — not filtered. `coder` has Bash, and a denylist of write constructs cannot be closed: `sed -i`, here-docs, `patch`, `git checkout` and any interpreter with `-c` all write files. Rather than pretend to catch them, the gate runs none of them. This costs nothing, because `LOCKED` means *"stop, the phase is waiting on you"* — the coder runs its tests and lint while unlocked.
- **Only you can unlock**, from your own shell — Claude can't. The edit tools can't write `.approval-gate`, and Bash referring to it is refused (quoting like `.approval-gat"e"` is caught too — though the Bash filename check is best-effort, not a hard barrier; what makes the lock hold is that **no** Bash runs while locked). A rollback can't flip it either: gate state is preserved and never snapshotted.

```shell
! echo LOCKED > .approval-gate      # activate + lock
! echo UNLOCKED > .approval-gate    # after approving a phase
```

The `!` prefix runs in *your* shell, so it isn't a Claude tool call the hook can intercept.
</details>

<details>
<summary><b>💾 Checkpoints & rollback</b> — how it works</summary>

<br>In a git repo, a `PreToolUse` hook (`hooks/checkpoint.py`) snapshots the working tree before every mutating tool call to a shadow ref `refs/dev-workflow/checkpoints/<ts>` — via git plumbing on a temp index, so it **never touches your index / HEAD / branch / worktree**. Fail-open, with a timeout.

- `/dev-workflow:checkpoints` — list snapshots (newest first).
- `/dev-workflow:rollback [ref]` — restore to a checkpoint (default: latest). It first saves current state as a reversible `pre-rollback` checkpoint (`undo` reverses it); never moves your branch, never hard-deletes.

Rollback restores tracked *content*; files created since are left in place (they show in `git status`).

**v1 limits:** git only · no auto-pruning — refs are local (not pushed); prune with
`git for-each-ref --format='delete %(refname)' refs/dev-workflow | git update-ref --stdin` · snapshots respect `.gitignore`, so keep secrets ignored.
</details>

<details>
<summary><b>🧾 Evidence gate</b> — how it works</summary>

<br>Completion checkpoints ask for *cited proof*. Each phase's `phase-log.md` has an `- Evidence:` ledger to fill with concrete artifacts — test/command output, `file:line` references, the cases verified — one per acceptance criterion. Review subagents back every verdict with what they actually checked.

A `Stop` hook (`hooks/evidence_guard.py`) enforces it: end a turn with the current phase marked `[x] code-reviewed` but its Evidence ledger empty, and it blocks and asks for proof — and it keeps blocking if you stop again without filling it. Fail-open, silent unless a phase-log is active.

**What the hook can and cannot check.** It verifies the ledger *exists and is not a placeholder or a scrap* — it cannot judge whether what you wrote is true. "Everything looks fine" is long enough to pass the hook; it is the `coder` and reviewer prompts, and your own eyes at the approval gate, that make the evidence real. The hook raises the floor; it is not a proof checker.

To stop it from hard-locking a turn, it gives up after 3 consecutive blocks — and says so loudly in the message, so a phase never slips through an empty ledger *silently*.
</details>

<details>
<summary><b>♻️ Context re-injection</b> — how it works</summary>

<br>A `SessionStart` hook (`hooks/status.py`) re-surfaces the active feature, phase progress, and gate state at every session start — **including after `/compact` or auto-compaction** (it fires with `source: "compact"` and adds a "context was just compacted — re-read the files" reminder). This keeps the file-based source of truth (`spec.md` / `plan.md` / `phase-log.md`) from being lost to context rot.
</details>

## Under the hood

- **Files are the source of truth** — `spec.md` / `plan.md` / `phase-log.md` survive `/compact` and `/clear`. Re-read them, don't trust conversation memory.
- **You review AFTER the AI** reviewers at every phase; nothing advances unapproved.
- **Token triage** — the `feature` skill sizes each job (trivial / standard / complex) and scales the machinery: trivial skips research and the option panel; standard runs a 2-architect panel; complex runs a 3-architect panel and a full final audit. **The tier never scales security coverage down**: `code-reviewer` runs on every phase in every tier, and `security-scan-fast` is gated on the phase's *surface*, not the tier — a new endpoint in a trivial feature gets scanned; a copy tweak in a complex one does not.
- **Token discipline across phases** — the fresh-context re-reads that make multi-phase workflows expensive are attacked directly: **one `coder` is reused across a feature's phases** (continued, not respawned) so codebase intake is paid once, not per phase; the orchestrator hands coder and reviewers the **exact files/paths** from `plan.md` so they Read the spot instead of Grep-walking to find it; and `conventions.md` is kept lean because every subagent re-reads it in full. Reviewers stay freshly spawned per phase on purpose — objective fresh eyes are the point. (An MCP can *store* shared context but can't avoid this cost: each subagent still pulls it into its own window.)
- **Optional: semantic code retrieval** — on large codebases, a symbol-level retrieval MCP (e.g. [Serena](https://github.com/oraios/serena)) lets agents read *symbols* rather than whole files, shrinking read size. It's an opt-in per-project MCP, not bundled — add it to your own `.mcp.json` if the codebase is big enough to warrant it.
- **Domain context** ships per-project via `conventions.md` (plugins can't ship a project `CLAUDE.md`). The plugin's skills and subagents Read it directly; `init` also adds an `@conventions.md` import to your `CLAUDE.md` so plain chat sessions — not just `/dev-workflow:*` — carry the same project context. A minimal `references/clean-code.md` baseline applies in **every** project, greenfield or not — but it is strictly subordinate: on a genuine conflict, precedence is linter/formatter > `conventions.md` > surrounding style > baseline.

## Requirements

- **`python3` on PATH** — the hooks are invoked as `python3`. macOS and most Linux distros ship no binary named `python` at all, so that is the only name that reliably resolves. On Windows, the Microsoft Store build provides `python3`; if you installed from python.org you may only have `python` and `py`, in which case add a `python3` shim on PATH.
  Check with `python3 --version`. If it fails, the hooks fail to launch — and because hooks fail open, you get **no approval gate, no checkpoints and no evidence gate, silently**.
- **Git** for checkpoints/rollback (the other features work without it).
- Add **`.dev-workflow/`** to your project `.gitignore`.
