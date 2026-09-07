-- Run in Supabase SQL editor after sql/visit_schedules_v2.sql. Idempotent.
-- A visit_schedules row (whether an online "Schedule a visit" request or a
-- manual walk-in log) can cover a whole party (party_size > 1), but only
-- ever recorded one visitor_name plus aggregate male_count/female_count for
-- the group. That's not enough to identify who was actually on site if
-- something happens to them — this table records every visitor in the
-- party individually (name, origin, sex), one row each.
--
-- visit_schedules.origin/male_count/female_count are kept as-is and are
-- now derived from this table on save (majority origin + summed genders),
-- so the existing arrivals dashboard and DTA3 export keep working
-- unchanged off the aggregate columns.

CREATE TABLE IF NOT EXISTS visit_schedule_visitors (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    visit_schedule_id BIGINT NOT NULL,
    full_name TEXT NOT NULL,
    origin TEXT NOT NULL,
    gender TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'visit_schedule_visitors_visit_schedule_id_fkey') THEN
        ALTER TABLE visit_schedule_visitors ADD CONSTRAINT visit_schedule_visitors_visit_schedule_id_fkey
            FOREIGN KEY (visit_schedule_id) REFERENCES visit_schedules(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'visit_schedule_visitors_origin_check') THEN
        ALTER TABLE visit_schedule_visitors ADD CONSTRAINT visit_schedule_visitors_origin_check
            CHECK (origin IN ('this_city', 'other_city', 'other_province', 'foreign'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'visit_schedule_visitors_gender_check') THEN
        ALTER TABLE visit_schedule_visitors ADD CONSTRAINT visit_schedule_visitors_gender_check
            CHECK (gender IN ('male', 'female'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_visit_schedule_visitors_visit_schedule_id
    ON visit_schedule_visitors (visit_schedule_id);
