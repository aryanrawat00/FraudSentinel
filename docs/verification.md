# Phase 1 verification - 16 November 2026

Verified on Windows using Python 3.12.14, Node.js 26.3.1, and PostgreSQL 16.15.
All database records used for these checks were synthetic.

| Check | Result |
| --- | --- |
| Backend API, configuration, data isolation, seed/reset, and schema tests | 16 passed with `RUN_POSTGRES_TESTS=1` |
| PostgreSQL migration upgrade, downgrade, and re-upgrade | Passed in an isolated, rolled-back test schema |
| Seed run twice | Six transactions, one case, one evidence record, one seed event; no duplicates |
| Alembic schema drift check | No new upgrade operations detected |
| Python lint | Passed |
| Python dependency compatibility (`pip check`) | Passed |
| TypeScript check and Vite production build | Passed |
| Chromium end-to-end tests | 4 passed |
| Desktop and mobile visual inspection | Passed at 1440px and 390px widths |
| Compose YAML parsing, migration dependency, loopback bindings | Passed static checks |
| Ignore rules | Local environment, database files, dependencies, and build output excluded; examples and lockfiles trackable |

The browser tests use the real local API and PostgreSQL for the success path.
They verify the INR 95,000 transfer at 02:14 IST, refresh, and a viewport without
page-level horizontal overflow. Separate browser tests simulate API/database
outages to verify visible errors, no fabricated counts, and successful retry.
The transaction table itself scrolls horizontally on small screens.

The PostgreSQL integration test uses a randomly named schema within a transaction
and rolls it back. It does not drop or rebuild the development database. Tests
also verify unrelated analyst records stay out of the demo overview, invalid
cross-case evidence is rejected, and reset preserves unrelated cases.

## Remaining verification limits

- Docker Desktop / Docker Engine is not installed here. Container image builds,
  `docker compose config`, and Compose startup were **not run**. YAML parsing is
  not a substitute for Docker's own validation. Run the README Docker commands
  on a Docker-enabled machine before relying on the container path.
- The in-app browser preview failed due to its Windows path handling. Independent
  headless Chromium tests and screenshot inspection succeeded.
- Starlette emits a dependency deprecation warning for the `httpx` test client;
  all API tests pass. Address this when updating the locked test dependencies.
- Detection, production authentication, OPA enforcement, LLM investigation,
  human approval, and report generation are not implemented in this foundation.

The next implementation priority is explainable fraud feature extraction and a
baseline detector, followed by persisted assessments and reason codes on the
transaction API/UI. Agent execution must remain unavailable until the planned
authorization and policy gate is implemented and tested.
