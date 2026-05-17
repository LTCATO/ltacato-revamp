-- Optional database helpers for the tourist itinerary planner.
-- Your existing schema already includes itineraries, itinerary_items, and tourist_passports.
-- Run in Supabase SQL editor only if you need indexes or RLS policies.

-- Speed up "my trips" and dashboard exports
CREATE INDEX IF NOT EXISTS idx_itineraries_tourist_id ON public.itineraries (tourist_id);
CREATE INDEX IF NOT EXISTS idx_itinerary_items_itinerary_id ON public.itinerary_items (itinerary_id);
CREATE INDEX IF NOT EXISTS idx_passport_stamps_passport_id ON public.passport_stamps (passport_id);

-- Example RLS (adjust to your auth setup; service role bypasses RLS)
-- ALTER TABLE public.itineraries ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY itineraries_tourist_select ON public.itineraries
--   FOR SELECT USING (auth.uid() = tourist_id);
-- CREATE POLICY itineraries_tourist_insert ON public.itineraries
--   FOR INSERT WITH CHECK (auth.uid() = tourist_id);
-- CREATE POLICY itineraries_tourist_update ON public.itineraries
--   FOR UPDATE USING (auth.uid() = tourist_id);
-- CREATE POLICY itineraries_tourist_delete ON public.itineraries
--   FOR DELETE USING (auth.uid() = tourist_id);
