BEGIN;

ALTER TABLE sources
    ADD COLUMN robots_status text NOT NULL DEFAULT 'unknown' CHECK (
        robots_status IN ('unknown', 'allowed', 'limited', 'disallowed', 'not_applicable')
    ),
    ADD COLUMN terms_reviewed_at timestamptz,
    ADD COLUMN identity_verified_at timestamptz,
    ADD COLUMN review_due_at timestamptz,
    ADD COLUMN access_notes text;

CREATE TABLE source_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'SRV-%'),
    source_id uuid NOT NULL REFERENCES sources(id),
    actor_id text NOT NULL,
    actor_role text NOT NULL CHECK (actor_role IN ('source_admin', 'system_admin')),
    action text NOT NULL CHECK (
        action IN ('approve_for_trial', 'activate', 'degrade', 'deactivate', 'retire')
    ),
    previous_status text NOT NULL,
    resulting_status text NOT NULL,
    previous_crawl_status text NOT NULL,
    resulting_crawl_status text NOT NULL,
    reason text NOT NULL CHECK (length(trim(reason)) >= 8),
    rule_version text NOT NULL,
    identity_verified boolean NOT NULL DEFAULT false,
    terms_reviewed boolean NOT NULL DEFAULT false,
    authority_scope_reviewed boolean NOT NULL DEFAULT false,
    robots_status text NOT NULL CHECK (
        robots_status IN ('unknown', 'allowed', 'limited', 'disallowed', 'not_applicable')
    ),
    evidence_urls jsonb NOT NULL DEFAULT '[]'::jsonb,
    access_notes text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX source_decisions_source_created_idx
    ON source_decisions (source_id, created_at DESC);

CREATE INDEX sources_review_due_idx
    ON sources (review_due_at)
    WHERE status IN ('trial', 'active', 'degraded');

INSERT INTO schema_migrations (filename)
VALUES ('0004_source_governance.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
