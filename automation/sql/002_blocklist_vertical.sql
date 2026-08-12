-- 002_blocklist_vertical.sql  ·  Task 0, item 4
-- Makes the keyword blocklist vertical-aware AND field-aware.
--
-- Two problems this fixes:
--   1. feed_blocklist is global: every term suppresses matching titles in all jobs.
--      Security's blocklist is security-scoped and must NOT suppress warehouse jobs,
--      and warehouse terms must not touch security rows.
--   2. Suppression matched on TITLE only. Staffing FIRMS (Integrity Staffing,
--      PeopleReady, Adecco, Elwood Staffing, ...) live in the COMPANY field, not the
--      title, so firm-level blocklisting needs a company match.
--
-- Design:
--   vertical  text NULL      NULL -> applies to ALL verticals (reserved; none today).
--                            'x'  -> suppresses only jobs whose vertical = 'x'.
--   field     text NOT NULL  'title' (default) or 'company' -> which column the term
--             DEFAULT 'title' is matched against (ilike *term*).
-- Existing terms are all security title-keywords, so they backfill to
-- vertical='security', field='title'.
--
-- Run once in the Supabase SQL editor, AFTER 001. Safe to re-run.

ALTER TABLE feed_blocklist
  ADD COLUMN IF NOT EXISTS vertical text;

UPDATE feed_blocklist
  SET vertical = 'security'
  WHERE vertical IS NULL;

ALTER TABLE feed_blocklist
  ADD COLUMN IF NOT EXISTS field text NOT NULL DEFAULT 'title';

-- Data-integrity guard; the ingest also whitelists the value before querying.
ALTER TABLE feed_blocklist
  DROP CONSTRAINT IF EXISTS feed_blocklist_field_chk;
ALTER TABLE feed_blocklist
  ADD CONSTRAINT feed_blocklist_field_chk CHECK (field IN ('title', 'company'));
