# Milestones 2–4 final review — 18 November 2026

## Delivery status

| Milestone | Verified implementation | Release status |
| --- | --- | --- |
| 2 | Configurable deterministic detection, exact scores, explanations, saved inputs and deduplicated assessment history | Complete in isolated synthetic sandbox; active rollout pending |
| 3 | Bounded account graph, direct/indirect connections, supported patterns, scoped evidence and provenance | Complete in isolated synthetic sandbox; active rollout pending |
| 4 | Cases, self-assignment, transitions, atomic links, notes/history and immutable JSON reports | Complete in isolated synthetic sandbox; active rollout pending |

The frontend and backend work together using actual sandbox PostgreSQL records.
The existing overview remains functional. Production authentication, OPA, human
approvals and agent execution were not implemented; milestones 5–8 were not started.
PDF export, independent evidence verification and cross-user assignment are deferred.

## Executed verification

- **133 backend tests passed** in the full permitted suite, including unit,
  API/security, repository, two upgrade-only PostgreSQL migration tests and an
  actual concurrent HTTP test against the isolated PostgreSQL sandbox.
- **1 additional existing live PostgreSQL read-only test passed**, verifying the
  original health/readiness/demo endpoints. Total: **134 backend tests passed**.
- **18 browser tests passed**: all 11 original foundation regressions plus seven
  investigation tests. The latter include a real PostgreSQL-backed ingestion →
  analysis → evidence → case → status → note → linked evidence → JSON report flow.
- TypeScript, Vite production build, Ruff, Python dependency consistency, formatting
  of new Python/TypeScript files and Git whitespace checks passed.
- Desktop dashboard, account relationships and the 390-pixel mobile dashboard were
  visually reviewed; the inspected screens had no clipping or broken layout.
- The original destructive downgrade/upgrade PostgreSQL test was **not run**.
- The old live “database must equal newest migration head” test was **not run**:
  the active database intentionally remains at 0002 pending approval. A separate
  read-only schema comparison against the unchanged Milestone 1 model passed.
  The isolated 0003 schema passed full Alembic/model comparison.
- One existing Starlette/httpx deprecation warning remains. Browser tooling emits
  an environment `NO_COLOR`/`FORCE_COLOR` warning. Neither is suppressed in tests.
- Docker runtime is unavailable; no Docker validation or production performance
  SLA is claimed. Synthetic scenarios do not establish real-world fraud accuracy.

## Review findings and fixes

Multiple review passes covered the Milestone 1 repository, existing routes, input
handling, queries, frontend and complete migration SQL.

1. Fixed new constraint-name mismatches caught by PostgreSQL drift checks. Added
   explicit new PK/FK/check names and preservation assertions.
2. Fixed the inaccessible case-status selector caught by browser testing. Blocked
   repeated actions during requests and preserved loading state across overlapping reads.
3. Added case-before-transaction lock ordering and row refreshes. Concurrent
   identical analyses return the same assessment; competing case associations
   produce one success and one conflict, preserving the first association.
4. Made repeated links leave version/timeline unchanged, rejected stale updates,
   and blocked analysis/evidence mutation on closed cases.
5. Rechecked evidence and assessment source references during report generation;
   refused unavailable/cross-case provenance and oversized reports. Case graph
   findings use all included case transactions, including disconnected components.
6. Normalized UTC timestamps and tested equivalent offsets. Missing data adds no
   risk, currency/type baselines are separate, and temporal rules share a cap.
7. Added 1 MiB streamed request limits, safe validation errors, no-store headers,
   hostile-origin/host rejection, synthetic-only ingestion and stored-role checks.
8. Removed misleading unconditional “Not assessed” labels from the foundation
   preview while preserving original data and access behavior.
9. Corrected stale Phase 2 status documentation and distinguished current activation
   from the historical Milestone 1 preparation record.

SQL uses bound parameters; server-controlled dataset scope governs resources.
Evidence/report retrieval is scoped. No arbitrary SQL, destructive route,
client-selected role, external agent tool or unescaped HTML rendering was added.
Changed-source/build secret checks found no active credentials. `.env`, dumps,
databases, local manifests, dependencies and test output remain ignored.

The fixed local identity and powerful local database role are explicit limitations.
This is not production authentication, tenant authorization, a policy firewall,
independently verified evidence or tamper-proof audit storage. Real-data mutation
and agent execution must stay disabled until the later security milestones.

## Database and Git checkpoint

Active database: `fraudsentinel` at `127.0.0.1:55432`, revision
`0002_intelligence_contracts`. New head: `0003_investigation_workflow`.
No migration was applied to the active database during this work.

Read-only checks confirmed original values, relationships and indexes: one user,
one case, six transactions, one evidence record, one audit event, zero assessments,
agent requests and policy decisions, and empty account/case-account tables.
`.env` matches the Milestone 1 activation fingerprint. The active schema has no
unexplained drift against 0002; 0003 is an intentional pending migration.

The new migration ran only in temporary rollback-only schemas and new synthetic
sandbox databases. It adds five tables and three indexes. No destructive operation,
original-record update, downgrade or reset was performed. Review the complete
[generated SQL](phase2-m234-upgrade.sql).

Branch: `main`. HEAD: `decf38e6a3ce1a636b799b660dea545e01d469b3`.
Existing remote preserved. Nothing staged, committed or pushed; no branch or remote
history was changed. The manifest includes the protected 18-file Milestone 1 baseline.

## Reproduce checks

Launch/resume the isolated API and frontend using the [operating guide](phase2-milestones234.md).
Then run in PowerShell:

```powershell
Set-Location F:\Fraud-Sentinel
$env:RUN_PHASE2_POSTGRES_TESTS = '1'
$env:PHASE2_TEST_ENV_FILE = 'F:\Fraud-Sentinel\.env'
$env:RUN_SANDBOX_HTTP_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml tests --ignore=tests/integration/test_postgres.py --ignore=tests/integration/test_postgres_readonly.py -q
$env:RUN_POSTGRES_READONLY_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml tests/integration/test_postgres_readonly.py::test_existing_postgres_serves_real_health_and_demo_responses -q
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend tests scripts
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
$env:PLAYWRIGHT_BROWSERS_PATH = 'F:\Fraud-Sentinel\tmp\playwright'
npm.cmd --prefix frontend run test:e2e
npm.cmd --prefix frontend run test:e2e -- --config playwright.investigation.config.ts
```

## Approval and next phase

Ready for review and milestone 5 planning, not real financial data or production.
Before active rollout, approve migration 0003, then verify a fresh restorable backup,
target database, revision and reviewed SQL before applying it. Schema approval
does not authorize real-data writes, agents, a Git commit or a push.

Review the sandbox at `http://127.0.0.1:5175/#investigations`; the original app remains
at `http://127.0.0.1:5173`. Licensing/comparisons are in
[reference-review.md](reference-review.md). No reference code was copied.

## Exact file manifest

<!-- FILE_MANIFEST -->

Total: **51 files**: **16 modified**, **35 added**, **0 deleted**. All unstaged.

Includes all 18 Milestone 1 paths. This session adds 33 paths to that baseline and extends 7 baseline files.

### Modified tracked files

- `README.md`
- `backend/app/api/v1/router.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/models/__init__.py`
- `backend/app/models/records.py`
- `backend/app/schemas/overview.py`
- `backend/migrations/env.py`
- `backend/scripts/reset_demo.py`
- `docs/phase2-readiness.md`
- `frontend/playwright.config.ts`
- `frontend/src/app/App.tsx`
- `frontend/src/services/validation.ts`
- `frontend/src/styles/global.css`
- `frontend/src/types/api.ts`
- `frontend/tests/foundation.spec.ts`

### Added/untracked files

- `backend/app/api/v1/intelligence.py`
- `backend/app/core/request_limits.py`
- `backend/app/models/workflow.py`
- `backend/app/repositories/intelligence.py`
- `backend/app/schemas/intelligence.py`
- `backend/app/schemas/workflow.py`
- `backend/app/services/__init__.py`
- `backend/app/services/access.py`
- `backend/app/services/detection.py`
- `backend/app/services/evidence.py`
- `backend/app/services/investigations.py`
- `backend/app/services/relationships.py`
- `backend/config/scoring-rules.example.json`
- `backend/migrations/versions/0002_intelligence_contracts.py`
- `backend/migrations/versions/0003_investigation_workflow.py`
- `backend/scripts/run_investigation_sandbox.py`
- `backend/scripts/synthetic_scenarios.py`
- `docs/phase2-m234-upgrade.sql`
- `docs/phase2-milestone1.md`
- `docs/phase2-milestones234.md`
- `docs/phase2-plan.md`
- `docs/phase2-review-results.md`
- `docs/reference-review.md`
- `frontend/playwright.investigation.config.ts`
- `frontend/src/app/InvestigationWorkspace.tsx`
- `frontend/src/services/intelligence.ts`
- `frontend/tests/investigation.spec.ts`
- `tests/integration/test_intelligence_repository.py`
- `tests/integration/test_investigation_workflow.py`
- `tests/integration/test_phase2_migration.py`
- `tests/integration/test_sandbox_concurrency.py`
- `tests/integration/test_workflow_postgres.py`
- `tests/security/test_investigation_boundaries.py`
- `tests/unit/test_detection_rules.py`
- `tests/unit/test_intelligence_contracts.py`

### Milestone 1 paths extended

- `README.md`
- `docs/phase2-readiness.md`
- `frontend/src/app/App.tsx`
- `backend/app/repositories/intelligence.py`
- `docs/phase2-milestone1.md`
- `docs/phase2-plan.md`
- `tests/integration/test_phase2_migration.py`
