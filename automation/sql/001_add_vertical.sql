-- 001_add_vertical.sql  ·  Task 0, item 3
-- Adds a `vertical` column to the jobs table so a job's vertical is captured at
-- ingest (bbj_feed_fetch.normalize sets it from the query, never inferred from the
-- title). Existing rows are all security, so they backfill to 'security'.
--
-- Written to be idempotent AND to repair a column that was already added as a bare
-- nullable text (which is the state we found: column present, every row NULL). A
-- plain `ADD COLUMN IF NOT EXISTS ... NOT NULL DEFAULT` is a NO-OP once the column
-- exists, so it never applies the default/not-null to an existing nullable column.
-- The explicit backfill + ALTER steps below fix that case too.
--
-- Run once in the Supabase SQL editor. Safe to re-run.

ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS vertical text;

-- Backfill: every pre-warehouse row is security.
UPDATE jobs
  SET vertical = 'security'
  WHERE vertical IS NULL;

-- Now that no NULLs remain, apply the default + NOT NULL to guard future rows.
ALTER TABLE jobs
  ALTER COLUMN vertical SET DEFAULT 'security';
ALTER TABLE jobs
  ALTER COLUMN vertical SET NOT NULL;

-- Feed selection will filter by vertical (Task 1); index the column now.
CREATE INDEX IF NOT EXISTS jobs_vertical_idx ON jobs (vertical);
