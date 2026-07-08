# Link Audit + Less Clicking — Brief

Two things: (1) a real link audit that cross-checks pages, sitemap, and actual on-page links, and
(2) a Claude Code setup that stops it asking you to approve every little step.

---

## PART 1 — The link audit (`bbj_link_audit.py`)

Put `bbj_link_audit.py` in the repo root and run, from the repo folder:

```
python bbj_link_audit.py
python bbj_link_audit.py --csv audit.csv     (also writes a spreadsheet)
```

**What it cross-checks (three sources of truth against each other):**
- Every real page that exists on disk.
- Every internal link written on those pages (`<a href>`).
- Every URL in your sitemap(s).

**What it reports:**
- **A) Broken internal links** — a page links to an internal URL that has no real page. This is the
  Houston 404 cause. For each one it AUTO-SUGGESTS the correct target by matching slug words, so
  `houston-armed-security` -> `armed-security-houston` is found for you. **That suggestion list is your
  redirect/fix map, for every metro at once**, not just Houston.
- **B) Dead sitemap URLs** — sitemap entries that point at a 404 (tells Google to crawl dead pages).
- **C) Pages missing from the sitemap** — real pages Google may never discover.
- **D) Orphan pages** — real pages nothing links to.

**Why this supersedes the hand-written Houston 404 map:** the audit generates the complete old-URL ->
real-URL mapping across Houston, San Antonio, Dallas, and Austin in one pass, with the fix already
suggested. You don't hand-map anything.

### How to act on it (hand this loop to Claude Code)
1. Run the audit. Section A is the fix list.
2. For each broken link, two fixes (do both):
   - **Redirect:** add `{ "source": "<dead url>", "destination": "<suggested real url>", "permanent": true }`
     to the `redirects` array in `vercel.json`. Merge, do not overwrite the file.
   - **Fix the internal link:** repoint the `href` on the linking page(s) at the real URL, so users and
     Googlebot stop hitting the dead end. The audit lists which pages link to each dead target.
3. For **San Antonio** dead targets whose suggestion points back at the *same* slug (the page 404s at
   its own correct address), the fix is to **restore/rebuild that page**, not redirect it. Those pages
   were ranking at their own URL (e.g. `university-security-san-antonio` at position 4).
4. Regenerate the sitemap so it lists only real URLs (fixes section B and C).
5. Re-run `bbj_link_audit.py` and confirm sections A and B are zero.

Note: `bbj_page_check.py` (content health) and `bbj_link_audit.py` (link/URL health) are complementary.
Run both after any batch of page work.

---

## PART 2 — Stop Claude Code asking you to approve everything

The reason it asks constantly is that the default mode confirms before every edit and command. You fix
that by telling it, once, what's safe, so the routine stuff runs silently and only the risky stuff stops.
This does NOT mean "approve everything." The one gate you keep is the deploy: nothing reaches production
without your review.

### Create one file: `.claude/settings.local.json` in the repo
(This file is personal and gitignored, so it only affects your machine.)

```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Read(**)", "Grep(**)", "Glob(**)",
      "Bash(python *)", "Bash(python3 *)",
      "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(git show*)",
      "Bash(git add*)", "Bash(git commit *)",
      "Bash(git branch*)", "Bash(git checkout*)", "Bash(git switch*)",
      "Bash(ls *)", "Bash(cat *)", "Bash(dir*)", "Bash(type *)", "Bash(findstr *)", "Bash(rg *)"
    ],
    "ask": [
      "Bash(git push*)",
      "Bash(git merge*)"
    ],
    "deny": [
      "Bash(git push --force*)", "Bash(git push -f*)",
      "Bash(git reset --hard*)",
      "Bash(rm *)", "Bash(rm -rf *)", "Bash(del *)",
      "Bash(curl *)", "Bash(wget *)",
      "Bash(npm install*)", "Bash(pip install*)",
      "Bash(vercel *)", "Bash(*deploy*)",
      "Read(.env)", "Read(./.env*)", "Read(**/.env*)"
    ]
  }
}
```

**What this does, in plain terms:**
- **`acceptEdits`** — Claude Code edits repo files without asking each time. This kills most of the prompts.
- **allow list** — reading, searching, running your `python` audit scripts, and normal git work
  (status, diff, add, commit, branching) all run silently.
- **ask list** — `git push` and `git merge` still stop and ask **once**. This is your deploy gate: it can
  push a branch to get you a Vercel preview, but it pauses so you decide when something goes out.
- **deny list** — things that never run automatically: force-push, hard reset, deleting/moving files,
  network fetches, installs, direct Vercel deploys, and reading your `.env` secrets
  (`SEARCHAPI_KEY`, `SUPABASE_SERVICE_KEY`). Deny always wins and can't be overridden.

Rules evaluate deny -> ask -> allow, so the dangerous list is always safe even alongside broad allows.

### Add a short "how to work" block to `CLAUDE.md`
So it self-drives the loop instead of pausing between every step:

```
## Working autonomously
- Run the full loop end to end without pausing between steps: branch -> make the surgical edits ->
  run the relevant audit (bbj_page_check.py / bbj_link_audit.py) -> commit.
- Only stop to ask when: (1) about to git push or merge, (2) a fix is genuinely ambiguous, or
  (3) a change would touch working functionality.
- After any page or link change, re-run the audits and report the before/after counts.
- Surgical edits only. Branch first. Never edit on main.
```

### Two in-session helpers
- Type `/permissions` inside Claude Code to see and edit the active rules any time.
- Type `/fewer-permission-prompts` and it will review what you've been approving and suggest safe
  additions to the allow list.

### What NOT to do
Do not use `--dangerously-skip-permissions` to escape the prompts. That removes the deploy gate and the
`.env` protection too. The settings file above gets you the quiet experience without handing over the keys.

---

## Net effect
You run the audit, hand Claude Code the fix loop, and it works through the whole batch, editing, running
audits, committing, and only stopping when it's time to push. You go from approving dozens of little steps
to approving one thing: the deploy.
