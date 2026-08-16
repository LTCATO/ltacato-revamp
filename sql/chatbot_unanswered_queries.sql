-- Run in Supabase SQL editor. Logs LARA chat questions it couldn't answer
-- (route/spot/event/faq misses), for LTCATO staff to review and promote
-- into chatbot_knowledge FAQ entries.

CREATE TABLE IF NOT EXISTS chatbot_unanswered_queries (
    id BIGSERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL UNIQUE,
    intent TEXT,
    role TEXT,
    miss_count INTEGER NOT NULL DEFAULT 1,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    promoted_knowledge_id BIGINT REFERENCES chatbot_knowledge(id)
);

CREATE INDEX IF NOT EXISTS idx_chatbot_unanswered_last_seen
    ON chatbot_unanswered_queries (last_seen_at DESC);
