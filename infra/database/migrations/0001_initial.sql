BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'SRC-%'),
    name text NOT NULL,
    owner text NOT NULL,
    base_url text NOT NULL,
    source_grade text NOT NULL CHECK (source_grade IN ('S1','S2','S3','S4','S5','S6')),
    authority_scope jsonb NOT NULL DEFAULT '[]'::jsonb,
    languages jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate','trial','active','degraded','inactive','retired')),
    crawl_status text NOT NULL DEFAULT 'pending_terms_review',
    last_reviewed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'DOC-%'),
    source_id uuid NOT NULL REFERENCES sources(id),
    canonical_url text NOT NULL,
    document_type text NOT NULL CHECK (document_type IN ('html','pdf','social','api','other')),
    primary_language text,
    published_at timestamptz,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    publication_status text NOT NULL DEFAULT 'raw_only' CHECK (
        publication_status IN ('discovered','raw_only','staged','under_review','canonical_private','publishable','published','rejected','expired','quarantined')
    ),
    UNIQUE (source_id, canonical_url)
);

CREATE TABLE document_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(id),
    previous_version_id uuid REFERENCES document_versions(id),
    version_number integer NOT NULL CHECK (version_number > 0),
    title_original text,
    raw_object_uri text NOT NULL,
    content_hash text NOT NULL CHECK (content_hash LIKE 'sha256:%'),
    text_original text,
    source_updated_at timestamptz,
    crawled_at timestamptz NOT NULL,
    etag text,
    last_modified text,
    processing_status text NOT NULL DEFAULT 'fetched',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (document_id, version_number),
    UNIQUE (document_id, content_hash)
);

CREATE TABLE entities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'ENT-%'),
    entity_type text NOT NULL,
    canonical_name text NOT NULL,
    name_original text,
    status text NOT NULL DEFAULT 'active',
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE entity_aliases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id uuid NOT NULL REFERENCES entities(id),
    alias text NOT NULL,
    language text,
    normalized_alias text NOT NULL,
    source_document_version_id uuid REFERENCES document_versions(id),
    confidence numeric(5,4) CHECK (confidence BETWEEN 0 AND 1),
    UNIQUE (entity_id, normalized_alias, language)
);

CREATE TABLE events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'EVT-%'),
    event_type text NOT NULL,
    title_zh text NOT NULL,
    summary_zh text,
    event_date date,
    event_date_precision text NOT NULL DEFAULT 'unknown',
    fact_level text NOT NULL DEFAULT 'F0' CHECK (fact_level IN ('F0','F1','F2','F3','F4')),
    conflict boolean NOT NULL DEFAULT false,
    publication_status text NOT NULL DEFAULT 'canonical_private',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE event_entities (
    event_id uuid NOT NULL REFERENCES events(id),
    entity_id uuid NOT NULL REFERENCES entities(id),
    role text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, entity_id, role)
);

CREATE TABLE claims (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'CLM-%'),
    subject_entity_id uuid REFERENCES entities(id),
    predicate text NOT NULL,
    value_json jsonb NOT NULL,
    value_type text NOT NULL,
    fact_level text NOT NULL DEFAULT 'F0' CHECK (fact_level IN ('F0','F1','F2','F3','F4')),
    claim_status text NOT NULL DEFAULT 'active' CHECK (
        claim_status IN ('active','partial','conflict','corrected','retracted','superseded','source_unavailable')
    ),
    valid_from timestamptz,
    valid_to timestamptz,
    observed_at timestamptz NOT NULL DEFAULT now(),
    rule_version text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE claim_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id uuid NOT NULL REFERENCES claims(id),
    document_version_id uuid NOT NULL REFERENCES document_versions(id),
    evidence_role text NOT NULL CHECK (evidence_role IN ('supports','contradicts','mentions','supersedes','retracts')),
    source_span jsonb NOT NULL,
    independence_group text,
    directness numeric(5,4) CHECK (directness BETWEEN 0 AND 1),
    extraction_confidence numeric(5,4) CHECK (extraction_confidence BETWEEN 0 AND 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (claim_id, document_version_id, evidence_role, source_span)
);

CREATE TABLE event_claims (
    event_id uuid NOT NULL REFERENCES events(id),
    claim_id uuid NOT NULL REFERENCES claims(id),
    PRIMARY KEY (event_id, claim_id)
);

CREATE TABLE projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'PRJ-%'),
    entity_id uuid NOT NULL UNIQUE REFERENCES entities(id),
    project_status text NOT NULL DEFAULT 'rumor' CHECK (
        project_status IN ('rumor','intent','announced','approved','construction','trial_operation','operational','delayed','scaled_down','suspended','cancelled')
    ),
    status_as_of date,
    status_evidence_claim_id uuid REFERENCES claims(id),
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'POL-%'),
    entity_id uuid NOT NULL UNIQUE REFERENCES entities(id),
    issuer_entity_id uuid REFERENCES entities(id),
    policy_level text,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','announced','gazetted','effective','amended','expired','repealed')),
    current_version_id uuid,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE policy_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id uuid NOT NULL REFERENCES policies(id),
    previous_version_id uuid REFERENCES policy_versions(id),
    document_version_id uuid NOT NULL REFERENCES document_versions(id),
    version_label text NOT NULL,
    published_at timestamptz,
    effective_at timestamptz,
    expires_at timestamptz,
    fields jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (policy_id, version_label)
);

ALTER TABLE policies
    ADD CONSTRAINT policies_current_version_fk
    FOREIGN KEY (current_version_id) REFERENCES policy_versions(id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE embeddings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    object_type text NOT NULL,
    object_id uuid NOT NULL,
    model_id text NOT NULL,
    embedding vector,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (object_type, object_id, model_id)
);

CREATE TABLE review_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'REV-%'),
    review_type text NOT NULL,
    risk_level text NOT NULL CHECK (risk_level IN ('R0','R1','R2','R3')),
    object_type text NOT NULL,
    object_id uuid NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','in_review','approved','approved_with_limits','returned','rejected','quarantined')),
    assigned_to uuid,
    decision_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz
);

CREATE TABLE audit_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_type text NOT NULL,
    actor_id text NOT NULL,
    action text NOT NULL,
    object_type text NOT NULL,
    object_id text NOT NULL,
    before_json jsonb,
    after_json jsonb,
    reason text,
    task_id text,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE outbox (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type text NOT NULL,
    aggregate_type text NOT NULL,
    aggregate_id uuid NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    attempts integer NOT NULL DEFAULT 0
);

CREATE INDEX documents_published_at_idx ON documents (published_at DESC);
CREATE INDEX document_versions_crawled_at_idx ON document_versions (crawled_at DESC);
CREATE INDEX entity_aliases_normalized_idx ON entity_aliases (normalized_alias);
CREATE INDEX events_event_date_idx ON events (event_date DESC);
CREATE INDEX events_fact_level_idx ON events (fact_level, publication_status);
CREATE INDEX claims_subject_predicate_idx ON claims (subject_entity_id, predicate);
CREATE INDEX claim_evidence_document_idx ON claim_evidence (document_version_id);
CREATE INDEX review_tasks_status_risk_idx ON review_tasks (status, risk_level, created_at);
CREATE INDEX outbox_unpublished_idx ON outbox (created_at) WHERE published_at IS NULL;

COMMIT;

