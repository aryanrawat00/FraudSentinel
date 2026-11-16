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

## Verify changes

Fast tests use isolated SQLite databases. The optional PostgreSQL test uses a
temporary schema and rolls it back without modifying the demo database.

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml tests -q
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend tests scripts
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend run build
```

With PostgreSQL running:

```powershell
$env:RUN_POSTGRES_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml tests -q
Remove-Item Env:RUN_POSTGRES_TESTS
Push-Location backend
..\.venv\Scripts\python.exe -m alembic check
Pop-Location
```

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

## Version control

The existing remote is
[aryanrawat00/FraudSentinel](https://github.com/aryanrawat00/FraudSentinel), with
`main` tracking `origin/main`. Follow [CONTRIBUTING.md](CONTRIBUTING.md): verify
each module, commit meaningfully, review every outgoing file/commit for secrets,
and show the change and commit summary before pushing. Never force-push, delete
branches, or overwrite remote history.
