/**
 * inject-footer-links.js
 * BlackBarJobs — Injects footer site links into pages missing them
 *
 * USAGE:
 * 1. Drop this file in your repo root (same folder as index.html)
 * 2. Run: node inject-footer-links.js
 * 3. Safe to re-run — skips files that already have footer links
 */

const fs   = require('fs');
const path = require('path');

// Folders to scan — root and jobs subfolder
const SCAN_DIRS = ['.', 'jobs'];

const FOOTER_CSS = `
  .footer-links { margin-bottom: 10px; display: flex; flex-wrap: wrap; justify-content: center; gap: 4px 2px; font-size: 0.72rem; }
  .footer-links a { color: var(--muted, #6b7280); text-decoration: none; }
  .footer-links a:hover { text-decoration: underline; }
  .footer-links span { color: #d1d5db; }`;

const FOOTER_HTML = `
  <!-- Site Links -->
  <div class="footer-links">
    <a href="/security-jobs-dfw">DFW Security Jobs</a>
    <span>·</span>
    <a href="/jobs/security-officer-jobs-dallas">Dallas Security Jobs</a>
    <span>·</span>
    <a href="/jobs/armed-security-dfw">Armed Security</a>
    <span>·</span>
    <a href="/jobs/unarmed-security-dfw">Unarmed Security</a>
    <span>·</span>
    <a href="/jobs/overnight-security-dfw">Overnight Security</a>
    <span>·</span>
    <a href="/jobs/event-security-dfw">Event Security</a>
    <span>·</span>
    <a href="/texas-security-license-requirements">TX License Guide</a>
  </div>`;

function injectFooter(filePath) {
  const fileName = path.relative('.', filePath);
  let html = fs.readFileSync(filePath, 'utf8');

  // Skip if already has footer links
  if (html.includes('footer-links')) {
    console.log(`  SKIP  ${fileName} — already has footer links`);
    return;
  }

  // Skip if no footer tag
  if (!html.includes('<footer>')) {
    console.log(`  SKIP  ${fileName} — no footer tag found`);
    return;
  }

  // Inject CSS before closing </style>
  if (!html.includes('.footer-links')) {
    html = html.replace('</style>', FOOTER_CSS + '\n</style>');
  }

  // Inject HTML at start of <footer>
  html = html.replace('<footer>', '<footer>' + FOOTER_HTML);

  fs.writeFileSync(filePath, html, 'utf8');
  console.log(`  OK    ${fileName}`);
}

console.log('\nBlackBarJobs — Inject Footer Links\n');

let total = 0;
SCAN_DIRS.forEach(dir => {
  if (!fs.existsSync(dir)) return;
  fs.readdirSync(dir)
    .filter(f => f.endsWith('.html'))
    .forEach(f => {
      injectFooter(path.join(dir, f));
      total++;
    });
});

console.log(`\nDone. Scanned ${total} files.\n`);
