# Phase 1 architecture

React calls relative `/api/v1` URLs. Vite proxies these during development;
Nginx does the same in Compose. FastAPI validates responses with Pydantic,
opens bounded SQLAlchemy sessions, and accesses PostgreSQL using psycopg.
Connection URLs are built from separate settings to handle special characters
in passwords correctly.

The schema contains users, cases, transactions, risk assessments, evidence,
agent requests, policy decisions, and audit events. Monetary amounts use fixed
precision decimals. Transaction timestamps have time zones and are displayed in
IST. Evidence has a composite foreign key to its transaction and case, preventing
cross-case references at the database level.

Alembic owns schema changes. API startup neither creates tables nor seeds data.
The seed inserts six synthetic transactions, a demo analyst/case, one source
evidence record, and one seed audit event. It creates no fabricated risk score or
policy decision. Reset affects only the reserved demo case.

## Current access model

`DEMO_MODE=true` enables a fixed server-side demo identity. The overview query
only includes cases owned by that identity; caller-supplied user/role headers
cannot select another analyst. This is a local demonstration identity, not a
production login system. Demo mode is disabled by default and rejected when
`APP_ENV=production`. Compose exposes services only on loopback.
The stored demo user must also retain the `investigator` role. Other roles are
rejected before case/transaction queries. No role is accepted from client headers.

Production settings require a nonempty database password, reject wildcard CORS,
and disable interactive API documentation. This foundation still needs proper
authentication, authorization, TLS, secret management, monitoring, and deployment
hardening before production use.
The current portable local PostgreSQL role is a superuser, as created by the
initial development cluster. Its privileges and credentials were not changed
during stabilization. Before deployment, provision separate migration and
least-privilege runtime roles and move away from the local demo identity.

No agent tool endpoints, LLM calls, direct agent database access, or financial
actions exist in Phase 1. Policy and agent folders reserve the locations for the
planned backend authorization gate. Do not enable agent execution until OPA
enforcement, scope validation, approval handling, and denial-before-query tests
are implemented.

## Dependencies

Python and npm versions are locked after local verification. PostgreSQL 16 is
the configured and tested database. Docker image digest pinning belongs with
deployment hardening. The optional portable Windows PostgreSQL helper supports
local testing without Docker; its binaries, data, password, logs, and browser
downloads remain ignored.

The frontend now validates runtime API responses as well as using TypeScript
interfaces. Uvicorn's lifespan releases the engine in a `finally` block even
when shutdown encounters an exception. Neither change introduces a new service,
dependency, data migration, or agent capability.

References: [FastAPI containers](https://fastapi.tiangolo.com/deployment/docker/),
[SQLAlchemy psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg),
[Vite setup](https://vite.dev/guide/), and
[portable PostgreSQL](https://github.com/leinelissen/embedded-postgres).
