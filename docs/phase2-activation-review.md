# Milestones 2–4 integration and migration approval package

Prepared 18 November 2026. **STOPPED before active migration 0003, awaiting explicit approval.**

## Final dependency hardening review

The follow-up review found that checking a source hash alone did not bind
`prepare_m234_activation` to its intended module name and path. The bootstrap now
requires that name to resolve exactly to
`F:\Fraud-Sentinel\tmp\prepare_m234_activation.py`. The execution engine, legacy
helper, backend packages and Alembic dynamic modules receive equivalent bindings.
A finder placed before other import hooks rejects shadow locations and unexpected
loaders. Preloaded first-party objects are refused because their executed code
cannot be authenticated from `__file__`. Verified sources are compiled directly.
Unlisted local source/bytecode dependencies and noncanonical, traversal, symlink
or Windows reparse paths fail closed. File and ancestor-directory handles prevent
write/replacement and directory-renaming races while the runner is active.

The engine explicitly verifies `transaction_read_only=on` for the active preflight
and restored-copy comparison. Approval mode remains separate and has not been
executed. The backup, readiness evidence, original 51 implementation files and
`.env` remain preserved. The manifest builder requires the exact previous checksum
for replacement, archives that manifest, hashes locked files and atomically writes
the replacement; it has no database operations.

The expanded isolated suite contains 41 tests, including shadow helper imports,
preloaded replacements, wrong source hashes, path/reparse escape, unlisted bytecode,
real Windows junction rejection and file/directory locks, lock acquisition failure,
read-only enforcement and transaction outcomes.
The final normal/optimized test results, read-only preflight results and manifest
checksum are recorded in `tmp/m234-safeguard-review-receipt.json` and the final audit
response after the protected sources are finalized. Historical results below are
from the previous review; they are not substitutes for those final reruns.

This final review does not run the PostgreSQL upgrade tests, even in rollback-only
schemas, against the active database. Real activation/commit is not rehearsed here;
transaction failure paths use isolated mocks. Standard library, virtualenv packages,
the interpreter and Windows remain trusted. Do not use the old checksum or an
unreviewed freshly calculated checksum to authorize execution.

## Safeguard correction and re-audit

The initial runner failed its independent safety audit. The corrected procedure
supersedes that runner and the old command without a manifest checksum.

- Removed all safety assertions: 32 explicit runtime checks in the preparation
  helper and 60 in the legacy helper; the old runner's 17 assertions were replaced
  by explicit checks in the new bootstrap/execution engine. These checks remain
  active under Python optimization. No application or migration source changed.
- The bootstrap requires an exact approval/check flag (abbreviations rejected) and
  a separately recorded `--manifest-sha256`. It verifies and locks the manifest
  before loading local execution dependencies. The checksum must come from the
  completed review, not be recomputed blindly immediately before execution.
- Protected inventory includes all Git-visible files, all `tmp/*m234*.py` helpers,
  the imported legacy helper, baseline/readiness manifests, `.env` and the existing
  backup. New repository/helper paths invalidate the inventory. Any unlisted local
  Python source import is refused. Verified local source is compiled directly,
  avoiding stale local bytecode. Alembic SQL generation now runs in-process under
  this same verification boundary.
- Windows handles deny writes/deletion/replacement of protected files and remain
  held across imports, SQL generation, database validation and commit/reporting.
  Hashes/inventory are checked initially, immediately before migration and before
  commit. Database identity/revision and the preservation snapshot are checked
  inside the transaction immediately before migration. Post-migration data/schema
  checks and the final protected-file checks occur before commit.
- Outcomes distinguish `preflight_refused`, `failed_rolled_back`, `committed`,
  `committed_reporting_failed` and `state_uncertain`. Commit acknowledgement failures
  or failed rollback require manual inspection. No automatic retry/restore occurs.
  Completion is written atomically to a separate local outcome file; the original
  backup/readiness evidence is not overwritten.
- Isolated tests passed: 24 under normal Python, 24 with `-O`, and 24 with
  `PYTHONOPTIMIZE=1`. They cover approval parsing, identity/revision, missing/changed
  backup, protected files, `.env`, SQL, restored/preserved data, dependency omission,
  Windows write/replacement denial, transaction ordering, rollback/commit uncertainty
  and post-commit reporting failure. Database execution in these tests is mocked.
  A test initially exposed an unclear `.env` error message; it was corrected and
  all three execution modes rerun successfully.

Files modified: `tmp/apply_m234_after_approval.py`,
`tmp/prepare_m234_activation.py`, `tmp/activate_milestone1.py`, and this report.
Files added: `tmp/m234_execution.py`, `tmp/build_m234_manifest.py`,
`tmp/test_m234_safeguards.py`, and the protected manifest. Helpers/manifests remain
ignored by Git. The original 51 implementation paths are preserved.

Residual trust boundary: this is a local operational safeguard, not protection
against a compromised Windows administrator, Python interpreter or installed
third-party packages. Standard library/virtualenv code remains trusted; repository
requirements and configuration are hashed. The bootstrap itself is trusted to
perform its self/hash checks. An abrupt process/connection loss during COMMIT
requires manual database inspection. No production or agent authorization is added.

The protected manifest is created only after the reviewed source is finalized.
Its checksum is recorded separately in the final response/local receipt; the
manifest itself is read-locked and must match that checksum. Any subsequent code,
configuration or dependency-inventory change requires another review and manifest.


## Integration decision and plan

The reviewed implementation is already in `F:\Fraud-Sentinel`, on `main` at
`decf38e6a3ce1a636b799b660dea545e01d469b3`. There is no separate Milestones 2–4
code checkout to copy. The older detached worktree `F:\Fraud-Sentinel-phase2-m1`
contains the historical Milestone 1 preparation and is not the current integration source.

The isolated environment is the PostgreSQL database
`fraudsentinel_sandbox_fd28e34317374f19`, on the same local PostgreSQL server as the
active database. It is at `0003_investigation_workflow`. Its API runs on loopback
8001 and its Vite frontend on 5175, using the main checkout's code. The normal API
and frontend remain on 8000 and 5173. The sandbox supplies process-only database,
demo/sandbox and CORS settings; the frontend proxy selects 8001. No second copy of
the application or new dependencies are needed.

The 51-file review covers backend routes/configuration, contracts, both model
collections, repository/service boundaries, migrations, frontend integration,
tests and documentation. The exact disposition of every path appears below.
Against the saved Milestone 1 baseline, 11 paths remain byte-identical and seven
were intentionally extended during the previously completed Milestones 2–4 work.
The other 33 paths belong to Milestones 2–4. Those seven extensions are limited to
the overview integration, concurrency locks, migration test table count and status
documentation. No integration conflict or accidental removal requiring a code
change was identified.

The practical integration sequence is:

1. Preserve all 51 current files and their hashes; do not copy from the old worktree.
2. Confirm backend/router, Alembic metadata and frontend imports already connect the
   implementation in place. Preserve the existing environment, branch and remote.
3. Verify the original database, create a fresh full logical backup, restore it into
   a new separate database, and compare records/schema. **Completed.**
4. Regenerate and inspect exactly `0002:0003` SQL. Prepare guarded execution and
   recovery instructions. **Completed.**
5. Obtain explicit approval for the active schema migration. **Pending.**
6. Only after approval, recheck hashes/target/revision and execute the guarded
   transaction below; then perform the specified verification. Do not enable
   real-data mutation APIs, implement Milestone 5, commit or push.

**No application source, configuration or application tests were changed
during this preparation.** The safeguard correction updates this approval report. All original 51 file hashes still match the start of
this review. This approval document is the sole additional Git-visible file.

## Active database and current integrity

- Target: `fraudsentinel`, `127.0.0.1:55432`, PostgreSQL 16.15.
- Local data directory: `F:\Fraud-Sentinel\tmp\pgdata`.
- Current revision: **`0002_intelligence_contracts`**.
- Database OID, cluster identifier, server address and original role matched the
  saved Milestone 1 activation identity. Credentials were not printed or changed.
- All 10 application tables plus `alembic_version` were inspected. Existing
  columns, values, 44 constraints and 31 indexes were captured and verified.
- All **20 foreign-key integrity checks passed**; constraints were validated and
  indexes valid/ready. The active schema matches the Milestone 1 metadata.
- Counts: users 1, cases 1, transactions 6, evidence 1, audit events 1; accounts,
  case-account links, assessments, agent requests and policy decisions all 0.
- Original data/relationships and `.env` still match the preservation baseline.

## Fresh backup and independent restore test

Backup created and verified at **2026-11-18 09:29:48 UTC / 14:59:48 IST**:

`F:\Fraud-Sentinel\backups\phase2-m234-20261118T092945Z-03d60d\before-0003.dump`

- Format: full database PostgreSQL custom-format logical archive; 31,650 bytes.
- SHA-256: `21fcd36c0ee81a0de5d454012b97249c0c7225ec240790e8fd9ab1d33a469d11`.
- PostgreSQL 16.15 clients used an exported repeatable-read snapshot, so the dump
  and preservation fingerprints describe the same database snapshot.
- The archive was restored with `pg_restore --exit-on-error --single-transaction`
  into the newly created database
  `fraudsentinel_restorecheck_m234_20261118t092945z_1db664`.
- Restore succeeded without warnings/errors. All application row counts and
  complete row-value hashes matched; table/column definitions, defaults,
  nullability, constraints, indexes and revision matched. Only PostgreSQL's two
  equivalent renderings of four explicitly enumerated string checks were
  normalized for comparison. No arbitrary constraint differences were ignored.
- The restored database passed all 20 foreign-key checks and Milestone 1 model
  comparison. It remains at 0002 and is retained with default transactions read-only.
- A fresh read-only check confirmed the active database did not change during the
  backup/restore operation. No active schema operation or migration was performed.
- Backup folder permissions are restricted to the current Windows account and
  SYSTEM. Dumps, manifests and helper scripts remain ignored by Git.

The directory also contains the archive inventory, reviewed SQL and
`activation-readiness.json`. This is a database backup, not a cluster/OS backup:
cross-server recovery would also need compatible roles and PostgreSQL tooling.
Nothing was deleted, including the verification database and previous backups.

## Complete migration review

The regenerated SQL matches [the reviewed SQL](phase2-m234-upgrade.sql).
Normalized SQL SHA-256:
`a2f5f825b42e6718c0569cf4ae29b13696c41fb32edefc992e195605214ccc6b`.

| New table | Purpose | Constraints | Explicit secondary index |
| --- | --- | --- | --- |
| `analysis_runs` | Reproducible inputs and assessment deduplication | PK, fingerprint unique, assessment FK | None |
| `case_workflows` | Detailed status, assignment and version | PK, case/owner composite FK, assignee FK, two checks | `owner_id` |
| `case_events` | Investigation history and notes | PK, case FK, actor FK | `case_id` |
| `investigation_reports` | Immutable report snapshots | PK, fingerprint unique, case FK | `case_id` |
| `evidence_fingerprints` | Evidence content deduplication | PK, fingerprint unique, evidence FK | None |

Totals: **five empty tables**, **17 constraints** (five PKs, three unique constraints,
seven FKs and two checks), and **11 new index entries** (three explicit secondary
indexes plus eight indexes supporting primary/unique constraints). The earlier
“three indexes” description refers to explicit `CREATE INDEX` statements.

Existing tables, rows, columns, constraints and indexes are preserved. No data
backfill, reset, `DROP`, `DELETE`, `TRUNCATE`, `INSERT` or `ALTER` is present in the
upgrade SQL. The only `UPDATE` changes the Alembic revision from 0002 to 0003.
No cascading deletion behavior is introduced. The downgrade intentionally refuses
execution to protect investigation history.

DDL and FK creation require database locks; other writers can cause contention.
The prepared runner uses a five-second lock timeout, a 30-second statement timeout,
the explicit `public` search path, and locks existing tables in SHARE mode for its
preservation checks. Reads can continue; writes may wait briefly. It executes the
upgrade and preservation checks in one PostgreSQL transaction. No timing SLA is
claimed. A lock timeout or unexpected check failure must stop the operation.

## Exact execution command — only after explicit approval

The local guarded runner was prepared at
`F:\Fraud-Sentinel\tmp\apply_m234_after_approval.py`.
Use `--check --manifest-sha256 <REVIEWED_MANIFEST_SHA256>` for read-only verification.
The application mode has not been executed; the checksum is required in both modes.

```powershell
Set-Location F:\Fraud-Sentinel
.\.venv\Scripts\python.exe -B tmp\apply_m234_after_approval.py --approved --manifest-sha256 <REVIEWED_MANIFEST_SHA256>
```

Internally, this calls Alembic `upgrade 0003_investigation_workflow` with an explicit
connection; it does not use `head`. It revalidates the branch/checkpoint, all 51
file hashes, `.env`, backup checksum, restored copy, generated SQL, database identity,
current revision and full preservation snapshot. Unexpected checkout or database
changes stop execution. If records have changed since the backup, create and
restore-test a new backup and review that state before proceeding.

Before committing the database transaction, the runner checks that all existing
values, columns, relationships and indexes remain intact, the five new tables are
empty, the expected constraints/indexes exist, all FKs pass and Alembic reports no
schema drift. Any unexpected result must be investigated, not bypassed.

**Schema approval does not enable investigation APIs on the active database.**
`investigation_sandbox` remains false there; forcing it true against `fraudsentinel`
is rejected by the existing startup guard. Do not weaken that guard. Until the
later approved identity/policy work, the complete investigation workflow remains
available only in the isolated synthetic database.

## Recovery strategy

1. If migration/checks fail before commit, PostgreSQL rolls back that transaction.
   Stop, inspect the revision and preservation fingerprints, and report the failure.
   Do not automatically retry, downgrade or run demo-reset commands.
2. If the schema commits but later application checks fail, stop further activation
   and writes. Keep the original overview and safety gates intact; retain the added
   tables and investigate a forward repair. Do not delete new history.
3. If restoration becomes necessary, obtain separate approval. Verify the backup
   checksum and restore into a **new empty database** with compatible owner/locale,
   using `pg_restore --exit-on-error --single-transaction`, without `--clean`.
   Compare all data/schema before considering a connection switch.
4. Switching the application connection, replacing active data or changing `.env`
   requires separate explicit approval. No such recovery action is authorized or
   performed by this preparation. Retain the original database and backups.

## Verification and remaining gate

New checks completed during this preparation:

- 51-file review/classification and SHA-256 preservation check; no merge conflicts.
- Active/restored database integrity, full logical restore verification, model
  comparison and the guarded runner's read-only preflight: passed.
- **11 read-only HTTP smoke checks passed** across both APIs/frontends: original
  health/readiness/overview, active capabilities and access denial, sandbox health,
  capabilities/dashboard/account graph, and both frontend entry pages.
- Changed-file/build scan found no active secret values, credential signatures or
  conflict markers. Git whitespace validation passed.

The prior completed verification remains **134 backend tests and 18 browser tests
passed**, plus TypeScript, production build, Ruff, formatting and dependency checks;
see [the implementation review](phase2-review-results.md). Those complete suites
were not needlessly repeated because application/test files were unchanged.
They are prior results, not a claim of post-activation verification.

After approval and successful migration, rerun the relevant backend/security and
frontend regressions, TypeScript/build, API and integrity checks, and the complete
ingestion → analysis → relationships → evidence → case → report workflow in the
isolated sandbox. Migration rehearsals remain isolated. Use read-only checks for
the preserved main records; do not insert synthetic test records into the active
database or enable its write routes. Record post-activation results separately.

Known limits remain: synthetic-only investigation access; no production identity,
OPA or agent execution; bounded analysis/report sizes; no PDF or independent
evidence verification. Docker runtime was unavailable in the completed review;
existing Starlette/httpx and browser color-environment warnings remain documented.
No Milestone 5 work has started. Active activation and its final verification are
pending; the code is ready for that approval gate.

## Git status and exact file classification

Branch `main`; HEAD `decf38e6a3ce1a636b799b660dea545e01d469b3`.
Remote preserved: `https://github.com/aryanrawat00/FraudSentinel.git`.
The original 51 changes remain unchanged and unstaged. Adding this approval report
makes **52 changed paths: 16 modified tracked files, 36 added/untracked files,
zero deleted, zero staged**. Nothing was committed or pushed.

The table below classifies the original 51 paths; this new approval report is the
52nd path. “M1 extended” describes previously completed work, not new edits today.

<!-- INTEGRATION_FILE_CLASSIFICATION -->

| File | Git state | Milestone classification |
| --- | --- | --- |
| [README.md](../README.md) | Modified | M1 extended for M2-4 |
| [backend/app/api/v1/intelligence.py](../backend/app/api/v1/intelligence.py) | Added/untracked | M2-4 |
| [backend/app/api/v1/router.py](../backend/app/api/v1/router.py) | Modified | M2-4 |
| [backend/app/core/config.py](../backend/app/core/config.py) | Modified | M2-4 |
| [backend/app/core/request_limits.py](../backend/app/core/request_limits.py) | Added/untracked | M2-4 |
| [backend/app/main.py](../backend/app/main.py) | Modified | M2-4 |
| [backend/app/models/__init__.py](../backend/app/models/__init__.py) | Modified | M1 preserved |
| [backend/app/models/records.py](../backend/app/models/records.py) | Modified | M1 preserved |
| [backend/app/models/workflow.py](../backend/app/models/workflow.py) | Added/untracked | M2-4 |
| [backend/app/repositories/intelligence.py](../backend/app/repositories/intelligence.py) | Added/untracked | M1 extended for M2-4 |
| [backend/app/schemas/intelligence.py](../backend/app/schemas/intelligence.py) | Added/untracked | M1 preserved |
| [backend/app/schemas/overview.py](../backend/app/schemas/overview.py) | Modified | M1 preserved |
| [backend/app/schemas/workflow.py](../backend/app/schemas/workflow.py) | Added/untracked | M2-4 |
| [backend/app/services/__init__.py](../backend/app/services/__init__.py) | Added/untracked | M2-4 |
| [backend/app/services/access.py](../backend/app/services/access.py) | Added/untracked | M2-4 |
| [backend/app/services/detection.py](../backend/app/services/detection.py) | Added/untracked | M2-4 |
| [backend/app/services/evidence.py](../backend/app/services/evidence.py) | Added/untracked | M2-4 |
| [backend/app/services/investigations.py](../backend/app/services/investigations.py) | Added/untracked | M2-4 |
| [backend/app/services/relationships.py](../backend/app/services/relationships.py) | Added/untracked | M2-4 |
| [backend/config/scoring-rules.example.json](../backend/config/scoring-rules.example.json) | Added/untracked | M2-4 |
| [backend/migrations/env.py](../backend/migrations/env.py) | Modified | M2-4 |
| [backend/migrations/versions/0002_intelligence_contracts.py](../backend/migrations/versions/0002_intelligence_contracts.py) | Added/untracked | M1 preserved |
| [backend/migrations/versions/0003_investigation_workflow.py](../backend/migrations/versions/0003_investigation_workflow.py) | Added/untracked | M2-4 |
| [backend/scripts/reset_demo.py](../backend/scripts/reset_demo.py) | Modified | M1 preserved |
| [backend/scripts/run_investigation_sandbox.py](../backend/scripts/run_investigation_sandbox.py) | Added/untracked | M2-4 |
| [backend/scripts/synthetic_scenarios.py](../backend/scripts/synthetic_scenarios.py) | Added/untracked | M2-4 |
| [docs/phase2-m234-upgrade.sql](../docs/phase2-m234-upgrade.sql) | Added/untracked | M2-4 |
| [docs/phase2-milestone1.md](../docs/phase2-milestone1.md) | Added/untracked | M1 extended for M2-4 |
| [docs/phase2-milestones234.md](../docs/phase2-milestones234.md) | Added/untracked | M2-4 |
| [docs/phase2-plan.md](../docs/phase2-plan.md) | Added/untracked | M1 extended for M2-4 |
| [docs/phase2-readiness.md](../docs/phase2-readiness.md) | Modified | M1 extended for M2-4 |
| [docs/phase2-review-results.md](../docs/phase2-review-results.md) | Added/untracked | M2-4 |
| [docs/reference-review.md](../docs/reference-review.md) | Added/untracked | M2-4 |
| [frontend/playwright.config.ts](../frontend/playwright.config.ts) | Modified | M2-4 |
| [frontend/playwright.investigation.config.ts](../frontend/playwright.investigation.config.ts) | Added/untracked | M2-4 |
| [frontend/src/app/App.tsx](../frontend/src/app/App.tsx) | Modified | M1 extended for M2-4 |
| [frontend/src/app/InvestigationWorkspace.tsx](../frontend/src/app/InvestigationWorkspace.tsx) | Added/untracked | M2-4 |
| [frontend/src/services/intelligence.ts](../frontend/src/services/intelligence.ts) | Added/untracked | M2-4 |
| [frontend/src/services/validation.ts](../frontend/src/services/validation.ts) | Modified | M1 preserved |
| [frontend/src/styles/global.css](../frontend/src/styles/global.css) | Modified | M2-4 |
| [frontend/src/types/api.ts](../frontend/src/types/api.ts) | Modified | M1 preserved |
| [frontend/tests/foundation.spec.ts](../frontend/tests/foundation.spec.ts) | Modified | M1 preserved |
| [frontend/tests/investigation.spec.ts](../frontend/tests/investigation.spec.ts) | Added/untracked | M2-4 |
| [tests/integration/test_intelligence_repository.py](../tests/integration/test_intelligence_repository.py) | Added/untracked | M1 preserved |
| [tests/integration/test_investigation_workflow.py](../tests/integration/test_investigation_workflow.py) | Added/untracked | M2-4 |
| [tests/integration/test_phase2_migration.py](../tests/integration/test_phase2_migration.py) | Added/untracked | M1 extended for M2-4 |
| [tests/integration/test_sandbox_concurrency.py](../tests/integration/test_sandbox_concurrency.py) | Added/untracked | M2-4 |
| [tests/integration/test_workflow_postgres.py](../tests/integration/test_workflow_postgres.py) | Added/untracked | M2-4 |
| [tests/security/test_investigation_boundaries.py](../tests/security/test_investigation_boundaries.py) | Added/untracked | M2-4 |
| [tests/unit/test_detection_rules.py](../tests/unit/test_detection_rules.py) | Added/untracked | M2-4 |
| [tests/unit/test_intelligence_contracts.py](../tests/unit/test_intelligence_contracts.py) | Added/untracked | M1 preserved |

