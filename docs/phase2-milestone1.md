# Phase 2 Milestone 1 - contracts and persistence

## Status

Activated and verified in the main checkout at `F:\Fraud-Sentinel`. The active
database revision is `0002_intelligence_contracts`. Before activation, a custom
PostgreSQL backup was restored into a separate database and verified, the clean
Phase 1 checkpoint was checked, and the complete migration SQL was reviewed.
All 18 tested files were promoted; existing records, relationships, indexes and
`.env` were preserved. Activation verification passed 72 backend tests and
11 browser tests, TypeScript, build, Ruff and schema checks. No commits/pushes
were made. The checkpoint remains `decf38e`.

**Historical implementation record below:** the remaining sections document the
isolated preparation and pre-activation gate as originally reviewed. References
to pending promotion or a Phase 1-only main checkout are historical, not the
current state. For the current milestones 2–4 implementation, validation and
pending migration **0003**, see [the operating guide](phase2-milestones234.md).

The [eight-milestone plan](phase2-plan.md) describes the full scope and gates.

## Implemented contracts and repository behavior

Pydantic contracts are defined in `backend/app/schemas/intelligence.py`.
The repository is `backend/app/repositories/intelligence.py`.

| Entity | Contract and implemented persistence |
| --- | --- |
| Account | Identifier, known/unknown status, optional opening time, source and synthetic flag; create/retrieve within dataset scope |
| Transaction | Source/destination references, decimal amount, currency, aware timestamp, type/status, optional channel/device/location, source and synthetic flag; create without a case, retrieve, filter and paginate |
| Case | Title, description and priority; create/retrieve, attach transactions and accounts idempotently; preserve existing open/in_review/closed statuses |
| Assessment | 0-100 decimal score, category, factors with contributions/source IDs/review guidance, method, version, status and missing information; append history and retrieve it |
| Evidence | Primary transaction, optional account, case and/or assessment association, fact/indicator/interpretation kind, method and typed provenance; create/retrieve, initially unverified |

Inputs reject extra fields, privileged caller-supplied ownership, invalid IDs,
nonpositive/oversized amounts, more than two monetary decimal places, binary
floating-point money, invalid/naive timestamps, and unbounded query limits.
Currency validation checks a three-uppercase-letter format; it is not a complete
ISO registry check. The current monetary storage supports **two decimal places**;
three-decimal currencies require a later reviewed precision decision. No exchange
rate conversion or cross-currency aggregation is performed.

Timestamps normalize to UTC. Query windows are [start, end), with stable ordering
by descending time then transaction ID. Page size is 1-100 and offset 0-10000.
Supporting provenance references are validated in one bounded query, with at
most 100 distinct transaction IDs. Missing context is null, not invented data.

Factor contributions must sum to the supplied score and reason codes must be
unique. This validates a contract; it does **not** implement a detection engine,
category threshold selection, correlation handling, or model evaluation.
Those are Milestone 2. Test assessments are explicitly synthetic fixtures.

## Access and transaction boundaries

Repository callers must supply a trusted application actor. The actor must exist
with a supported role; reviewers cannot mutate records. Administrator, analyst,
and investigator operations remain restricted to their own dataset. The owner is
never taken from a contract body. Resource selection is scoped in SQL, including
assessment and evidence retrieval. Cross-scope account/case references also have
composite database foreign keys.

This is **not authentication**. No new HTTP endpoint, CORS permission, login,
token, agent tool, OPA enforcement, or administrator credential was introduced.
New mutation APIs remain unavailable pending the identity/policy milestone.

The caller owns the SQLAlchemy session transaction. Repository methods flush,
never commit. A failed import can be rolled back atomically. IDs are not reused
to overwrite existing records, and assessments are append-only through this API.
Existing audit events record actions and case scope; detailed per-resource audit
references, case history and human approvals remain later workflow work.

## Migration proposed for approval

`backend/migrations/versions/0002_intelligence_contracts.py` follows
`0001_foundation`. It is PostgreSQL-only and transactional.

1. Add `accounts` and `case_accounts` with access ownership and foreign keys.
2. Add case description, priority and optional update time.
3. Allow transactions before case creation; add owner/account references and
   source/context/status metadata. Legacy customer, beneficiary and device
   fields become nullable so missing information can be represented honestly.
4. Backfill **only the new transaction owner column**, copying the existing case
   owner. Existing IDs, amounts, currencies, times, case links, and source fields
   are unchanged. Account mappings and historical creation times remain null.
5. Add assessment explanation/status fields. Keep the existing 0-1 score column,
   constraint, values and history. Repository conversion multiplies/divides by
   100 exactly; e.g. stored `0.4200` becomes contract score `42.00`.
6. Allow evidence associated with an assessment before case creation. Retain the
   existing transaction/case foreign key, and add direct transaction and
   assessment/transaction constraints. Legacy provenance remains empty/unknown.
7. Add indexes for ownership and account/assessment lookups.

There are no DELETE, DROP TABLE, TRUNCATE, database recreation, or original-column
value updates. Schema locks and owner backfill still require a reviewed rollout
on the existing database. Automatic downgrade is deliberately refused because
it would discard Phase 2 columns/records. Recovery uses a separately reviewed
forward repair or an authorized backup restoration, not an automatic data drop.

The isolated PostgreSQL test upgrades an empty **temporary test schema** to
Phase 1, inserts synthetic historical records, upgrades to Phase 2, compares all
original column values, verifies schema/model agreement and exercises actual
repository writes/reads. Its outer transaction rolls back the entire test schema.
The application's public schema/revision is never migrated by that test.

## Phase 1 compatibility

Existing routes, demo access restrictions, liveness, frontend design and seed
behavior remain. The overview contract now accepts null customer/device/
beneficiary context. The frontend displays "Customer unavailable" / "Unavailable"
instead of fabricating values or crashing.

The explicit demo-reset helper now removes reserved-case account links and
assessment-only evidence tied to that case's transactions before recreating its
synthetic records. Account references and unrelated cases are preserved. Reset
was tested only on isolated fixtures and was **not run on the existing database**.

## Verification results

- **70 backend tests passed**, including all selected Phase 1 unit/API/security
  tests, new contracts/repository tests and the actual PostgreSQL upgrade test.
- **11 browser tests passed** on the isolated frontend at port 5174, including
  the original ten tests and missing-context compatibility. The success path
  used the unchanged Phase 1 API at port 8000; malformed/null contexts used
  interception. This is not a claim of exposed Phase 2 HTTP APIs.
- TypeScript, Vite production build, Ruff and schema/model drift checks passed.
- One existing Starlette/httpx deprecation warning remains.
- The original destructive PostgreSQL round-trip test remains excluded. Its
  full-head downgrade is incompatible with the new forward-only migration; it
  must not be used as a Phase 2 release check without a separately reviewed test
  strategy. Its assertions were not weakened or removed.
- The two existing live PostgreSQL read-only tests are pending on the Phase 2
  checkout because the live application schema deliberately remains at Phase 1.
  Run them after approval and application of the migration. The isolated upgrade
  test checks the new schema now.
- Docker execution remains unavailable in this environment.

No dependency version, `.env`, primary checkout source file, branch, or remote was
changed. Main's database preservation is checked separately after testing.
The final preservation check matched the original record and `.env` fingerprints;
main remained clean and live readiness returned ready/connected/schema-ready.
Changed-file and frontend-bundle secret checks passed. The generated SQL for
review is available locally at `tmp/phase2-milestone1-upgrade.sql`.

## Reproduce the isolated backend checks (PowerShell)

This checkout uses the already installed Phase 1 virtual environment, with
`PYTHONPATH` selecting the new source. The test environment file is read only.

```powershell
Set-Location F:\Fraud-Sentinel-phase2-m1
$env:PYTHONPATH = 'F:\Fraud-Sentinel-phase2-m1\backend'
$env:RUN_PHASE2_POSTGRES_TESTS = '1'
$env:PHASE2_TEST_ENV_FILE = 'F:\Fraud-Sentinel\.env'
& 'F:\Fraud-Sentinel\.venv\Scripts\python.exe' -m pytest -c backend/pyproject.toml tests --ignore=tests/integration/test_postgres.py --ignore=tests/integration/test_postgres_readonly.py -q
& 'F:\Fraud-Sentinel\.venv\Scripts\python.exe' -m ruff check --config backend/pyproject.toml backend tests scripts
Remove-Item Env:RUN_PHASE2_POSTGRES_TESTS, Env:PHASE2_TEST_ENV_FILE, Env:PYTHONPATH
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

To reproduce browser verification without conflicting with Phase 1, start
`npm.cmd run dev -- --port 5174` from the isolated checkout's `frontend` directory.
The local ignored `frontend/tmp/phase2-playwright.config.ts` points the standard
suite to that server. Then run:

```powershell
Set-Location F:\Fraud-Sentinel-phase2-m1\frontend
$env:PLAYWRIGHT_BROWSERS_PATH = 'F:\Fraud-Sentinel\tmp\playwright'
npm.cmd run test:e2e -- --config tmp/phase2-playwright.config.ts
```

Do not start the modified backend against the Phase 1 schema: it requires the
reviewed migration. Keep the original Phase 1 servers running until rollout.

## Files in this milestone

Modified: `README.md`, `docs/phase2-readiness.md`,
`backend/app/models/records.py`, `backend/app/models/__init__.py`,
`backend/app/schemas/overview.py`, `backend/scripts/reset_demo.py`,
`frontend/src/types/api.ts`, `frontend/src/services/validation.ts`,
`frontend/src/app/App.tsx`, `frontend/tests/foundation.spec.ts`.

Added: `backend/app/schemas/intelligence.py`,
`backend/app/repositories/intelligence.py`,
`backend/migrations/versions/0002_intelligence_contracts.py`,
`tests/unit/test_intelligence_contracts.py`,
`tests/integration/test_intelligence_repository.py`,
`tests/integration/test_phase2_migration.py`,
`docs/phase2-plan.md`, `docs/phase2-milestone1.md`.

Deleted: none. Local browser config, generated SQL and dependencies are ignored.

## Next approval and remaining work

Review this migration and diff before promoting the tested files to the main
checkout and applying revision `0002_intelligence_contracts` to the existing
database. That activation is the remaining Milestone 1 gate. No commit or push
is included in migration approval.

After activation, verify live readiness, unchanged legacy values, existing API/UI
behavior and the two read-only PostgreSQL tests. Review and authorize a milestone
checkpoint separately. Milestone 2 can then implement actual detection, factor
weights/correlation caps, historical windows and configurable risk categories.

Technical references used for the migration and constraints:
[Alembic operations](https://alembic.sqlalchemy.org/en/latest/ops.html),
[SQLAlchemy constraints](https://docs.sqlalchemy.org/en/20/core/constraints.html).
