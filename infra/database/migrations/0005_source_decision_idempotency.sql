BEGIN;

ALTER TABLE source_decisions
    ADD COLUMN idempotency_key text,
    ADD COLUMN request_fingerprint text;

UPDATE source_decisions
SET idempotency_key = 'legacy:' || public_id,
    request_fingerprint = 'legacy:' || public_id
WHERE idempotency_key IS NULL OR request_fingerprint IS NULL;

ALTER TABLE source_decisions
    ALTER COLUMN idempotency_key SET NOT NULL,
    ALTER COLUMN request_fingerprint SET NOT NULL,
    ADD CONSTRAINT source_decisions_idempotency_key_unique UNIQUE (idempotency_key);

INSERT INTO schema_migrations (filename)
VALUES ('0005_source_decision_idempotency.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
