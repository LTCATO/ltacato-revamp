-- Run in Supabase SQL editor. Idempotent.
-- Lets a citizen attach a photo (e.g. a scanned ID or supporting document)
-- to a Citizen's Charter service request, so they can see what they sent
-- when they check "My Requests" later.

ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS attachment_url TEXT;
