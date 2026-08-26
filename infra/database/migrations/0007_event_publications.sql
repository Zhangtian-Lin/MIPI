BEGIN;

ALTER TABLE events
    ADD COLUMN attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN rule_version text,
    ADD COLUMN created_by text,
    ADD COLUMN projection_idempotency_key text,
    ADD COLUMN projection_fingerprint text;

CREATE UNIQUE INDEX events_projection_idempotency_idx
    ON events (projection_idempotency_key)
    WHERE projection_idempotency_key IS NOT NULL;

CREATE TABLE event_publications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'EVP-%'),
    event_id uuid NOT NULL REFERENCES events(id),
    revision integer NOT NULL CHECK (revision > 0),
    projection jsonb NOT NULL,
    publisher_id text NOT NULL,
    publication_reason text NOT NULL CHECK (length(trim(publication_reason)) >= 8),
    rule_version text NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    request_fingerprint text NOT NULL,
    is_current boolean NOT NULL DEFAULT true,
    published_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_id, revision)
);

CREATE UNIQUE INDEX event_publications_current_idx
    ON event_publications (event_id)
    WHERE is_current;
CREATE INDEX event_publications_date_idx
    ON event_publications ((projection->>'event_date') DESC, published_at DESC)
    WHERE is_current;

INSERT INTO schema_migrations (filename)
VALUES ('0007_event_publications.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
