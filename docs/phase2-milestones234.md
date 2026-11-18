# Phase 2 milestones 2–4 — implementation and operating guide

Reviewed 18 November 2026. Milestones 2, 3 and 4 are implemented and verified in
the **isolated synthetic sandbox**. Activation on the existing development database
is pending approval for `0003_investigation_workflow`. This is not production
authorization or a completion claim for milestones 5–8.

The original database remains `fraudsentinel`, `127.0.0.1:55432`, at
`0002_intelligence_contracts`. Its six transactions, one case, one evidence record,
one user and one audit event are preserved. `.env`, branch `main`, remote and
checkpoint `decf38e6a3ce1a636b799b660dea545e01d469b3` are unchanged. Nothing is staged,
committed or pushed. See [verification and file manifest](phase2-review-results.md).

## Architecture and scope

FastAPI routes under `/api/v1/intelligence` call deterministic services and the
existing scoped SQLAlchemy repository. Transactions, accounts, assessments and
evidence retain Milestone 1 contracts and exact decimal handling. Services flush;
the API transaction commits the entire operation or rolls it back on failure.
Pydantic request contracts reject extra ownership/privilege fields. Explicit
response models cover persisted records, assessment detail, dashboard and reports.

Five additive tables preserve new state: `analysis_runs`, `case_workflows`,
`case_events`, `investigation_reports`, `evidence_fingerprints`. They use a separate
SQLAlchemy metadata collection so pending workflow activation does not make the
original foundation's readiness check fail. Alembic compares both collections at
the new head. There is no separate graph database or new runtime dependency.

The frontend keeps the existing overview and adds an investigation workspace with
API-backed dashboard, transaction ingestion/analysis, directed account graph,
evidence register, case forms, status transitions, notes, linked records, timeline,
saved-report retrieval and JSON download. Loading, empty, error, validation,
responsive layout and keyboard-accessible controls are included. Graph drawing
shows up to 20 nodes; the connection table lists the complete returned bounded graph.

## Detection and risk methodology

Inputs are stored transactions. History belongs to the same dataset and source
account (or a legacy customer reference when account mapping is unavailable).
Synthetic, non-synthetic and unknown-provenance records are not mixed. Only
strictly earlier event timestamps within 30 days are considered; equal timestamps
are excluded because their order is unknown. The latest 99 earlier records are the
default bound. Truncation and insufficient history are disclosed. Amount and timing
baselines require five same-currency, same-transaction-type observations. No FX
conversion, customer identity inference or trained model is used.

| Rule | Default contribution | Explanation |
| --- | ---: | --- |
| Amount spike | 25 | Amount at least 5× the comparable historical median |
| Rapid sequence | 25 | At least 4 observed transactions within 10 minutes, including target |
| Unusual hour | 15 | UTC hour at least 3 circular hours from all comparable historical hours |
| New device | 10 | Observed device absent from at least five known earlier device observations |
| New country | 10 | Observed country absent from at least five known earlier country observations |
| New channel | 5 | Observed payment channel absent from at least five earlier known observations |
| Rapid fan-out | 10 | At least 3 distinct recorded receiver accounts within the rapid window |

Rapid sequence and fan-out share a configurable 35-point cap. Weights must be
nonnegative and total at most 100. Missing attributes add **no points**. Failed,
pending and reversed targets are not scored using completed-payment rules. Legacy
unknown-status records remain explicitly unknown. UTC normalization prevents the
database connection timezone from changing the timing rule.

Categories: low `[0,25)`, medium `[25,50)`, high `[50,75)`, critical `[75,100]`.
These are review priorities, not fraud probabilities or verdicts. Default values
are validated in `Rules`; [configuration example](../backend/config/scoring-rules.example.json)
can be selected with the process-only `SCORING_RULES_PATH` setting. Do not edit the
existing `.env` for verification. The sandbox launcher carries this setting through.

Each contribution cites stored transaction IDs and provides analyst guidance.
Public decimal scores are divided by 100 into existing `Numeric(5,4)` storage and
multiplied by 100 on read. An analysis snapshot saves the exact target, bounded
history, algorithm identifier, configuration and truncation flag. A SHA-256
fingerprint produces a deterministic assessment identifier. Repeated identical
analysis reuses the result; changed history/configuration appends another result.
This is content deduplication, not cryptographic authentication. Row locks and
unique keys protect concurrent requests. Replay is the pure `evaluate` function
over the saved snapshot and configuration.

Synthetic scenarios cover normal activity (0), large amount (25), unusual timing
(15), bursts, repeated transfers, fan-out, a directed cycle and a composite critical
signal (85) under default rules. These outcomes are fixture expectations, not
real-world model accuracy. New inputs and customized rules may produce other scores.

## Relationships and evidence

Traversal is scoped, depth 1–3, with at most 100 transaction records and 100 findings.
Filters use `[occurred_from, occurred_before)`. Directed edges carry observed sender,
receiver, transaction IDs, count and completed-count information. Repeated transfers,
shared counterparties, shared source-device references, fan-out and three-account
cycles are derived from those records. A cycle does not establish chronological
fund flow; common devices/counterparties do not establish common ownership. No
geographic-distance or legal-identity inference is made.

Evidence is immutable through the API: there is no edit/delete/verification endpoint.
New evidence is unverified, with kind, primary transaction, optional account,
assessment/case references, source description, observation timestamp and provenance.
Assessment-factor collection is idempotent. Manual evidence validates all references
before content deduplication. Account references must be transaction participants.
Case-associated evidence cannot cite sources assigned to another case. Reports
recheck provenance, including sources that were associated with a different case
after evidence collection. Corrections are new evidence records or analyst notes.

## Case workflow and reports

Cases can start manually or from transactions, assessments, account findings and
evidence. The UI's account workflow carries the returned graph's source transactions
into the case form for review. A transaction retains one primary case; reassignment
is refused. Association requests are idempotent. Case and transaction locks prevent
competing requests from silently moving records.

Transitions are `open → under_investigation → pending_review → resolved → closed`.
Pending review and resolved can return to investigation; an open case can be closed
without progressing. Closed cases reject mutations, including analysis/evidence
collection, but permit report generation. Optimistic case versions reject stale edits.
Assignment is limited to the current investigator or unassigned; cross-user
assignment awaits real identity and shared-scope policy.

The existing `cases.status` contract remains `open/in_review/closed`; new workflow
statuses live in `case_workflows` and project to those legacy states. Detailed
case-created, status/metadata-change, link, note, assessment and report events are
append-only. Legacy audit history is preserved but is not retrospectively invented.

Reports snapshot case overview/status, accounts, case transactions, assessments and
factor explanations, case-source relationship findings, evidence, supporting source
transactions, timeline, observations, analyst notes, recommendations and limitations.
Recorded facts, independently verified evidence, system findings and notes are
separate. The verified-facts section is empty unless a stored evidence record is
already verified; no new verification authority is claimed. Reports can be retrieved
later and regenerated; identical source state reuses the report. Prior report-generation
events are excluded from the content hash to keep regeneration idempotent.

Limits: 100 case transactions, 100 accounts, 100 evidence records, 500 assessments,
500 non-report timeline events and 500 supporting sources. Oversized reports fail
explicitly instead of silently dropping evidence. JSON export is implemented; PDF
export is deferred. Report hashes detect content differences but are not signatures
or externally anchored audit integrity guarantees.

## API inventory

All paths below are relative to `/api/v1/intelligence`. Except `/capabilities`,
they require the explicitly enabled local synthetic sandbox. Lists support validated
`limit` (1–100) and `offset` (0–10000) where applicable.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/capabilities` | Safe feature availability without touching protected data |
| GET | `/dashboard` | Actual scoped totals, latest-score distribution, high-risk activity and events |
| GET / POST | `/accounts` | List / create synthetic account references |
| GET / POST | `/transactions` | Filter/list / ingest synthetic transfers |
| GET | `/transactions/{id}` | Details, latest assessment history and evidence |
| POST | `/transactions/{id}/analyze` | Persist deterministic analysis |
| GET | `/transactions/{id}/assessments` | Paginated assessment history |
| GET | `/assessments/{id}` | Assessment and reproducibility snapshot |
| POST | `/assessments/{id}/evidence` | Collect actual factor evidence |
| GET | `/accounts/{id}/relationships` | Connected accounts, directed graph and supported findings |
| GET / POST | `/evidence` | Filter/list / validate and record evidence |
| GET | `/evidence/{id}` | Scoped evidence detail |
| GET / POST | `/cases` | Filter/list / create case and initial links atomically |
| GET / PATCH | `/cases/{id}` | Case detail / version-checked update |
| GET | `/cases/{id}/transactions` | Paginated linked transactions |
| POST | `/cases/{id}/links` | Link transactions, assessments, accounts and evidence |
| POST | `/cases/{id}/notes` | Append analyst note |
| GET | `/cases/{id}/timeline` | Paginated detailed history |
| GET / POST | `/cases/{id}/reports` | List snapshots / generate report |
| GET | `/cases/{id}/reports/{report_id}` | Retrieve immutable JSON snapshot |

Writes require `X-FraudSentinel-Sandbox: synthetic-only`, an allowed Origin when
present and no cross-site fetch context. This header is a CSRF/context marker,
**not a password or authentication token**. Host and peer must be loopback; the
stored fixed demo user must retain investigator role. Client-supplied identity is
never used. SQLite is permitted only for in-memory test fixtures. PostgreSQL must
be local and named `fraudsentinel_sandbox_*`; enabling the flag against `fraudsentinel`
fails at startup. Production and non-demo configurations reject sandbox activation.

Writes are capped at 1 MiB, responses use `Cache-Control: no-store`, validation does
not echo rejected values, SQL details/parameters are not returned, and response text
is rendered with React escaping. Disabled-mode, host and origin refusals occur
before database access; the stored-role check precedes dataset queries. SQL queries
use bound parameters. There is no arbitrary SQL/tool execution,
external financial action, agent runtime, authentication token, OPA enforcement or
human approval executor. These remain milestones 5 and 6. Local machine users can
access the sandbox; it must contain synthetic data only.

## Reproduce the synthetic workflow

The existing `.env` is read only for local PostgreSQL connectivity. The launcher
creates a random **new** sandbox database, applies migrations there, checks drift,
seeds labeled scenarios and starts loopback API port 8001. It refuses remote targets.
It never drops databases, downgrades or resets existing records. Each fresh launch
retains prior sandboxes. `--resume` reopens the recorded sandbox without migrating or
seeding it; the ignored `tmp/investigation-sandbox.json` contains no credentials.

```powershell
# Terminal 1: first launch; use --resume for subsequent launches.
Set-Location F:\Fraud-Sentinel\backend
..\.venv\Scripts\python.exe -m scripts.run_investigation_sandbox --port 8001

# Terminal 2: separate frontend, leaving the main app on 5173 intact.
Set-Location F:\Fraud-Sentinel\frontend
$env:API_PROXY_TARGET = 'http://127.0.0.1:8001'
npm.cmd run dev -- --port 5175
```

Open `http://127.0.0.1:5175/#investigations`. Analyze `scenario_high`, collect its
evidence, create a case, link the collected evidence, add a note, advance its status
and generate a report. Relationships rooted at `scenario_sender` show the synthetic
network. No financial data, account actions or external AI calls are performed.

## Migration approval gate

The complete reviewed SQL is [0003 upgrade SQL](phase2-m234-upgrade.sql). It creates
five tables and three indexes and updates only the Alembic revision. No original
tables, columns, indexes, constraints, rows or relationships are removed or changed.
Upgrade-only tests run in random schemas and roll back the entire schema afterward.
They verify original values, FK/index preservation and model/schema agreement.

**Do not apply it to the active database yet.** Approval must precede an active
rollout with a fresh restorable backup, target/revision verification and reviewed
SQL. Applying the schema alone does not authorize real-data write APIs; those stay
disabled pending the later identity/policy milestone. No commit or push is included.

## Limitations before milestone 5

- Implement real authentication, RBAC/shared scopes, least-privilege database roles,
  policy enforcement and an auditable human approval boundary before real-data writes.
- Keep agent execution unavailable until the later approved executor milestone.
- Validate/tune rules on authorized representative data before operational use.
  No real-world accuracy, calibrated probability or performance SLA has been measured.
- Dense graphs and large reports are bounded; wider investigations need reviewed
  pagination/export expansion. Graph findings are capped at 100 and report limitations
  disclose that bound. Transactions with equal event times have unknown ordering.
- Cross-case historical evidence is deliberately refused, not silently merged.
- Audit events and reports are append-only through the API, not tamper-proof against
  privileged direct database writes. Evidence verification and PDF export are absent.
- The current local PostgreSQL role is powerful; sandbox containment is not a substitute
  for production credentials, identity or policies. Docker runtime remains untested.

See [reference repository review](reference-review.md) for adopted/deferred ideas.
