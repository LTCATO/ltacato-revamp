-- Run in Supabase SQL editor after sql/visit_schedules.sql. Idempotent.
-- Drops the "one active visit per spot+email" restriction (a visit is now
-- just a log entry, repeats/walk-ins are fine) and adds the fields needed
-- to derive LTCATO arrival reports from real visit logs instead of manual
-- entry: category/nights, origin+gender breakdown, check-in timestamp,
-- and manual (walk-in) log bookkeeping.

ALTER TABLE visit_schedules ALTER COLUMN visitor_email DROP NOT NULL;
DROP INDEX IF EXISTS uq_visit_schedules_active_per_spot_email;

ALTER TABLE visit_schedules
    ADD COLUMN IF NOT EXISTS visitor_category TEXT NOT NULL DEFAULT 'day_tour',
    ADD COLUMN IF NOT EXISTS overnight_nights INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS origin TEXT,
    ADD COLUMN IF NOT EXISTS male_count INTEGER,
    ADD COLUMN IF NOT EXISTS female_count INTEGER,
    ADD COLUMN IF NOT EXISTS arrived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_manual BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS logged_by UUID;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'visit_schedules_visitor_category_check') THEN
        ALTER TABLE visit_schedules ADD CONSTRAINT visit_schedules_visitor_category_check
            CHECK (visitor_category IN ('day_tour', 'overnight'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'visit_schedules_origin_check') THEN
        ALTER TABLE visit_schedules ADD CONSTRAINT visit_schedules_origin_check
            CHECK (origin IS NULL OR origin IN ('this_city', 'other_city', 'other_province', 'foreign'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'visit_schedules_logged_by_fkey') THEN
        ALTER TABLE visit_schedules ADD CONSTRAINT visit_schedules_logged_by_fkey
            FOREIGN KEY (logged_by) REFERENCES profiles(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_visit_schedules_arrived_at ON visit_schedules (arrived_at);
