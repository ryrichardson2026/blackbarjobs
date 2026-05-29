/**
 * fix-related-links.js
 * BlackBarJobs — Related links deduplication + resources index generator
 *
 * USAGE:
 * 1. Drop this file into your repo folder (same folder as your HTML files)
 * 2. Run: node fix-related-links.js
 * 3. All HTML files will have their related links section rebuilt
 * 4. resources-index.html will be generated/updated
 * 5. Commit everything in one push
 */

const fs   = require('fs');
const path = require('path');

// ─── LIVE PAGE INVENTORY ──────────────────────────────────────────────────────
// Single source of truth. Add new pages here as you build them.
// related: which other pages to show in this page's related links section.
// Max 8 related links per page — ordered by relevance.

const PAGES = [

  // ── DFW CATEGORY PAGES ──
  {
    file:     null, // hosted separately, not in this repo folder
    url:      '/jobs/overnight-security-dfw',
    label:    '🌙 Overnight Security Jobs — DFW',
    category: 'dfw',
    type:     'overnight',
  },
  {
    file:     null,
    url:      '/jobs/armed-security-dfw',
    label:    '🛡️ Armed Security Jobs — DFW',
    category: 'dfw',
    type:     'armed',
  },
  {
    file:     null,
    url:      '/jobs/unarmed-security-dfw',
    label:    '👮 Unarmed Security Jobs — DFW',
    category: 'dfw',
    type:     'unarmed',
  },
  {
    file:     null,
    url:      '/jobs/event-security-dfw',
    label:    '🎟️ Event Security Jobs — DFW',
    category: 'dfw',
    type:     'event',
  },
  {
    file:     null,
    url:      '/jobs/tsa-airport-security-dfw',
    label:    '✈️ TSA & Airport Security — DFW',
    category: 'dfw',
    type:     'tsa',
  },
  {
    file:     null,
    url:      '/jobs/loss-prevention-dfw',
    label:    '🏪 Loss Prevention Jobs — DFW',
    category: 'dfw',
    type:     'loss-prevention',
  },

  // ── CITY PAGES ──
  {
    file:     'dallas-overnight-security.html',
    url:      '/jobs/dallas-overnight-security',
    label:    '🌙 Overnight Security — Dallas',
    category: 'city',
    type:     'overnight',
    city:     'dallas',
    related:  [
      '/jobs/overnight-security-dfw',
      '/jobs/armed-security-dfw',
      '/jobs/unarmed-security-dfw',
      '/jobs/event-security-dfw',
      '/jobs/loss-prevention-dfw',
      '/jobs/tsa-airport-security-dfw',
      '/jobs/fort-worth-overnight-security-jobs',
      '/jobs/irving-overnight-security-jobs',
    ],
  },
  {
    file:     'fort-worth-overnight-security-jobs.html',
    url:      '/jobs/fort-worth-overnight-security-jobs',
    label:    '🌙 Overnight Security — Fort Worth',
    category: 'city',
    type:     'overnight',
    city:     'fort-worth',
    related:  [
      '/jobs/overnight-security-dfw',
      '/jobs/armed-security-dfw',
      '/jobs/unarmed-security-dfw',
      '/jobs/event-security-dfw',
      '/jobs/loss-prevention-dfw',
      '/jobs/tsa-airport-security-dfw',
      '/jobs/dallas-overnight-security',
      '/jobs/grand-prairie-overnight-security-jobs',
    ],
  },
  {
    file:     'irving-overnight-security-jobs.html',
    url:      '/jobs/irving-overnight-security-jobs',
    label:    '🌙 Overnight Security — Irving',
    category: 'city',
    type:     'overnight',
    city:     'irving',
    related:  [
      '/jobs/overnight-security-dfw',
      '/jobs/tsa-airport-security-dfw',
      '/jobs/armed-security-dfw',
      '/jobs/unarmed-security-dfw',
      '/jobs/loss-prevention-dfw',
      '/jobs/event-security-dfw',
      '/jobs/dallas-overnight-security',
      '/jobs/fort-worth-overnight-security-jobs',
    ],
  },
  {
    file:     'grand-prairie-overnight-security-jobs.html',
    url:      '/jobs/grand-prairie-overnight-security-jobs',
    label:    '🌙 Overnight Security — Grand Prairie',
    category: 'city',
    type:     'overnight',
    city:     'grand-prairie',
    related:  [
      '/jobs/overnight-security-dfw',
      '/jobs/armed-security-dfw',
      '/jobs/unarmed-security-dfw',
      '/jobs/loss-prevention-dfw',
      '/jobs/event-security-dfw',
      '/jobs/tsa-airport-security-dfw',
      '/jobs/arlington-event-security-jobs',
      '/jobs/fort-worth-overnight-security-jobs',
    ],
  },
  {
    file:     'arlington-event-security-jobs.html',
    url:      '/jobs/arlington-event-security-jobs',
    label:    '🎟️ Event Security — Arlington',
    category: 'city',
    type:     'event',
    city:     'arlington',
    related:  [
      '/jobs/event-security-dfw',
      '/jobs/unarmed-security-dfw',
      '/jobs/armed-security-dfw',
      '/jobs/overnight-security-dfw',
      '/jobs/loss-prevention-dfw',
      '/jobs/tsa-airport-security-dfw',
      '/jobs/grand-prairie-overnight-security-jobs',
      '/jobs/dallas-overnight-security',
    ],
  },
  {
    file:     'plano-unarmed-security-jobs.html',
    url:      '/jobs/plano-unarmed-security-jobs',
    label:    '👮 Unarmed Security — Plano',
    category: 'city',
    type:     'unarmed',
    city:     'plano',
    related:  [
      '/jobs/unarmed-security-dfw',
      '/jobs/armed-security-dfw',
      '/jobs/overnight-security-dfw',
      '/jobs/loss-prevention-dfw',
      '/jobs/event-security-dfw',
      '/jobs/tsa-airport-security-dfw',
      '/jobs/frisco-unarmed-security-jobs',
      '/jobs/dallas-overnight-security',
    ],
  },
  {
    file:     'frisco-unarmed-security-jobs.html',
    url:      '/jobs/frisco-unarmed-security-jobs',
    label:    '👮 Unarmed Security — Frisco',
    category: 'city',
    type:     'unarmed',
    city:     'frisco',
    related:  [
      '/jobs/unarmed-security-dfw',
      '/jobs/armed-security-dfw',
      '/jobs/overnight-security-dfw',
      '/jobs/event-security-dfw',
      '/jobs/loss-prevention-dfw',
      '/jobs/tsa-airport-security-dfw',
      '/jobs/plano-unarmed-security-jobs',
      '/jobs/dallas-overnight-security',
    ],
  },

  // ── RESOURCE PAGES ──
  {
    file:     'texas-security-license-requirements.html',
    url:      '/texas-security-license-requirements',
    label:    '📋 Texas Security License Requirements',
    category: 'resource',
    type:     'guide',
    related:  [
      '/jobs/overnight-security-dfw',
      '/jobs/unarmed-security-dfw',
      '/jobs/armed-security-dfw',
      '/jobs/event-security-dfw',
      '/jobs/loss-prevention-dfw',
      '/jobs/tsa-airport-security-dfw',
      '/jobs/dallas-overnight-security',
      '/jobs/arlington-event-security-jobs',
    ],
  },
];

// ─── RELATED LINKS HTML BUILDER ───────────────────────────────────────────────

function buildRelatedGrid(relatedUrls) {
  const lookup = {};
  PAGES.forEach(p => { lookup[p.url] = p.label; });

  return relatedUrls.map(url => {
    const label = lookup[url] || url;
    return `      <a href="${url}" class="related-item">
        <span class="related-item-label">${label}</span>
        <span class="related-item-arrow">→</span>
      </a>`;
  }).join('\n');
}

// ─── INJECT INTO HTML FILE ────────────────────────────────────────────────────

function fixRelatedLinks(page) {
  if (!page.file || !page.related) return;

  const filePath = path.join(__dirname, page.file);
  if (!fs.existsSync(filePath)) {
    console.log(`  SKIP  ${page.file} — file not found`);
    return;
  }

  let html = fs.readFileSync(filePath, 'utf8');

  // Find and replace the related-grid div contents
  const gridStart = html.indexOf('<div class="related-grid">');
  const gridEnd   = html.indexOf('</div>', gridStart) + 6;

  if (gridStart === -1) {
    console.warn(`  WARN  ${page.file} — no related-grid found`);
    return;
  }

  const newGrid = `<div class="related-grid">\n${buildRelatedGrid(page.related)}\n    </div>`;
  html = html.slice(0, gridStart) + newGrid + html.slice(gridEnd);

  fs.writeFileSync(filePath, html, 'utf8');
  console.log(`  OK    ${page.file} — ${page.related.length} links`);
}

// ─── RESOURCES INDEX PAGE ─────────────────────────────────────────────────────

function buildResourcesIndex() {
  const dfwPages    = PAGES.filter(p => p.category === 'dfw');
  const cityPages   = PAGES.filter(p => p.category === 'city');
  const resourcePages = PAGES.filter(p => p.category === 'resource');

  function pageCard(p) {
    return `        <a href="${p.url}" class="index-card">
          <span class="index-card-label">${p.label}</span>
          <span class="index-card-arrow">→</span>
        </a>`;
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Security Jobs in Dallas–Fort Worth | BlackBarJobs</title>
<meta name="description" content="Browse all security job listings and resources for the Dallas–Fort Worth area. Overnight, unarmed, armed, event security, loss prevention, and TSA jobs across DFW.">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%23000814'/><text x='50%25' y='50%25' dominant-baseline='central' text-anchor='middle' font-family='Arial Black,sans-serif' font-weight='900' font-size='13' fill='%23FFC300'>BB</text></svg>">
<meta property="og:title" content="Security Jobs in Dallas–Fort Worth | BlackBarJobs">
<meta property="og:url" content="https://www.blackbarjobs.com/security-jobs-dfw">
<meta property="og:type" content="website">
<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-TP9JXK39');</script>
<!-- End Google Tag Manager -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --navy-deep: #000814; --navy-mid: #001D3D; --navy-light: #003566;
    --gold: #FFC300; --gold-hover: #FFD60A; --gold-muted: #E6A800;
    --white: #ffffff; --off-white: #f4f5f7; --charcoal: #1a1a1a;
    --muted: #5a6474; --border: #e2e5ea;
  }
  html { scroll-behavior: smooth; }
  body { font-family: 'Barlow', sans-serif; background: var(--white); color: var(--charcoal); font-size: 16px; line-height: 1.6; -webkit-font-smoothing: antialiased; }

  nav { position: fixed; top: 0; left: 0; right: 0; z-index: 200; background: var(--white); padding: 10px 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); }
  .nav-logo { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: 1.25rem; color: #111; line-height: 1; border-bottom: 9px solid #111; padding-bottom: 4px; display: inline-block; text-decoration: none; }
  .nav-logo span { color: #FFC300; }
  .nav-logo .nav-security { color: #111; font-weight: 600; font-size: 1rem; opacity: 0.6; margin-left: 6px; }

  .hero { margin-top: 49px; background: var(--navy-deep); position: relative; overflow: hidden; padding: 56px 20px 48px; }
  .hero::before { content: ''; position: absolute; inset: 0; background-image: linear-gradient(rgba(255,195,0,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,195,0,0.04) 1px, transparent 1px); background-size: 40px 40px; pointer-events: none; }
  .hero-inner { position: relative; z-index: 1; max-width: 640px; }
  .hero-badge { display: inline-block; font-family: 'Barlow Condensed', sans-serif; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--gold); border: 1px solid rgba(255,195,0,0.4); padding: 4px 10px; border-radius: 3px; margin-bottom: 14px; }
  .hero h1 { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp(2.2rem, 8vw, 3rem); line-height: 1.05; color: var(--white); margin-bottom: 12px; }
  .hero h1 em { color: var(--gold); font-style: normal; }
  .hero p { font-size: 0.95rem; color: rgba(255,255,255,0.6); line-height: 1.6; max-width: 520px; }

  .index-section { padding: 36px 20px; border-bottom: 1px solid var(--border); }
  .index-section:last-of-type { border-bottom: none; }
  .index-label { font-family: 'Barlow Condensed', sans-serif; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
  .index-section h2 { font-family: 'Barlow Condensed', sans-serif; font-size: clamp(1.4rem, 5vw, 1.8rem); font-weight: 800; color: var(--navy-deep); line-height: 1.1; margin-bottom: 16px; }
  .index-grid { display: flex; flex-direction: column; gap: 8px; }
  .index-card { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border: 1.5px solid var(--border); border-radius: 10px; text-decoration: none; transition: border-color 0.12s, background 0.12s; background: var(--white); }
  .index-card:hover { border-color: var(--gold); background: var(--off-white); }
  .index-card-label { font-family: 'Barlow Condensed', sans-serif; font-size: 1rem; font-weight: 700; color: var(--navy-deep); }
  .index-card-arrow { font-size: 0.85rem; color: var(--muted); }

  .count-badge { display: inline-block; font-size: 0.68rem; font-weight: 700; background: var(--navy-deep); color: var(--gold); padding: 2px 8px; border-radius: 3px; margin-left: 8px; vertical-align: middle; font-family: 'Barlow Condensed', sans-serif; letter-spacing: 0.06em; }

  .alert-wrap { background: var(--navy-deep); padding: 36px 20px 40px; text-align: center; border-top: 3px solid rgba(255,195,0,0.3); }
  .alert-wrap h2 { font-family: 'Barlow Condensed', sans-serif; font-size: clamp(1.6rem, 6vw, 2.2rem); font-weight: 800; color: var(--white); line-height: 1.1; margin-bottom: 6px; }
  .alert-wrap h2 span { color: var(--gold); }
  .alert-wrap p { font-size: 0.88rem; color: rgba(255,255,255,0.55); margin-bottom: 20px; }
  .alert-form { display: flex; flex-direction: column; gap: 9px; max-width: 360px; margin: 0 auto; }
  .alert-field { position: relative; }
  .alert-field-icon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); font-size: 1rem; pointer-events: none; }
  .alert-form input { width: 100%; padding: 13px 14px 13px 40px; border: 1.5px solid rgba(255,255,255,0.15); border-radius: 10px; font-size: 1rem; font-family: 'Barlow', sans-serif; color: var(--white); background: rgba(255,255,255,0.08); outline: none; transition: border-color 0.15s; -webkit-appearance: none; }
  .alert-form input::placeholder { color: rgba(255,255,255,0.35); }
  .alert-form input:focus { border-color: var(--gold); }
  .alert-form input.error { border-color: #e53935; }
  .btn-primary { display: block; width: 100%; padding: 15px; background: var(--gold); color: var(--navy-deep); font-family: 'Barlow Condensed', sans-serif; font-size: 1.1rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; border: none; border-radius: 10px; cursor: pointer; text-align: center; text-decoration: none; transition: background 0.15s; }
  .btn-primary:hover { background: var(--gold-hover); }
  .alert-trust { display: flex; align-items: center; gap: 6px; justify-content: center; margin-top: 8px; font-size: 0.7rem; color: rgba(255,255,255,0.35); }
  .alert-note { font-size: 0.62rem; color: rgba(255,255,255,0.25); line-height: 1.5; margin-top: 10px; max-width: 340px; margin-left: auto; margin-right: auto; }

  footer { padding: 22px 20px; text-align: center; background: var(--navy-deep); border-top: 1px solid rgba(255,255,255,0.08); }
  .footer-logo { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: 1.1rem; color: var(--white); margin-bottom: 6px; }
  .footer-logo span { color: var(--gold-muted); }
  footer p { font-size: 0.72rem; color: rgba(255,255,255,0.35); line-height: 1.6; }
  footer a { color: rgba(255,255,255,0.35); text-decoration: underline; }

  @media (min-width: 640px) {
    .hero { padding: 72px 48px 56px; }
    .index-section { padding: 40px 40px; }
    .index-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .alert-wrap { padding: 48px 40px 52px; }
    footer { padding: 28px 40px; }
  }
</style>
</head>
<body>
<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-TP9JXK39"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->

<nav>
  <a href="/" class="nav-logo">BlackBar<span>Jobs</span><span class="nav-security">| Security</span></a>
</nav>

<section class="hero">
  <div class="hero-inner">
    <div class="hero-badge">Dallas–Fort Worth</div>
    <h1>Security Jobs<br><em>Across DFW</em></h1>
    <p>Browse security job openings by role type and city across the Dallas–Fort Worth metro. Get instant alerts when new positions open near you.</p>
  </div>
</section>

<div class="index-section">
  <div class="index-label">Browse by Role</div>
  <h2>DFW Security Jobs by Type <span class="count-badge">${dfwPages.length} categories</span></h2>
  <div class="index-grid">
${dfwPages.map(pageCard).join('\n')}
  </div>
</div>

<div class="index-section">
  <div class="index-label">Browse by City</div>
  <h2>Security Jobs by City <span class="count-badge">${cityPages.length} cities</span></h2>
  <div class="index-grid">
${cityPages.map(pageCard).join('\n')}
  </div>
</div>

<div class="index-section">
  <div class="index-label">Resources</div>
  <h2>Guides &amp; Resources</h2>
  <div class="index-grid">
${resourcePages.map(pageCard).join('\n')}
  </div>
</div>

<div class="alert-wrap" id="alerts">
  <h2>Get Notified When <span>Jobs Open</span> Near You</h2>
  <p>New security openings across DFW are posted regularly. Sign up for instant alerts.</p>
  <div class="alert-form" id="alertForm">
    <div class="alert-field">
      <span class="alert-field-icon">📍</span>
      <input id="a-zip" type="text" inputmode="numeric" pattern="[0-9]*" placeholder="ZIP Code" maxlength="5">
    </div>
    <div class="alert-field">
      <span class="alert-field-icon">📱</span>
      <input id="a-phone" type="tel" inputmode="tel" placeholder="Mobile Number">
    </div>
    <div class="alert-field">
      <span class="alert-field-icon">✉️</span>
      <input id="a-email" type="email" inputmode="email" placeholder="Email Address">
    </div>
    <div id="alertError" style="display:none;color:#e53935;font-size:0.75rem;text-align:left;"></div>
    <button class="btn-primary" onclick="submitAlert()">Get Job Alerts →</button>
    <div class="alert-trust">
      <svg width="12" height="12" viewBox="0 0 20 20" fill="none"><path d="M10 2L3 6v5c0 4 3.1 7.7 7 8.9C13.9 18.7 17 15 17 11V6L10 2z" fill="rgba(255,195,0,0.6)"/></svg>
      No spam. Unsubscribe anytime.
    </div>
    <p class="alert-note">By submitting I agree to receive SMS and email updates regarding jobs from BlackBarJobs. Msg &amp; data rates may apply. Reply STOP to unsubscribe.</p>
  </div>
  <div id="alertSuccess" style="display:none;text-align:center;padding:20px 0;">
    <div style="font-size:2.5rem;margin-bottom:12px;">✅</div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.6rem;font-weight:800;color:var(--white);margin-bottom:6px;">You're On The List</div>
    <div style="font-size:0.88rem;color:rgba(255,255,255,0.55);">We'll notify you when security jobs open near you in DFW.</div>
  </div>
</div>

<footer>
  <div class="footer-logo">BlackBar<span>Jobs</span>.com</div>
  <p>Security job alerts for professionals across the US.<br>
  <a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank">Privacy Policy</a></p>
</footer>

<script>
  function submitAlert() {
    var zip   = document.getElementById('a-zip').value.trim();
    var phone = document.getElementById('a-phone').value.trim();
    var email = document.getElementById('a-email').value.trim();
    var errEl = document.getElementById('alertError');
    document.getElementById('a-zip').classList.remove('error');
    document.getElementById('a-phone').classList.remove('error');
    if (!zip || zip.length < 5) {
      errEl.textContent = 'Please enter a valid ZIP code.';
      errEl.style.display = 'block';
      document.getElementById('a-zip').classList.add('error');
      return;
    }
    if (!phone && !email) {
      errEl.textContent = 'Please enter a phone number or email.';
      errEl.style.display = 'block';
      document.getElementById('a-phone').classList.add('error');
      return;
    }
    errEl.style.display = 'none';
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({ event: 'alert_form_submit', page_url: window.location.href, zip: zip });
    fetch('https://hook.us2.make.com/qv0ynbmsfwf33wknewif43ijdlwif58x', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        timestamp: new Date().toISOString(), zip, phone, email,
        role: 'general', source: window.location.href,
        consent: true, consent_timestamp: new Date().toISOString(),
        consent_text: 'By submitting I agree to receive SMS and email updates regarding jobs from BlackBarJobs. Msg & data rates may apply. Reply STOP to unsubscribe.'
      })
    });
    document.getElementById('alertForm').style.display = 'none';
    document.getElementById('alertSuccess').style.display = 'block';
  }
</script>
</body>
</html>`;

  const outPath = path.join(__dirname, 'security-jobs-dfw.html');
  fs.writeFileSync(outPath, html, 'utf8');
  console.log(`  OK    security-jobs-dfw.html — resources index generated`);
}

// ─── RUN ──────────────────────────────────────────────────────────────────────

console.log('\nBlackBarJobs — Fix Related Links + Build Resources Index\n');

console.log('Fixing related links:');
PAGES.filter(p => p.file && p.related).forEach(fixRelatedLinks);

console.log('\nBuilding resources index:');
buildResourcesIndex();

console.log('\nDone. Upload all changed files + security-jobs-dfw.html to GitHub.\n');

// ─── ADDING NEW PAGES IN FUTURE ───────────────────────────────────────────────
// 1. Add a new entry to the PAGES array above with file, url, label, category, type, city, related
// 2. Run: node fix-related-links.js
// 3. The new page's related links are set, existing pages that should link to it are NOT
//    auto-updated — manually add the new URL to relevant pages' related arrays above
//    then re-run the script
