BEGIN;

CREATE TABLE trade_indicator_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'TIB-%'),
    ingestion_record_id uuid NOT NULL REFERENCES ingestion_records(id),
    source_id uuid NOT NULL REFERENCES sources(id),
    document_version_id uuid NOT NULL REFERENCES document_versions(id),
    dataset_id text NOT NULL CHECK (dataset_id = 'trade_sitc_1d'),
    fact_level text NOT NULL CHECK (fact_level IN ('F0','F1','F2','F3','F4')),
    status text NOT NULL DEFAULT 'canonical_private' CHECK (
        status IN ('canonical_private', 'published', 'rejected')
    ),
    observation_count integer NOT NULL CHECK (observation_count > 0),
    processed_by text NOT NULL,
    rule_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ingestion_record_id, rule_version)
);

CREATE TABLE trade_indicator_observations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL REFERENCES trade_indicator_batches(id),
    period date NOT NULL CHECK (extract(day from period) = 1),
    sitc_section text NOT NULL CHECK (
        sitc_section IN ('overall','0','1','2','3','4','5','6','7','8','9')
    ),
    exports_rm_million numeric NOT NULL CHECK (exports_rm_million >= 0),
    imports_rm_million numeric NOT NULL CHECK (imports_rm_million >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (batch_id, period, sitc_section)
);

CREATE TABLE trade_indicator_publications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id text NOT NULL UNIQUE CHECK (public_id LIKE 'TIP-%'),
    batch_id uuid NOT NULL UNIQUE REFERENCES trade_indicator_batches(id),
    revision bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    idempotency_key text NOT NULL UNIQUE,
    request_fingerprint text NOT NULL,
    projection jsonb NOT NULL,
    publisher_id text NOT NULL,
    reason text NOT NULL CHECK (length(trim(reason)) >= 8),
    rule_version text NOT NULL,
    is_current boolean NOT NULL DEFAULT true,
    published_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX trade_indicator_publications_current_idx
    ON trade_indicator_publications (is_current) WHERE is_current;
CREATE INDEX trade_indicator_observations_period_idx
    ON trade_indicator_observations (period DESC, sitc_section);

INSERT INTO schema_migrations (filename)
VALUES ('0006_trade_indicators.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
