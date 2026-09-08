-- Run in Supabase SQL editor. Idempotent.
-- Mirrors sql/feedback_hide.sql for event_feedbacks: lets LGU/LTCATO staff
-- hide a bad event review from the event's public page without deleting it
-- — the row (and its rating, for the average) is kept for oversight, it's
-- just excluded from the public feed. There's no establishment-owner
-- equivalent here since events belong to an LGU (or to LTCATO itself, when
-- lgu_id is null) rather than to an individual establishment.

ALTER TABLE public.event_feedbacks
    ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS hidden_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS hidden_by UUID;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'event_feedbacks_hidden_by_fkey') THEN
        ALTER TABLE public.event_feedbacks ADD CONSTRAINT event_feedbacks_hidden_by_fkey
            FOREIGN KEY (hidden_by) REFERENCES public.profiles(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_event_feedbacks_is_hidden ON public.event_feedbacks (is_hidden);
