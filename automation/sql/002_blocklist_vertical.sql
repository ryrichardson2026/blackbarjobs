-- 002_blocklist_vertical.sql  ·  Task 0, item 4
-- Makes the keyword blocklist vertical-aware. Today feed_blocklist is global: every
-- term suppresses matching titles in all jobs. Security's blocklist is security-
-- scoped and must NOT suppress warehouse jobs (a "guard" term would wrongly kill a
-- warehouse "guard shack" posting, etc.), and warehouse staffing-firm terms must not
-- touch security rows.
--
-- Design: a nullable `vertical` column.
--   * vertical IS NULL  -> term applies to ALL verticals (reserved for future shared
--                          terms; none today).
--   * vertical = 'x'    -> term suppresses only jobs whose vertical = 'x'.
-- All existing terms are backfilled to 'security' (they were authored for security).
--
-- Run once in the Supabase SQL editor, AFTER 001. Safe to re-run.

ALTER TABLE feed_blocklist
  ADD COLUMN IF NOT EXISTS vertical text;

-- Existing terms are security-only. (NULL is reserved for all-vertical terms.)
UPDATE feed_blocklist
  SET vertical = 'security'
  WHERE vertical IS NULL;
