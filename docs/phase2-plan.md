# Phase 2 implementation plan

Baseline: `decf38e6a3ce1a636b799b660dea545e01d469b3`. The local branch and GitHub
`main` were both verified at that checkpoint before implementation. Phase 1 was
clean. No new commits or pushes are authorized automatically.

## Milestones and release gates

| Milestone | Deliverable | Verification / release gate | Current status |
| --- | --- | --- | --- |
| 1. Contracts and persistence | Account/transaction/case/assessment/evidence contracts, scoped repositories, preservation migration | Contract/security tests, actual PostgreSQL upgrade preservation, schema drift, migration review | Activated and verified at revision 0002 |
| 2. Detection | Configurable historical windows; amount, frequency, timing, contextual indicators; deterministic scoring | Boundary, missing-history, currency, time, causality and contribution tests | Implemented and verified in isolated synthetic sandbox; active rollout pending |
| 3. Relationships and evidence | Directed transaction graph, supported patterns, provenance-backed findings | Chain/cycle/fan-out fixtures; traceable sources and bounded traversal | Implemented and verified in isolated synthetic sandbox; active rollout pending |
| 4. Investigation workflow | Case transitions, assignments, notes, history, structured reports | Authorized transitions and factual report/source validation | Implemented and verified in isolated synthetic sandbox; active rollout pending |
| 5. Identity and policy | Authentication, expiration/logout, RBAC, OPA and approval gate | Actual allow/deny policy evaluation; failure/timeout denies before execution | Not implemented |
| 6. Investigation agents | Bounded structured workers using approved tools, timeouts and retry limits | No executor call on denied/unverifiable access; evidence and approval validation | Not implemented |
| 7. Frontend integration | Authenticated transaction/risk/case/report views and accessible account graph | Real authenticated API integration, browser workflows and build | Not started; synthetic UI integration was explicitly included in milestones 2–4 |
| 8. Final verification | Full regression/security tests, bounded performance measurements, reproducible synthetic demo and accurate docs | Explicit PASS/FAIL/BLOCKED/NOT IMPLEMENTED acceptance report | Not started |

Authentication and policy must precede real-data mutation APIs or agent execution.
The user explicitly authorized integrated synthetic testing in milestones 2–4.
Their write API is disabled by default and can only start against a separate local
`fraudsentinel_sandbox_*` database (or an in-memory unit fixture); it refuses the
active `fraudsentinel` database. It is not authentication. Review migration 0003
before active rollout, and approve any Git checkpoint separately. No work on
milestones 5–8 is authorized by this implementation.

See [milestones 2–4](phase2-milestones234.md),
[review/results](phase2-review-results.md) and [reference comparison](reference-review.md).

## Decisions established in Milestone 1

- Extend existing tables rather than introduce a second transaction ledger.
- Allow an unassigned transaction only with an access owner. Keep the existing
  primary-case link and transaction/case evidence foreign key. A transaction can
  have one primary investigation case in this milestone; reassignment is refused.
- Account ownership means application dataset access, not legal ownership of a
  bank account. No personal identity/payment credentials are stored.
- Do not infer account numbers from legacy customer or beneficiary identifiers.
  Missing mapping, observation time, location, and device context stay unknown.
- Preserve existing risk storage in the range 0-1; expose Phase 2 contract scores
  as exact decimals in the range 0-100. No historical score is overwritten.
- New factors identify supporting transaction IDs; new evidence includes typed
  provenance and begins unverified. Observations, indicators, and interpretations
  are distinct. Human verification is a later authorized workflow.
- Prefer ordinary Python/SQLAlchemy/Pydantic and deterministic algorithms. No
  dependency upgrades, paid AI service, graph database, queue, or orchestrator is
  needed for Milestone 1.

See [Milestone 1 implementation and review](phase2-milestone1.md). All future
detector outputs remain decision support, never proof of fraud.
