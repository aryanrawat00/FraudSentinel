# FraudSentinel

A secure AI-powered financial fraud detection and investigation platform.

Phase 1 provides a React + TypeScript + Vite workspace connected to FastAPI,
PostgreSQL models and migrations, synthetic demo data, and local / Docker
development configuration. The workspace shows real API/database results, with
loading, disconnected, unseeded, and retry states.

Six synthetic transfers include INR 95,000 at 02:14 IST on an unseen device.
**Transactions are not yet scored.** Scikit-learn detection, full authentication,
OPA enforcement, agent tools, approvals, and investigation reports are later
modules. A suspicious transaction is never automatically confirmed fraud.

## Requirements

- Python 3.12 or newer (3.12 is tested).
- Node.js 22.12 or newer and npm.
- PostgreSQL 16, or Docker Desktop with Docker Compose v2.

Commands use PowerShell from the repository root. This checkout already has an
ignored `.venv`, installed frontend dependencies, and a generated `.env`. Its
current database port is **55432**; fresh setup defaults to 5432. The `.venv`
uses Codex's bundled Python because standalone Python was unavailable; install
Python 3.12 to recreate it independently.

## First-time dependency setup

Skip the first command if `.venv` already exists. On a fresh Windows machine,
install Python 3.12 with its Python launcher first.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e backend
.\.venv\Scripts\python.exe scripts/init_env.py
npm.cmd --prefix frontend ci
```

`init_env.py` generates a random local database password in ignored `.env`.
It never prints the password or overwrites an existing file. `.env.example` is a
placeholder template. Never put secrets in frontend variables, source, or logs.

## Run with Docker Compose

After creating `.env`, start Docker Desktop:

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose run --rm seed
docker compose ps
```

Compose waits for PostgreSQL, applies migrations in a one-shot service, starts
FastAPI, then serves built React through Nginx. Seeding is explicit and repeatable.

- Workspace: <http://localhost:5173>
- API liveness: <http://localhost:8000/health>
- Database readiness: <http://localhost:8000/api/v1/health/ready>
- API documentation: <http://localhost:8000/docs>

Stop with `docker compose down`. The database volume is retained. Do not add
`-v` unless intentionally deleting your local database. Do not run Docker and
the local servers simultaneously on the same ports.

## Run locally on this Windows checkout

PostgreSQL, FastAPI, and React have been verified together without Docker.
Portable database binaries and browser downloads live under ignored `tmp/`.
If the PostgreSQL binaries are not present yet, download them:

```powershell
npm.cmd install --prefix tmp/postgres-tooling @embedded-postgres/windows-x64@16.15.0-beta.19
```

The package's Windows symlink manifest is empty; its binaries work without a
postinstall script. For a fresh portable setup, run
`.\.venv\Scripts\python.exe scripts/init_env.py --postgres-port 55432` before
starting PostgreSQL. If `.env` exists, edit `POSTGRES_PORT` locally instead.

Start the database, migrate, and seed:

```powershell
.\.venv\Scripts\python.exe scripts/local_postgres.py start
Push-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m scripts.seed_demo_data
Pop-Location
```

The helper manages only this checkout's `tmp/pgdata`, binds to `127.0.0.1`, and
uses password authentication. It does not install a Windows service. With an
existing PostgreSQL installation, create the database/user yourself, configure
`.env`, and skip the portable helper.

For an already initialized checkout, starting PostgreSQL and applying an already
current migration does not require reseeding. Preserve existing `.env` values
and database records. Do not run reset commands as part of routine startup.

In terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In terminal 2:

```powershell
npm.cmd --prefix frontend run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` to FastAPI; the browser never
receives database credentials. Stop each server with Ctrl+C, then stop PostgreSQL:

```powershell
.\.venv\Scripts\python.exe scripts/local_postgres.py stop
```

Keep the two server terminals open while using the app. Uvicorn stays running
until its process receives a stop signal; closing its terminal or pressing
Ctrl+C causes the normal "Shutting down" / "Application shutdown complete"
sequence. With `--reload`, saving backend code also produces a shutdown/startup
sequence as the worker is replaced. The previous verification session explicitly
stopped its servers; it did not uncover an automatic application shutdown bug.

To verify independently while both terminals remain open:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
Invoke-RestMethod http://127.0.0.1:5173/api/v1/demo/overview
```

## Verify changes

Fast tests use isolated SQLite databases. The optional PostgreSQL test uses a
temporary schema and rolls it back without modifying the demo database.

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml tests -q
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend tests scripts
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend run build
```

With existing PostgreSQL data, use the non-destructive verification command:

```powershell
$env:RUN_POSTGRES_READONLY_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml tests --ignore=tests/integration/test_postgres.py -q
Remove-Item Env:RUN_POSTGRES_READONLY_TESTS
Push-Location backend
..\.venv\Scripts\python.exe -m alembic check
Pop-Location
```

These PostgreSQL tests enforce read-only transactions, check schema/model drift,
and allow `upgrade head` only when the database is already at the expected head.
They do not seed, reset, drop tables, or apply pending migrations. The original
`tests/integration/test_postgres.py` remains intact: it explicitly runs a
downgrade/re-upgrade in a temporary schema and is excluded above because that
operation requires separate authorization. Its previous results are historical,
not a substitute for a fresh authorized run.

There is no frontend lint script configured. `npm.cmd --prefix frontend run
typecheck` and the production build check TypeScript; Ruff checks Python.

Browser tests require the seeded database and API on port 8000. Playwright starts
Vite if port 5173 is unused. Use the ignored browser cache:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) 'tmp/playwright'
Push-Location frontend
npx.cmd playwright install chromium --only-shell
npm.cmd run test:e2e
Pop-Location
```

Python's async test client and browsers need loopback socket access. In a
restricted sandbox, allow local networking rather than altering application
behavior to avoid the restriction.

## Seed and reset

Repeat `python -m scripts.seed_demo_data` from `backend/` using the virtual
environment Python to insert missing demo records without duplicates. To discard
changes in the reserved synthetic case and recreate it:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m scripts.reset_demo --confirm-synthetic-reset
Pop-Location
```

Only `case_demo_001` and its related records are reset. Other cases are preserved.
Seed/reset refuse production mode or disabled demo mode.
Reset is destructive within that case and requires explicit owner authorization;
it was not run against the existing database during the stabilization review.

## Environment settings

| Variable | Purpose / local behavior |
| --- | --- |
| `APP_ENV` | `development`, `test`, or `production`; production rejects demo access and disables API docs |
| `DEMO_MODE` | Enables a fixed demo investigator; defaults to false in code and is explicitly true in the example |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Database address; port must be 1-65535; Compose overrides these internally to `db:5432` |
| `POSTGRES_DB`, `POSTGRES_USER` | Existing database and connecting role |
| `POSTGRES_PASSWORD` | Local secret generated into ignored `.env`; whitespace-only values are invalid in production |
| `CORS_ORIGINS` | JSON array of allowed browser origins; only GET and Content-Type are currently required |
| `API_PROXY_TARGET` | Vite's server-side backend target, normally `http://127.0.0.1:8000` |
| `RUN_POSTGRES_READONLY_TESTS` | Test-process-only opt-in for non-destructive PostgreSQL verification |
| `PLAYWRIGHT_BROWSERS_PATH` | Test-process-only path to the browser cache |

No database credentials are exposed through Vite's client environment. Invalid
backend settings fail with validation messages that omit input values. The demo
identity must exist with the `investigator` role; a different stored role is
denied before case or transaction queries run. This is not production login/RBAC.

## Structure

```text
backend/         FastAPI, settings, demo identity, models, migrations, seed/reset
frontend/        React, typed API client, responsive workspace, browser tests
deploy/          Backend/frontend Dockerfiles and Nginx proxy
tests/           API, database, migration, and security checks
scripts/         Local environment and portable PostgreSQL helpers
data-contracts/  Reserved shared contracts; current schema is at /openapi.json
ml/              Reserved data/model/source folders for detection
policy/          Reserved OPA policy/example/test folders for the firewall
docs/            Architecture, API contracts, verification results, decisions
```

Browser tests live in `frontend/tests` to keep their dependencies with the UI.
Other paths follow the supplied directory reference; future modules have
directories, not nonfunctional placeholder endpoints.

See [architecture](docs/architecture.md), [API contracts](docs/api-contracts.md),
and [verification results](docs/verification.md) for current behavior and limits.
The current [stabilization report](docs/stabilization-report.md) records checks,
fixes, and unverified items; the [Phase 2 readiness report](docs/phase2-readiness.md)
sets the next implementation order without claiming unfinished features work.

## Version control

The existing remote is
[aryanrawat00/FraudSentinel](https://github.com/aryanrawat00/FraudSentinel), with
`main` tracking `origin/main`. Follow [CONTRIBUTING.md](CONTRIBUTING.md): verify
each module, commit meaningfully, review every outgoing file/commit for secrets,
and show the change and commit summary before pushing. Never force-push, delete
branches, or overwrite remote history.
