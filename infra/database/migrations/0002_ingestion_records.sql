BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations (filename)
VALUES ('0001_initial.sql')
ON CONFLICT (filename) DO NOTHING;

CREATE TABLE ingestion_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'ING-%'),
    contract_version text NOT NULL,
    task_id text NOT NULL,
    run_id text,
    idempotency_key text NOT NULL UNIQUE,
    source_id uuid NOT NULL REFERENCES sources(id),
    document_id uuid NOT NULL REFERENCES documents(id),
    document_version_id uuid NOT NULL REFERENCES document_versions(id),
    submitted_url text NOT NULL,
    canonical_url text NOT NULL,
    content_hash text NOT NULL CHECK (content_hash LIKE 'sha256:%'),
    raw_object_uri text NOT NULL,
    collection_relevance text NOT NULL CHECK (
        collection_relevance IN ('high','medium','low','unknown')
    ),
    verification_hint text CHECK (verification_hint IN ('F0','F1','F2','F3','F4')),
    publication_status text NOT NULL CHECK (
        publication_status IN ('raw_only','staged','under_review','quarantined')
    ),
    processing_status text NOT NULL CHECK (
        processing_status IN ('needs_review','quarantined')
    ),
    review_flags jsonb NOT NULL DEFAULT '[]'::jsonb,
    submitted_payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ingestion_records_status_created_idx
    ON ingestion_records (processing_status, created_at DESC);
CREATE INDEX ingestion_records_document_version_idx
    ON ingestion_records (document_version_id);
CREATE INDEX ingestion_records_source_hash_idx
    ON ingestion_records (source_id, content_hash);

INSERT INTO schema_migrations (filename)
VALUES ('0002_ingestion_records.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
