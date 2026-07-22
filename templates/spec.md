# Spec: <feature name>

> Source of truth for WHAT and WHY. Fill this before planning. Keep it updated
> if the decision changes.

## 1. Problem / idea
<What are we building and why. The user-facing goal — written as the orchestrator
restated it back to the user, not as the raw one-line request.>

## 1b. Acceptance criteria
<Concrete, checkable statements of what must be true when this is done. Each one
should be something an artifact can be pointed at: "a request with no `page` param
returns the first 20 orders", not "pagination works". Stage 4's Evidence ledger
cites one artifact per criterion, and each phase's `Done when:` in plan.md comes
from here.>

## 1c. Assumptions & answers
<What the user was ASKED and answered (question -> answer), and what was ASSUMED
without asking. Assumptions stay visible so they can be vetoed later — an
assumption nobody can see is just a guess.>

## 2. Domain research summary
<Key findings from the domain-researcher: relevant patterns, pitfalls, links.>

## 2b. What already exists here
<From the domain-researcher's codebase survey + project-map.md: the closest
existing implementations (path:line), the building blocks to reuse, the extension
point this hooks into, and what would be DUPLICATED if built from scratch. "Nothing
yet" is a valid answer — write it explicitly rather than leaving this blank.>

## 3. Solution options considered
| Option | Approach | Complexity | Performance | Security risk | Effort |
|--------|----------|------------|-------------|---------------|--------|
| A      |          |            |             |               |        |
| B      |          |            |             |               |        |
| C      |          |            |             |               |        |

## 4. Chosen solution + rationale
<Which option, and WHY it was chosen over the others. Note the tradeoffs
accepted.>

## 5. Non-goals / out of scope
<Explicitly what we are NOT doing in this feature.>

## 6. Project constraints that apply (from conventions.md)
<Relevant domain-specific correctness rules and conventions this feature must
respect.>
