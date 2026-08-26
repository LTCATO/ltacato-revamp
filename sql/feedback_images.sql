-- Allow tourists to attach photos to their spot/event reviews.
ALTER TABLE public.feedbacks
    ADD COLUMN IF NOT EXISTS images text[] DEFAULT '{}'::text[];

ALTER TABLE public.event_feedbacks
    ADD COLUMN IF NOT EXISTS images text[] DEFAULT '{}'::text[];
