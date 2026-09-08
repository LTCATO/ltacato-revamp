-- Run in Supabase SQL editor after sql/visit_schedule_visitors.sql. Idempotent.
-- Requiring a name + origin + sex for every single companion turned out to
-- be too much friction — gender is now captured as a simple male/female
-- headcount on visit_schedules itself (typed exactly, must add up to
-- party_size), not per person. This table now only holds whatever optional
-- name/origin detail a visitor chose to add for the rest of their party;
-- both are optional, and per-visitor gender is no longer collected at all.

ALTER TABLE visit_schedule_visitors ALTER COLUMN full_name DROP NOT NULL;
ALTER TABLE visit_schedule_visitors ALTER COLUMN origin DROP NOT NULL;
ALTER TABLE visit_schedule_visitors ALTER COLUMN gender DROP NOT NULL;
