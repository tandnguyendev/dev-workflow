# Domain: Finance / Fintech

This project handles money and transactions. Every coding decision must follow
the conventions below — do NOT re-research them each time.

## Money handling (mandatory)
- NEVER use `float`/`double` for monetary amounts. Use integer minor units
  (e.g. cents) as `bigint`/`int64`, or a fixed-precision `decimal` type.
- Every rounding operation must declare its mode explicitly (half-even /
  half-up) and be documented; never rely on implicit language rounding.
- A currency must always accompany an amount (never assume a default).

## Transactions (mandatory)
- Every money-writing operation must carry an **idempotency key** to prevent
  double-submit / duplicate retries.
- Balance writes must run inside a transaction with proper locking; no
  read-modify-write without a lock or version check.
- Every balance change must produce an **audit log**: who, when, before/after,
  and the transaction reference.

## What "security review" means in this domain
When reviewing security, prioritize finance-specific bugs, not just a generic
checklist:
- **Concurrent-debit race conditions** / double-spending (missing locks,
  non-atomic balance checks).
- **Rounding errors** that accumulate or can be exploited for gain.
- **Per-account authorization** (IDOR: acting on another user's account).
- **Skipped idempotency** leading to duplicate charges/transfers.
- Leakage of PII / card data; secrets or card numbers written to logs.
- Injection, auth bypass, insecure crypto, unsafe deserialization (generic
  checklist — still check these).

## Workflow (source of truth lives in files, NOT in the conversation)
- `spec.md` — the idea, the chosen solution, and the tradeoffs.
- `plan.md` — the phased plan and the files to change.
- `phase-log.md` — per phase: what was done, code + security review results,
  and whether the user has approved it.
When context is compacted/cleared, RE-READ these files instead of relying on
conversation memory.

## Checkpoints
After coding each phase: run the code review + security review, summarize for
the user, then STOP and wait for the user's approval. Do NOT proceed to the
next phase before it has been approved.
