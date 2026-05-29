/**
 * inject-sticky-bar.js
 * BlackBarJobs — Injects mobile sticky CTA bar into all SEO pages
 *
 * USAGE:
 * 1. Drop this file in your repo folder (same folder as your HTML files)
 * 2. Run: node inject-sticky-bar.js
 * 3. All .html files get the sticky bar injected
 * 4. Safe to re-run — skips files that already have it
 */

const fs   = require('fs');
const path = require('path');

const HTML_DIR = '.';

// ─── STICKY BAR CSS ───────────────────────────────────────────────────────────

const STICKY_CSS = `
  /* ── MOBILE STICKY BAR ── */
  .sticky-bar {
    display: none !important;
    position: fixed;
    bottom: 0; left: 0; right: 0;
    z-index: 99;
    padding: 10px 16px 16px;
    background: var(--navy-deep);
    border-top: 1px solid rgba(255,195,0,0.25);
    box-shadow: 0 -4px 20px rgba(0,0,0,0.4);
  }
  @media (max-width: 639px) {
    .sticky-bar.visible { display: block !important; }
    .sticky-bar a {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      padding: 14px;
      background: var(--gold);
      color: var(--navy-deep);
      font-family: 'Barlow Condensed', sans-serif;
      font-size: 1.1rem;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      border-radius: 10px;
      text-decoration: none;
    }
    body { padding-bottom: 74px; }
  }`;

// ─── STICKY BAR HTML ──────────────────────────────────────────────────────────

const STICKY_HTML = `
<!-- Mobile Sticky CTA Bar -->
<div class="sticky-bar" id="stickyBar">
  <a href="#alerts">Get Security Job Alerts</a>
</div>`;

// ─── STICKY BAR JS ────────────────────────────────────────────────────────────

const STICKY_JS = `
  // Mobile sticky bar — shows when hero scrolls out of view
  (function() {
    var bar = document.getElementById('stickyBar');
    if (!bar) return;
    var hero = document.querySelector('.hero');
    if (!hero) return;
    var observer = new IntersectionObserver(function(entries) {
      entries[0].isIntersecting
        ? bar.classList.remove('visible')
        : bar.classList.add('visible');
    }, { threshold: 0.1 });
    observer.observe(hero);
  })();`;

// ─── INJECT ───────────────────────────────────────────────────────────────────

function injectStickyBar(filePath) {
  const fileName = path.basename(filePath);

  // Skip the homepage and index — they have their own sticky bar
  if (['index.html', 'security-jobs-dfw.html'].includes(fileName)) {
    console.log(`  SKIP  ${fileName} — excluded`);
    return;
  }

  let html = fs.readFileSync(filePath, 'utf8');

  // Skip if already injected
  if (html.includes('stickyBar')) {
    console.log(`  SKIP  ${fileName} — already has sticky bar`);
    return;
  }

  // 1. Inject CSS before closing </style>
  html = html.replace('</style>', STICKY_CSS + '\n</style>');

  // 2. Inject HTML after <body> noscript tag (after GTM noscript)
  html = html.replace(
    '<!-- End Google Tag Manager (noscript) -->',
    '<!-- End Google Tag Manager (noscript) -->' + STICKY_HTML
  );

  // 3. Inject JS before closing </script> tag at end of file
  html = html.replace(
    /(<\/script>\s*<\/body>)/,
    STICKY_JS + '\n$1'
  );

  fs.writeFileSync(filePath, html, 'utf8');
  console.log(`  OK    ${fileName}`);
}

// ─── RUN ──────────────────────────────────────────────────────────────────────

console.log('\nBlackBarJobs — Inject Mobile Sticky Bar\n');

const files = fs.readdirSync(HTML_DIR)
  .filter(f => f.endsWith('.html'))
  .map(f => path.join(HTML_DIR, f));

console.log(`Found ${files.length} HTML file(s):\n`);
files.forEach(injectStickyBar);

console.log('\nDone. Upload all updated files to GitHub.\n');
