-- Run in Supabase SQL editor. Tourist "Schedule Visit" appointment requests per tourist spot.
-- Safe to re-run: uses IF NOT EXISTS everywhere, including for the foreign keys below.

CREATE TABLE IF NOT EXISTS visit_schedules (
    id BIGSERIAL PRIMARY KEY,
    tourist_spot_id BIGINT NOT NULL REFERENCES tourist_spots(id),
    tourist_id UUID REFERENCES profiles(id),
    visitor_name TEXT NOT NULL,
    visitor_email TEXT NOT NULL,
    visitor_phone TEXT,
    visit_date DATE NOT NULL,
    visit_time TIME NOT NULL,
    party_size INTEGER NOT NULL DEFAULT 1 CHECK (party_size > 0),
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'declined', 'completed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Foreign keys are required for Supabase/PostgREST to auto-embed
-- tourist_spots(...) / profiles(...) in .select() calls (same reason
-- arrival_reports/feedbacks can embed tourist_spots). If the table was
-- already created by an earlier run of this script without them, add
-- them now.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'visit_schedules_tourist_spot_id_fkey'
    ) THEN
        ALTER TABLE visit_schedules
            ADD CONSTRAINT visit_schedules_tourist_spot_id_fkey
            FOREIGN KEY (tourist_spot_id) REFERENCES tourist_spots(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'visit_schedules_tourist_id_fkey'
    ) THEN
        ALTER TABLE visit_schedules
            ADD CONSTRAINT visit_schedules_tourist_id_fkey
            FOREIGN KEY (tourist_id) REFERENCES profiles(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_visit_schedules_spot_status
    ON visit_schedules (tourist_spot_id, status);

CREATE INDEX IF NOT EXISTS idx_visit_schedules_email
    ON visit_schedules (visitor_email);

CREATE INDEX IF NOT EXISTS idx_visit_schedules_tourist
    ON visit_schedules (tourist_id);

-- Enforces "no second active visit for the same spot+email" at the DB level,
-- not just via an app-side check-then-insert (which would race under concurrent submits).
CREATE UNIQUE INDEX IF NOT EXISTS uq_visit_schedules_active_per_spot_email
    ON visit_schedules (tourist_spot_id, visitor_email)
    WHERE status IN ('pending', 'confirmed');
