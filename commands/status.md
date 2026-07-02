---
description: Show the current dev-workflow status — active feature, phase, approval state, and gate lock — from the working-doc files.
---

Report the current state of the dev-workflow feature in progress. Do this by
reading the project's working docs (do NOT rely on conversation memory):

1. Resolve the active feature: read `.dev-workflow/active` for the slug, then
   read `spec.md`, `plan.md`, `phase-log.md` from
   `.dev-workflow/features/<slug>/`. Fall back to the project root for the legacy
   single-feature layout. Read `.approval-gate` at the repo root if present.
2. Print a concise status:
   - Active feature (from the spec/phase-log title).
   - The chosen solution in one line (from `spec.md`), if decided.
   - Phases: how many are USER APPROVED vs total, and which phase is current /
     next (the first not-yet-approved phase in `phase-log.md`).
   - Any outstanding review findings recorded for the current phase.
   - Approval gate state (LOCKED / UNLOCKED / not set).
   - The single most useful next action.
3. If none of these files exist, say there is no active dev-workflow feature and
   suggest running `/dev-workflow:init` and `/dev-workflow:feature`.

Keep it short — this is a status readout, not a full report. Do not modify any
files.
