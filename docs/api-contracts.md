# Phase 1 API

Development documentation is available at `/docs`. The generated contract is
`/openapi.json`; frontend interfaces are in `frontend/src/types/api.ts`.

| Route | Response | Failure behavior |
| --- | --- | --- |
| `GET /health` | 200: `status`, `service`, `version`, UTC `timestamp` | Does not query the database |
| `GET /api/v1/health` | Same liveness response | Same as `/health` |
| `GET /api/v1/health/ready` | 200: `status=ready`, `database=connected`, `schema_ready=true` | 503 if PostgreSQL is unreachable or foundation tables are missing |
| `GET /api/v1/demo/overview` | 200: demo identity, scoped counts, up to six recent transactions | 403 if demo mode is disabled or the stored demo role is not investigator; 409 if unseeded; 503 for database failure |

Overview records contain `transaction_id`, `case_id`, `customer_id`, `amount`,
`currency`, `occurred_at`, `device_id`, and `beneficiary_id`. Amounts are decimal
strings to preserve money precision. Times are ISO 8601 timestamps with offsets.
Counts and records are selected from the demo identity's cases. The API accepts
no caller-controlled SQL, user identity, or role.

Database exceptions are not returned to clients. Failed readiness does not
affect liveness. Readiness checks connectivity and required table names; use
`alembic check` to check model/schema drift.

The frontend validates the JSON response shape before rendering counts and
records. Invalid JSON, invalid dates/amounts, and malformed readiness payloads
produce a recoverable error instead of a render crash or misleading migration
message. Currency labels come from each record's `currency`; timestamps remain
displayed in IST. Server error bodies are not copied into the user-facing error.

Only GET APIs exist today. CORS permits GET and Content-Type for the configured
origins, with no credentialed or wildcard access added. Agent, investigation
execution, and approval POST routes are intentionally absent until their real
authorization and policy workflow is implemented.
