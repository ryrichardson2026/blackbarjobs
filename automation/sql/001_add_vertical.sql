-- 001_add_vertical.sql  ·  Task 0, item 3
-- Adds a `vertical` column to the jobs table so a job's vertical is captured at
-- ingest (bbj_feed_fetch.normalize sets it from the query, never inferred from the
-- title). Existing rows backfill to 'security' via the DEFAULT, so nothing that
-- powers current security traffic changes.
--
-- Run once in the Supabase SQL editor. Safe to re-run: guarded with IF NOT EXISTS.

ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS vertical text NOT NULL DEFAULT 'security';

-- Feed selection will filter by vertical (Task 1); index the column now.
CREATE INDEX IF NOT EXISTS jobs_vertical_idx ON jobs (vertical);
