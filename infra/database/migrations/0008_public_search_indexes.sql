BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX event_publications_title_trgm_idx
    ON event_publications USING gin ((projection->>'title_zh') gin_trgm_ops)
    WHERE is_current;

CREATE INDEX event_publications_summary_trgm_idx
    ON event_publications USING gin ((projection->>'summary_zh') gin_trgm_ops)
    WHERE is_current;

INSERT INTO schema_migrations (filename)
VALUES ('0008_public_search_indexes.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
