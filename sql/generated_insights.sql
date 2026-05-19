-- Run in Supabase SQL editor. Caches AI-generated spot/event insights for Decision Support.

CREATE TABLE IF NOT EXISTS generated_insights (
    id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('spot', 'event')),
    entity_id BIGINT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_generated_insights_type
    ON generated_insights (entity_type);
