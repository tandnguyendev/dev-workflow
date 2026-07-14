# Phase log: <feature name>

> Append-only record of each phase. Survives /compact and /clear — re-read this
> instead of trusting conversation memory.
>
> **This file is machine-parsed.** Keep the `## Phase N — ...` headings and the
> `- Status:` / `- Evidence:` lines in the shape below: the hooks find a phase by
> its `## Phase`/`## Final review` heading, arm the evidence gate on the literal
> `[x] code-reviewed` (or `[x] full code review` in the Final review section), and
> read progress from the literal `[x] USER APPROVED`. Reworded into prose, the
> safety hooks go silent — without saying so.
> `[x] USER APPROVED` means the USER approved. Claude never ticks it unprompted.

## Phase 1 — <title>
- Status: [ ] coded  [ ] code-reviewed  [ ] security-scanned  [ ] USER APPROVED
- Changed: <files + key decisions>
- Code review result: <summary of findings + how resolved>
- Security scan result: <summary>
- Evidence: <cited PROOF this phase works — concrete artifacts only, no "looks
  fine". e.g. `pytest -q` -> 12 passed; snapshot ref created + `git rev-parse
  HEAD` unchanged; hooks/x.py:42 handles the empty case. Required before you ask
  the user to approve; each acceptance criterion should map to an artifact.>
- User notes: <what the user said / requested changes>

## Phase 2 — <title>
- Status: [ ] coded  [ ] code-reviewed  [ ] security-scanned  [ ] USER APPROVED
- Changed:
- Code review result:
- Security scan result:
- Evidence:
- User notes:

---
<!-- DELETE this whole section if Stage 5 is skipped (trivial + single-phase): an
     unticked section is reported as the current one forever. -->
## Final review (all phases)
- Status: [ ] full code review  [ ] security-audit  [ ] USER APPROVED
- Cross-phase findings:
- Resolution:
- Evidence: <cited proof for the whole feature — test suite result, validation
  command output, the key invariants checked end-to-end.>
