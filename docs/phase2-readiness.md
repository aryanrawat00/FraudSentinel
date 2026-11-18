# Phase 2 readiness - 17 November 2026

This records the Phase 1 baseline before Phase 2 implementation. See the
[current plan](phase2-plan.md) and [Milestone 1 review](phase2-milestone1.md) for
the activated Milestone 1 baseline. Current milestones 2–4 implementation and
verification are recorded in [the operating guide](phase2-milestones234.md) and
[final review](phase2-review-results.md); their active migration gate is still pending.

## 1. Decision

The implemented Phase 1 foundation is ready for controlled local Phase 2
development. It is not ready for production financial data or exposed agent
execution. The local PostgreSQL/API/frontend path is working, with 30 permitted
backend tests and 10 browser tests passing. Docker execution and the existing
downgrade test remain unverified in this stabilization pass.

## 2. What Phase 1 implements

- React/TypeScript/Vite workspace with a real API client, service status, scoped
  counts, a transaction preview, loading/empty/error states, and retry.
- FastAPI application factory, lifecycle management, liveness/readiness,
  development OpenAPI documentation, restricted CORS, and safe database errors.
- PostgreSQL/SQLAlchemy tables for users, cases, transactions, risk assessments,
  evidence, agent requests, policy decisions, and audit events; Alembic migration.
- Explicit synthetic seed/reset commands and a fixed local demo investigator.
- Locked dependencies, local setup helpers, Dockerfiles, Compose, and Nginx config.

## 3. Fully working and verified

Real React-to-Vite-proxy-to-FastAPI-to-PostgreSQL reads work. The demo shows six
existing synthetic transfers, one case, and zero assessments. Liveness, docs,
readiness, the frontend, and proxied data returned HTTP 200 at six sample points
over 76.2 seconds. Runtime response validation prevents invalid data from
crashing rendering. The INR 95,000 timestamp displays as 02:14 IST, and currency
formatting follows the record instead of assuming INR.

Configuration failures no longer print input fragments; invalid ports and blank
production passwords are rejected. Demo access requires the stored investigator
role. Case scoping, cross-case evidence constraints, sanitized database errors,
and unavailable agent execution routes are covered by tests. PostgreSQL row
fingerprints and the `.env` fingerprint remained unchanged.

## 4. Partially implemented

| Area | Present | Missing |
| --- | --- | --- |
| Identity / access | Fixed local demo identity, role and case scope | Real authentication, tenant isolation, durable user/agent permissions |
| Investigations | Case/evidence tables and seed example | Case CRUD API, evidence workflow, investigation UI |
| Risk assessment | Persistence model with bounded score and reason-code fields | Feature computation, detector, assessment service/API, evaluation |
| Agent security | Reserved directories, request/decision/audit tables, no exposed executor | OPA policies/client, authorization gate, approvals, bounded tools |
| Operations | Local runtime tested; Compose config checked statically | Image builds, Compose runtime, production roles and operational hardening |

## 5. Incomplete features

There is no fraud detector, ML training pipeline, fabricated accuracy metric,
location analysis, transaction-network analysis, active AI agent, LLM adapter,
human approval flow, or report generator. No existing detector or OPA engine
could therefore be executed. The UI correctly labels records as not assessed.
Phase 2 must implement real behavior instead of adding simulated outcomes.

## 6. Technical debt and security gaps

- Demo access is not authentication. Keep services on loopback and synthetic
  records only until real user/agent identities and authorization exist.
- The current local database role is a superuser. Separate migration and runtime
  privileges before deployment; do not silently rewrite the user's credentials.
- Every transaction currently requires a case. The target journey flags a
  transaction before an analyst creates a case. Decide how to decouple ingestion
  from case membership before building ingestion APIs. Use an additive migration
  and reviewed backfill that preserve existing IDs and evidence scope.
- Readiness checks table presence, not all schema details; retain the explicit
  Alembic drift check in release verification.
- Starlette warns about the test client's current httpx integration. It works
  with the locked versions; handle the warning through a deliberate dependency
  update, not an unrelated upgrade during stabilization.
- No frontend linter is configured. TypeScript checks and browser tests exist.
- Docker images use version tags rather than pinned digests; container runtime
  verification, TLS, secret management, monitoring, and backups remain future work.

## 7. Recommended Phase 2 architecture

Keep the existing layers. Put deterministic feature extraction and baseline
detection under `ml/src`, and application orchestration in backend services.
Validate transaction inputs with Pydantic before storing or scoring. Use decimal
money and timezone-aware timestamps; choose a documented scoring currency and
window definition rather than comparing amounts across currencies implicitly.

A detector result should contain a bounded score, source transaction ID,
reason codes, rule/model version, feature/evidence references, and scoring time.
Persist it in the existing assessment model and expose it through bounded,
authorized transaction APIs. The frontend should consume the persisted result,
including loading/error and human-review states. A high score is not proof of fraud.

For future agents, build the trust boundary before execution: authenticate the
principal, derive case/tenant scope server-side, evaluate OPA, require a valid
human approval when indicated, execute only an allow-listed bounded tool, validate
returned evidence scope, and write a sanitized audit event. On denial, timeout,
or unverifiable authorization, never call the executor. No unrestricted SQL,
filesystem, network, or external API tools should be made available to agents.

## 8. Dependencies needed

No application dependency was changed during stabilization. Begin with the
existing Python/SQLAlchemy/Pydantic stack and deterministic rules. Introduce
scikit-learn when a measured baseline or trained model requires it, pin a tested
version, and keep artifact/version provenance. Use the existing OPA/Rego plan for
the policy phase after validating a compatible runtime. LLM integration should
remain optional with a deterministic fallback; do not require paid APIs to demo.
Avoid graph databases, queues, orchestration frameworks, and additional services
until a demonstrated requirement justifies them.

## 9. Implementation order

1. Define transaction ingestion, case membership, feature windows, reason codes,
   scoring scale, and shared API contracts. Resolve the mandatory-case issue.
2. Implement synthetic feature extraction and an explainable deterministic
   baseline: amount deviation, frequency, unusual hour, new device/beneficiary.
3. Test missing/invalid inputs, boundary values, time zones, and data leakage.
   Evaluate only against meaningful labeled data; report limitations honestly.
4. Persist assessments with versioned reason codes and expose real transaction
   list/detail and assessment responses. Integrate the existing dashboard.
5. Add real identity and authorization, then OPA enforcement and audit/approval
   tests that prove denial happens before query execution.
6. Implement bounded investigation tools and evidence-linked reports only after
   the security gate passes. Add the optional LLM adapter behind that same gate.
7. Verify the end-to-end demo, container path, reproducible setup, and failure
   handling before a presentation or deployment milestone.

## 10. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Synthetic data mistaken for production model evidence | Label datasets/results; no invented accuracy; keep human review explicit |
| Leakage across time/customer/case boundaries | Time-aware evaluation splits, scope derived from the principal, negative tests |
| Amount and time inconsistencies | Decimal money, explicit currency handling, UTC storage and documented display/window zones |
| Agent prompt injection or unrestricted tools | Backend allow-list and OPA before execution; structured outputs and validated evidence |
| False claims that a denied request was blocked | Spy on the executor and assert it was never called; check the actual audit record |
| Schema change damages existing cases/evidence | Additive migrations, integrity checks, backups, explicit approval for destructive changes |
| Local success mistaken for deployment readiness | Keep Docker, production identity/roles, and operations as explicit release gates |

See [stabilization-report.md](stabilization-report.md) for exact commands and results.
