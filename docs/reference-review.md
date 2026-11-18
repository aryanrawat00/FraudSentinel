# Reference repository review — 18 November 2026

This is a source review, not a runtime audit or a claim that either project meets
FraudSentinel's security requirements. No external source code, assets or datasets
were copied, installed or executed.

## ArthaRaksha

[Repository](https://github.com/7shiny786/ArthaRaksha),
[Cloud Function source](https://github.com/7shiny786/ArthaRaksha/blob/main/Code/CloudFunction%20Code),
[fraud-analysis agent instructions](https://github.com/7shiny786/ArthaRaksha/blob/main/Code/Agent3-fraud_Analysis_Agent/Instructions.txt).

The inspected implementation is a Vertex AI/Gemini call-content prototype:
transcription, translation, summarization, fraud categorization and reporting tool
schemas. It is not an account-ledger graph detector. The Cloud Function writes
intermediate output to fixed GCS object names, accepts source paths, and includes
raw exception text in one error response. The reporting prompt contains a hardcoded
sender example. These patterns are unsuitable for evidence isolation or factual
investigation records. No repository-wide license was exposed in GitHub metadata
or the root listing; no reuse permission was assumed.

Adopted concept: carry clear reasons, source references and understandable report
sections through an investigation. FraudSentinel implements this independently
with stored transaction IDs, immutable snapshots and separate findings/notes.
Deferred: audio, translation, cloud agents and fraud-report submission; they need
separate scope, consent, infrastructure and policy review.

## AgentGuard / Vanzik

The supplied [AgentGuard URL](https://github.com/Caua-ferraz/AgentGuard) redirects to
[lictorate/vanzik](https://github.com/lictorate/vanzik). The inspected
[license](https://github.com/lictorate/vanzik/blob/master/LICENSE) is Apache-2.0,
with a [NOTICE](https://github.com/lictorate/vanzik/blob/master/NOTICE). Any future
code redistribution must preserve applicable license/notices and mark modifications;
this implementation contains no copied Vanzik code.

The Go [policy engine](https://github.com/lictorate/vanzik/blob/master/pkg/policy/engine.go)
evaluates deny, approval and allow rules, defaults to deny, and denies policy-provider
failures. The [proxy](https://github.com/lictorate/vanzik/blob/master/pkg/proxy/server.go)
tracks scoped approvals and one-shot consumption; its source also warns about
unauthenticated approvals when no API key is configured. The
[store interface](https://github.com/lictorate/vanzik/blob/master/pkg/store/store.go)
requires tenant attribution and preserves terminal decisions during synchronization.
Audit redaction/sealing are configuration-sensitive features, not universal guarantees.

Adopted now: explicit disabled-by-default boundaries, failure before database/tool
access, scoped reads, bounded input/output, immutable history, deterministic
deduplication and tests proving prohibited execution does not occur. FraudSentinel
does **not** claim to implement Vanzik, OPA, an AI firewall or human approvals.

Deferred to milestones 5/6: authenticated policy decisions, request-bound approvals,
expiry and one-shot execution, policy-unavailable denial, redacted audit export and
external integrity anchors. Adding an executor or permissive stand-in now would
violate the milestone boundary and weaken the current default refusal.

## Comparison with the implemented FraudSentinel workflow

| Area | FraudSentinel milestones 2–4 |
| --- | --- |
| Fraud intelligence | Deterministic ledger-based rules with saved inputs and exact decimal scores |
| Relationships | Bounded directed transfer graph and traceable associations; no identity claims |
| Evidence | Scoped original references, unverified-by-default records, idempotent collection |
| Cases/reports | Validated transitions, notes/history, immutable JSON snapshots |
| User experience | React investigation dashboard with actual scoped API data and error states |
| Security | Isolated synthetic sandbox only; real identity, policy and agents remain unimplemented |

No licensing assumptions were used to copy code, and no accuracy or security claims
from the reference readmes were adopted as verification evidence.
