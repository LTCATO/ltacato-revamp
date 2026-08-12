-- Run in Supabase SQL editor. Idempotent.
-- Existing duplicate/draft rows were already cleaned up directly (dev/test
-- artifacts from spot #36, confirmed and removed before this migration).
--
-- Adds:
--   - arrival_reports.updated_at, so regeneration is auditable
--   - a uniqueness constraint on (spot, category, report_type, report_date)
--     so generating the same report twice UPDATEs instead of duplicating
--   - visit_schedules.source, an explicit source-of-record field
--     (scheduled / walk_in / manual / imported) alongside the existing
--     is_manual flag, matching the SCHEDULED/WALK_IN/MANUAL/IMPORTED
--     vocabulary used across the reporting revision.

ALTER TABLE arrival_reports ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
UPDATE arrival_reports SET updated_at = created_at WHERE updated_at IS NULL;
ALTER TABLE arrival_reports ALTER COLUMN updated_at SET DEFAULT NOW();
ALTER TABLE arrival_reports ALTER COLUMN updated_at SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'arrival_reports_unique_period'
    ) THEN
        ALTER TABLE arrival_reports ADD CONSTRAINT arrival_reports_unique_period
            UNIQUE (tourist_spot_id, visitor_category, report_type, report_date);
    END IF;
END $$;

ALTER TABLE visit_schedules ADD COLUMN IF NOT EXISTS source TEXT;
UPDATE visit_schedules SET source = CASE WHEN is_manual THEN 'walk_in' ELSE 'scheduled' END
    WHERE source IS NULL;
ALTER TABLE visit_schedules ALTER COLUMN source SET DEFAULT 'scheduled';
ALTER TABLE visit_schedules ALTER COLUMN source SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'visit_schedules_source_check'
    ) THEN
        ALTER TABLE visit_schedules ADD CONSTRAINT visit_schedules_source_check
            CHECK (source IN ('scheduled', 'walk_in', 'manual', 'imported'));
    END IF;
END $$;
