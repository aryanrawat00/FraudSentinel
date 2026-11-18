BEGIN;

-- Running upgrade 0002_intelligence_contracts -> 0003_investigation_workflow

CREATE TABLE analysis_runs (
    assessment_id VARCHAR(64) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    snapshot JSON NOT NULL,
    CONSTRAINT pk_analysis_runs PRIMARY KEY (assessment_id),
    CONSTRAINT uq_analysis_runs_fingerprint UNIQUE (fingerprint),
    CONSTRAINT fk_analysis_runs_assessment_id_risk_assessments FOREIGN KEY(assessment_id) REFERENCES risk_assessments (assessment_id)
);

CREATE TABLE case_workflows (
    case_id VARCHAR(64) NOT NULL,
    owner_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    assigned_to VARCHAR(64),
    version INTEGER NOT NULL,
    CONSTRAINT pk_case_workflows PRIMARY KEY (case_id),
    CONSTRAINT fk_case_workflows_scope FOREIGN KEY(case_id, owner_id) REFERENCES cases (case_id, owner_id),
    CONSTRAINT ck_case_workflows_status CHECK (status IN ('open','under_investigation','pending_review','resolved','closed')),
    CONSTRAINT ck_case_workflows_version CHECK (version >= 1),
    CONSTRAINT fk_case_workflows_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (user_id)
);

CREATE INDEX ix_case_workflows_owner_id ON case_workflows (owner_id);

CREATE TABLE case_events (
    event_id VARCHAR(64) NOT NULL,
    case_id VARCHAR(64) NOT NULL,
    actor_id VARCHAR(64) NOT NULL,
    kind VARCHAR(40) NOT NULL,
    description TEXT NOT NULL,
    "references" JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_case_events PRIMARY KEY (event_id),
    CONSTRAINT fk_case_events_case_id_cases FOREIGN KEY(case_id) REFERENCES cases (case_id),
    CONSTRAINT fk_case_events_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (user_id)
);

CREATE INDEX ix_case_events_case_id ON case_events (case_id);

CREATE TABLE investigation_reports (
    report_id VARCHAR(64) NOT NULL,
    case_id VARCHAR(64) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    content JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_investigation_reports PRIMARY KEY (report_id),
    CONSTRAINT uq_investigation_reports_fingerprint UNIQUE (fingerprint),
    CONSTRAINT fk_investigation_reports_case_id_cases FOREIGN KEY(case_id) REFERENCES cases (case_id)
);

CREATE INDEX ix_investigation_reports_case_id ON investigation_reports (case_id);

CREATE TABLE evidence_fingerprints (
    evidence_id VARCHAR(64) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    CONSTRAINT pk_evidence_fingerprints PRIMARY KEY (evidence_id),
    CONSTRAINT uq_evidence_fingerprints_fingerprint UNIQUE (fingerprint),
    CONSTRAINT fk_evidence_fingerprints_evidence_id_evidence FOREIGN KEY(evidence_id) REFERENCES evidence (evidence_id)
);

UPDATE alembic_version SET version_num='0003_investigation_workflow' WHERE alembic_version.version_num = '0002_intelligence_contracts';

COMMIT;

