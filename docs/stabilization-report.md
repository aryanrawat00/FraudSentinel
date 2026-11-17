# Phase 1 stabilization report - 17 November 2026

## A. Project Health

The existing Phase 1 foundation is working for controlled local development:
React -> Vite proxy -> FastAPI -> PostgreSQL. It is ready to begin the next
implementation milestone with the limitations below. This is not production
security certification or a claim that fraud detection and autonomous
investigation are implemented.

The existing structure, UI, dependencies, database records, `.env`, branch,
remote, and Git history were preserved. No commits or pushes were made. Changes
are unstaged on `main`; HEAD remains
`7ae908511a26a0603025e9881a8c51fe1f9cf301`.

Local services were left running for handoff:

- Workspace: <http://127.0.0.1:5173>
- Liveness: <http://127.0.0.1:8000/health>
- Readiness: <http://127.0.0.1:8000/api/v1/health/ready>
- Development API docs: <http://127.0.0.1:8000/docs>
- Existing portable PostgreSQL: loopback port 55432.

The five live HTTP checks (liveness, docs, readiness, frontend, and proxied
overview) all returned 200 at six points over 76.2 seconds. This establishes
observed local availability, not a long-duration load or reliability guarantee.

## B. Issues Discovered

Eight concrete defects were reproduced before fixing them:

| Defect | Observed consequence |
| --- | --- |
| Settings validation included raw input fragments | A synthetic password fragment appeared in a formatted validation error |
| PostgreSQL port lacked a valid range | Zero, negative, and above-65535 ports were accepted by settings |
| Production password validation accepted whitespace | Blank-looking credentials passed configuration validation |
| Demo access did not check the stored investigator role | A revoked/different-role demo user could reach case queries |
| Lifespan disposal was outside a `finally` block | An exceptional lifespan exit could bypass engine cleanup |
| Frontend trusted transaction JSON without runtime validation | A malformed date crashed rendering |
| Readiness trusted malformed 503 bodies | An unrelated upstream response looked like a migration problem |
| Amount display forced INR | A USD transaction was displayed as INR |

The earlier backend shutdown was separately investigated: the preceding
verification session explicitly stopped its servers. Normal terminal closure,
Ctrl+C, and Uvicorn reload worker replacement produce the observed shutdown
messages. The lifespan cleanup defect was real, but was not the cause of that
intentional stop. No automatic post-startup exit was reproduced.

Additional limitations, rather than repaired Phase 1 defects: Docker is absent;
the local database role is a superuser; real authentication, OPA enforcement,
agent execution, and fraud scoring are not implemented; no frontend linter is
configured. These remain explicit boundaries for subsequent work.

## C. Issues Fixed

- Settings now hide input values in formatted validation errors, constrain ports
  to 1-65535, and reject whitespace-only production passwords without rewriting
  the actual password or `.env`.
- The demo overview requires the stored `investigator` role before querying
  cases or transactions. Existing server-derived identity and ownership scope
  are retained. This guard does not substitute for real authentication.
- Database engine disposal is guaranteed by a lifespan `try/finally`, including
  an exceptional exit.
- The frontend validates health, readiness, and overview JSON before rendering.
  Dates, decimal amounts, currencies, counts, and required fields are checked.
  Malformed JSON or payloads produce a recoverable error without exposing the
  response body; a successful refresh restores the real data.
- Amount formatting uses each transaction's currency, and the footer accurately
  describes that behavior. The existing layout and visual style are preserved.
- Added regression coverage, a read-only PostgreSQL verification path, clearer
  startup instructions, and this report. No application dependency, migration,
  Docker service, or architectural layer was added or replaced.

## D. Files Changed

All paths below are repository-relative. **10 modified, 7 added, 0 deleted.**

| Status | File | Purpose |
| --- | --- | --- |
| Modified | `README.md` | Startup, shutdown, environment, and safe verification instructions |
| Modified | `backend/app/api/v1/overview.py` | Investigator role guard |
| Modified | `backend/app/core/config.py` | Safer validation and configuration bounds |
| Modified | `backend/app/main.py` | Guaranteed lifespan cleanup |
| Modified | `docs/api-contracts.md` | Document response validation and access boundaries |
| Modified | `docs/architecture.md` | Document lifecycle, validation, and deployment limitations |
| Modified | `docs/verification.md` | Distinguish historical results from this pass |
| Modified | `frontend/src/app/App.tsx` | Currency-aware display |
| Modified | `frontend/src/services/api.ts` | Validate responses and sanitize errors |
| Modified | `frontend/tests/foundation.spec.ts` | Six additional browser tests |
| Added | `docs/phase2-readiness.md` | Ten-area readiness assessment and implementation order |
| Added | `docs/stabilization-report.md` | This report |
| Added | `frontend/src/services/validation.ts` | Runtime API response guards |
| Added | `tests/integration/test_postgres_readonly.py` | Existing database/schema/API checks without writes |
| Added | `tests/security/test_api_boundaries.py` | Role, CORS, unavailable execution, and error boundaries |
| Added | `tests/security/test_configuration.py` | Configuration secret and input validation regressions |
| Added | `tests/unit/test_lifespan.py` | Exceptional cleanup regression |

No tracked files were deleted. Existing test assertions were preserved. Temporary
verification scripts, screenshots, and audit output remain under ignored `tmp/`.
Neither `.env`, dependency manifests/lockfiles, migration files, nor the Git
index was changed.

## E. Frontend Verification

TypeScript checking and the Vite production build passed. All **10 Playwright
tests passed**, including real backend data/refresh, API and database failure
states, mobile layout, malformed timestamps, malformed readiness responses,
record currency, valid empty data, loading behavior, and non-JSON errors.

The real overview displayed six existing synthetic transfers, one assigned
case, and zero assessments. The INR 95,000 transfer displayed at 02:14 IST. No
fake scores or metrics were introduced. Outage/invalid-response tests use
browser interception; normal integration reads the running backend/database.

Desktop and 390-pixel mobile screenshots were visually inspected. The mobile
table retains its horizontal scrolling region without overflowing the document.
The separate final browser check found zero workspace console errors and
confirmed that Swagger UI rendered. Screenshots are available locally at
`tmp/stabilization-desktop.png` and `tmp/stabilization-mobile.png`.

There is no frontend lint script; a frontend lint result is **NOT VERIFIED**.
Type checking, build checks, and browser coverage do not imply linting ran.

## F. Backend Verification

The existing application factory and `app.main:app` entry point work. Uvicorn
remained available through the repeated live probes and was left running.
`GET /health`, `/api/v1/health`, `/api/v1/health/ready`, and
`/api/v1/demo/overview` were exercised by API/integration tests. Development
`/docs` loaded, including actual Swagger rendering.

The implemented frontend performs GET requests only. CORS remains limited to
the required origins, methods, and headers; no POST/PUT/PATCH/DELETE permissions
were added. GET preflight succeeds, POST preflight is rejected, and credentialed
CORS was not enabled. Backend database errors return sanitized messages.

Ruff and `pip check` passed. The locked test client emits one non-blocking
Starlette/httpx deprecation warning; no dependency upgrade was made to hide it.

## G. Database Verification

The existing PostgreSQL 16.15 cluster was used, without initialization, reseeding,
reset, database recreation, or a destructive migration. The new optional tests
enforce `SET TRANSACTION READ ONLY` on every transaction.

Verified on PostgreSQL:

- Connection succeeds and all eight application tables exist.
- Current revision equals the expected head, `0001_foundation`.
- `upgrade head` succeeds as a no-op only after asserting current equals head.
- Alembic's schema/model drift check reports no pending operations.
- The real API returns readiness and scoped synthetic overview data.
- Before/after row fingerprints and the `.env` fingerprint match.

Preserved counts: one user, one case, six transactions, one evidence record,
one audit event, and zero assessments, agent requests, or policy decisions.
No record contents or credentials were printed for this preservation check.

Existing isolated SQLite tests cover implemented seed/idempotence/reset behavior,
ownership scope, and evidence constraints. Those fixtures are not the existing
PostgreSQL database. Public CRUD endpoints are not implemented; live database
mutation was not claimed or performed.

The original PostgreSQL test runs downgrade/re-upgrade operations inside a
temporary schema. It remains unchanged and was explicitly excluded because the
user prohibited destructive migrations. Its fresh execution is **BLOCKED by
that constraint**, not counted as a pass. Applying an initial schema from empty
or a pending migration was therefore not newly verified on PostgreSQL this pass.

## H. Security Verification

Tests cover production demo rejection/docs behavior, fixed server-side identity,
case scope, investigator-role revocation, cross-case evidence protection,
restricted CORS, settings validation, and sanitized database errors. Sensitive
unimplemented POST paths return 404; tests assert they never connect to the
database. This verifies the current absence of exposed execution paths, not an
implemented agent firewall or approval system.

Changed source/document files were checked for the actual local database secret
and common private-key/token patterns without printing secrets. None were found.
`.env` remains ignored and unchanged; `.env.example` contains placeholders.
No real credentials or financial records were added to the changes.

Dependency checks reported:

- npm audit: **0 known vulnerabilities** in the installed/locked dependency tree.
- Official PyPI advisory metadata lookup: **35 pinned packages checked, 35
  verified, no advisories returned** for those versions.
- `pip check`: no broken requirements.

These are checks against available advisory metadata, not proof of absence of
all vulnerabilities or a penetration test. No dependency versions changed.

Remaining security boundaries: demo identity is not login; the existing local
database role is a superuser; OPA, bounded agent tools, human approval, and
production operations are incomplete. Keep this instance on loopback with
synthetic records. Separate migration/runtime privileges and implement real
authorization before deployment or exposing sensitive actions.

## I. Testing Results

| Check | Result |
| --- | --- |
| Permitted backend suite, including unit/API/security and read-only PostgreSQL | **30 passed**, 0 failed, 1 dependency warning |
| Frontend Playwright suite | **10 passed**, 0 failed |
| TypeScript check | Passed |
| Vite production build | Passed |
| Ruff | Passed |
| Python dependency compatibility | Passed |
| Repeated live HTTP probes | All 30 responses were HTTP 200 across 76.2 seconds |
| Browser console / Swagger render | 0 workspace console errors; docs rendered |
| Data and `.env` preservation fingerprints | Matched |
| Static Compose review | Passed service/volume/loopback-port/dependency checks |
| Docker Compose config/build/start/container health | **BLOCKED: Docker is not installed** |
| Original PostgreSQL downgrade/re-upgrade test | **BLOCKED: destructive migration prohibited** |
| Frontend lint | **NOT VERIFIED: no configured linter** |

Before the fixes, the new backend regression set produced seven failures and
six passes; three new frontend regressions failed while the original four
browser tests passed. The final permitted runs above have no failures. The
original migration test was not removed or weakened to obtain those results.

Required completion checklist:

| Requirement | Status and evidence |
| --- | --- |
| Frontend starts | PASS: live page and browser tests |
| Frontend production build | PASS |
| Backend starts and remains running | PASS within the observed interval; services retained |
| FastAPI health | PASS |
| Development API documentation | PASS: browser-rendered Swagger |
| PostgreSQL connection | PASS |
| Migrations work | PASS for current revision, no-op upgrade, and drift check; full apply/rollback NOT VERIFIED this pass |
| Existing API endpoints | PASS for implemented routes |
| Frontend/backend communication | PASS through Vite proxy |
| Dashboard receives actual responses | PASS |
| Existing fraud detection tested | NOT VERIFIED: detector/scoring not implemented |
| AI agent restrictions preserved/tested | NOT VERIFIED for actual agents/OPA; absent execution routes and database non-execution tested |
| Security tests executed | PASS for implemented boundaries |
| Existing unit/integration tests executed | PASS except the explicitly BLOCKED PostgreSQL downgrade test |
| No critical unresolved errors | No failing executed checks; production security readiness NOT VERIFIED and gaps remain |
| Environment documented | PASS: README environment table |
| Windows instructions documented | PASS: commands below and README |

## J. How to Run FraudSentinel

The services were already running at handoff. Do not start duplicate servers on
the same ports. These commands are for subsequent sessions and preserve the
existing `.env` and database. Dependencies and the browser cache are already
installed in this checkout; see README for first-time dependency installation.

**PostgreSQL, from the repository root:**

```powershell
Set-Location F:\Fraud-Sentinel
.\.venv\Scripts\python.exe scripts/local_postgres.py status
# Start only if stopped:
.\.venv\Scripts\python.exe scripts/local_postgres.py start
```

**Migration inspection and application:**

```powershell
Set-Location F:\Fraud-Sentinel\backend
..\.venv\Scripts\python.exe -m alembic current
..\.venv\Scripts\python.exe -m alembic heads
..\.venv\Scripts\python.exe -m alembic check
# Current database is already at head, so this is presently a no-op.
# Review any future pending migration before applying it.
..\.venv\Scripts\python.exe -m alembic upgrade head
```

Do not downgrade, reset, or reseed as part of routine startup. No destructive
migration or data reset is authorized by these instructions.

**Backend, terminal 1 (leave it open):**

```powershell
Set-Location F:\Fraud-Sentinel\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend, terminal 2 (leave it open):**

```powershell
Set-Location F:\Fraud-Sentinel\frontend
npm.cmd run dev
```

**Verification, terminal 3:**

```powershell
Set-Location F:\Fraud-Sentinel
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
Invoke-RestMethod http://127.0.0.1:5173/api/v1/demo/overview

$env:RUN_POSTGRES_READONLY_TESTS = '1'
try {
    .\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml tests --ignore=tests/integration/test_postgres.py -q
} finally {
    Remove-Item Env:RUN_POSTGRES_READONLY_TESTS -ErrorAction SilentlyContinue
}
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend tests scripts
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build

$env:PLAYWRIGHT_BROWSERS_PATH = 'F:\Fraud-Sentinel\tmp\playwright'
Push-Location frontend
try {
    npm.cmd run test:e2e
} finally {
    Pop-Location
}
```

The PostgreSQL read-only tests require the existing migrated database; browser
tests require the existing seeded demo. They do not initialize either.

**Stopping later:** press Ctrl+C in each server terminal, then:

```powershell
Set-Location F:\Fraud-Sentinel
.\.venv\Scripts\python.exe scripts/local_postgres.py stop
```

This stops PostgreSQL without deleting its data. These stop commands were not
run during final handoff. Docker instructions remain in README, but Docker
runtime verification requires installation and must avoid conflicting ports.

## K. Phase 2 Readiness

The local foundation is ready for controlled Phase 2 development. See
[the ten-area readiness report](phase2-readiness.md) for implemented, working,
partial and missing features; debt; security gaps; architecture; dependencies;
implementation order; and risk mitigations.

An early design decision is required: transactions currently require a case,
while the intended journey detects a suspicious transaction before case
creation. Resolve ingestion versus case membership using an additive, reviewed
migration/backfill that preserves IDs and evidence boundaries. Do not silently
drop constraints or rebuild the database.

No Phase 2 detector, scoring API, agent, policy engine, or report generator was
implemented in this stabilization task. Existing tables/directories provide
integration points, not proof of working future behavior.

## L. Recommended Next Steps

1. Define transaction ingestion/case membership, input contracts, feature
   windows, scoring scale, currencies, and explainable reason codes.
2. Implement deterministic synthetic feature extraction and a transparent
   baseline for amount deviation, frequency, unusual hour, and new
   device/beneficiary. Test missing data, boundaries, and time handling.
3. Persist versioned assessments using the existing model, expose scoped APIs,
   and connect the dashboard to actual stored results. Evaluate honestly; a
   high score is a review signal, not confirmed fraud.
4. Add real identity/authorization and OPA enforcement before agent execution;
   prove denial, timeout, and missing approval prevent tool/database execution.
5. Add bounded investigation/evidence tools and evidence-linked reports, with
   any optional LLM adapter behind the same security checks.
6. Verify Docker execution, production database privileges, operational controls,
   and the full demo journey before a deployment milestone.

Review the unstaged changes before creating any commits. This task did not
commit, push, force-push, change remotes, delete branches, or rewrite history.
