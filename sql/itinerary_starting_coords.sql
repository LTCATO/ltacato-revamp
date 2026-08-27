-- Saved itineraries only kept the starting point's text label, not its
-- coordinates, so the "Get Directions" recommendation on the first stop of
-- day 1 disappeared as soon as an itinerary was saved and reloaded.
ALTER TABLE public.itineraries
    ADD COLUMN IF NOT EXISTS starting_lat double precision,
    ADD COLUMN IF NOT EXISTS starting_lng double precision;
