-- Run in Supabase SQL editor. Idempotent.
-- Lets an establishment owner hide a bad review from their spot's public
-- page without deleting it — the row (and its rating, for the average) is
-- kept for LGU/LTCATO oversight, it's just excluded from the public feed.

ALTER TABLE public.feedbacks
    ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS hidden_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS hidden_by UUID;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'feedbacks_hidden_by_fkey') THEN
        ALTER TABLE public.feedbacks ADD CONSTRAINT feedbacks_hidden_by_fkey
            FOREIGN KEY (hidden_by) REFERENCES public.profiles(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_feedbacks_is_hidden ON public.feedbacks (is_hidden);
