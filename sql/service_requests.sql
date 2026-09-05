-- Run in Supabase SQL editor. Idempotent.
-- Citizen-facing intake for LTCATO's Citizen's Charter frontline services
-- (Tourism Division and History, Arts & Culture Division alike) — the
-- catalog of 8 services lives in services/citizen_charter.py, not in this
-- table; service_title/division here are a snapshot taken at submission
-- time so a later edit to the charter text doesn't rewrite past requests.

CREATE TABLE IF NOT EXISTS service_requests (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service_number INTEGER NOT NULL CHECK (service_number BETWEEN 1 AND 8),
    service_title TEXT NOT NULL,
    division TEXT NOT NULL CHECK (division IN ('Tourism', 'History, Arts & Culture')),
    tourist_id UUID REFERENCES profiles(id),
    requester_name TEXT NOT NULL,
    requester_email TEXT NOT NULL,
    requester_phone TEXT,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'under_review', 'responded')),
    staff_response TEXT,
    handled_by UUID REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_service_requests_status ON service_requests (status);
CREATE INDEX IF NOT EXISTS idx_service_requests_tourist_id ON service_requests (tourist_id);
CREATE INDEX IF NOT EXISTS idx_service_requests_created_at ON service_requests (created_at DESC);
