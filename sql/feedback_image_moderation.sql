-- Review photos are held for moderation before they're shown publicly.
-- Rows without images stay 'approved' by default since there's nothing to
-- moderate; the app sets 'pending' explicitly whenever images are attached.
ALTER TABLE public.feedbacks
    ADD COLUMN IF NOT EXISTS images_approval_status character varying NOT NULL DEFAULT 'approved'
    CHECK (images_approval_status IN ('pending', 'approved', 'rejected'));

ALTER TABLE public.event_feedbacks
    ADD COLUMN IF NOT EXISTS images_approval_status character varying NOT NULL DEFAULT 'approved'
    CHECK (images_approval_status IN ('pending', 'approved', 'rejected'));
