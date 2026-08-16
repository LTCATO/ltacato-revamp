-- Run in Supabase SQL editor. Idempotent.
-- Adds the paid "Featured" request workflow. events.approval_status already
-- supports 'pending'/'approved'/'rejected' (existing CHECK constraint) --
-- LGU-created events will now actually use 'pending' instead of always
-- being inserted as 'approved'.

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS featured_status TEXT NOT NULL DEFAULT 'none',
    ADD COLUMN IF NOT EXISTS featured_payment_reference TEXT,
    ADD COLUMN IF NOT EXISTS featured_requested_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS featured_reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS featured_reviewed_by UUID;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'events_featured_status_check') THEN
        ALTER TABLE events ADD CONSTRAINT events_featured_status_check
            CHECK (featured_status IN ('none', 'requested', 'approved', 'rejected'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'events_featured_reviewed_by_fkey') THEN
        ALTER TABLE events ADD CONSTRAINT events_featured_reviewed_by_fkey
            FOREIGN KEY (featured_reviewed_by) REFERENCES profiles(id);
    END IF;
END $$;
