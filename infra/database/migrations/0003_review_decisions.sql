BEGIN;

ALTER TABLE ingestion_records
    DROP CONSTRAINT ingestion_records_processing_status_check;

ALTER TABLE ingestion_records
    ADD CONSTRAINT ingestion_records_processing_status_check CHECK (
        processing_status IN (
            'needs_review', 'in_review', 'approved', 'returned', 'rejected', 'quarantined'
        )
    );

ALTER TABLE ingestion_records
    DROP CONSTRAINT ingestion_records_publication_status_check;

ALTER TABLE ingestion_records
    ADD CONSTRAINT ingestion_records_publication_status_check CHECK (
        publication_status IN ('raw_only', 'staged', 'under_review', 'rejected', 'quarantined')
    );

CREATE TABLE review_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'DEC-%'),
    review_task_id uuid NOT NULL REFERENCES review_tasks(id),
    actor_id text NOT NULL,
    actor_role text NOT NULL CHECK (
        actor_role IN ('reviewer', 'senior_reviewer', 'publisher', 'security_compliance')
    ),
    decision text NOT NULL CHECK (
        decision IN ('approve', 'approve_with_limits', 'return_for_fix', 'reject', 'quarantine')
    ),
    reason text NOT NULL CHECK (length(trim(reason)) >= 8),
    rule_version text NOT NULL,
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (review_task_id, actor_id)
);

CREATE INDEX review_decisions_task_created_idx
    ON review_decisions (review_task_id, created_at);

INSERT INTO schema_migrations (filename)
VALUES ('0003_review_decisions.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
