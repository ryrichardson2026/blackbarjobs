/**
 * inject-gtm.js
 * BlackBarJobs — GTM + GA4 injection script
 *
 * SETUP:
 * 1. Replace GTM_CONTAINER_ID below with your actual GTM ID (e.g. GTM-ABC1234)
 * 2. Run: node inject-gtm.js
 * 3. All .html files in the target directory will be updated in place
 * 4. Push to Vercel — done
 *
 * SAFE TO RE-RUN: script checks for existing GTM before injecting, no duplicates
 */

const fs   = require('fs');
const path = require('path');

// ─── CONFIG ───────────────────────────────────────────────────────────────────

const GTM_CONTAINER_ID = 'GTM-TP9JXK39';

// Directory containing your HTML files — change if your structure differs
// '.' = same folder as this script; adjust to e.g. './public' or './pages' as needed
const HTML_DIR = '.';

// ─── GTM SNIPPETS ─────────────────────────────────────────────────────────────

const GTM_HEAD = `<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','${GTM_CONTAINER_ID}');</script>
<!-- End Google Tag Manager -->`;

const GTM_BODY = `<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=${GTM_CONTAINER_ID}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->`;

// ─── DATALAYER PUSH FOR ALERT FORM CONVERSION ─────────────────────────────────
// Injected into each page's submitAlert() function so GTM can fire a conversion
// event when someone successfully submits the job alert form.
// GTM trigger: Custom Event = "alert_form_submit"

const CONVERSION_PUSH = `
    // GTM conversion event
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'alert_form_submit',
      page_url: window.location.href,
      zip: zip
    });`;

// ─── HELPERS ──────────────────────────────────────────────────────────────────

function getHtmlFiles(dir) {
  return fs.readdirSync(dir)
    .filter(f => f.endsWith('.html') && f !== 'index.html')
    .map(f => path.join(dir, f));
}

function injectGtm(filePath) {
  let html = fs.readFileSync(filePath, 'utf8');
  const fileName = path.basename(filePath);

  // Skip if GTM already present
  if (html.includes('googletagmanager.com/gtm.js')) {
    console.log(`  SKIP  ${fileName} — GTM already present`);
    return;
  }

  // 1. Inject GTM head snippet immediately after <head>
  if (html.includes('<head>')) {
    html = html.replace('<head>', `<head>\n${GTM_HEAD}`);
  } else {
    console.warn(`  WARN  ${fileName} — no <head> tag found, skipping head injection`);
  }

  // 2. Inject GTM body noscript immediately after <body>
  if (html.includes('<body>')) {
    html = html.replace('<body>', `<body>\n${GTM_BODY}`);
  } else {
    console.warn(`  WARN  ${fileName} — no <body> tag found, skipping body injection`);
  }

  // 3. Inject dataLayer conversion push into submitAlert() success block
  //    Inserts before the form hide / success show lines
  const successTrigger = `document.getElementById('alertForm').style.display = 'none';`;
  if (html.includes(successTrigger) && !html.includes('alert_form_submit')) {
    html = html.replace(successTrigger, `${CONVERSION_PUSH}\n    ${successTrigger}`);
  }

  fs.writeFileSync(filePath, html, 'utf8');
  console.log(`  OK    ${fileName}`);
}

// ─── RUN ──────────────────────────────────────────────────────────────────────

console.log(`\nBlackBarJobs — GTM Injection`);
console.log(`Container: ${GTM_CONTAINER_ID}`);
console.log(`Directory: ${path.resolve(HTML_DIR)}\n`);

if (!GTM_CONTAINER_ID || !GTM_CONTAINER_ID.startsWith('GTM-')) {
  console.error('ERROR: Invalid GTM container ID.\n');
  process.exit(1);
}

const files = getHtmlFiles(HTML_DIR);

if (!files.length) {
  console.log('No HTML files found in target directory.');
  process.exit(0);
}

console.log(`Found ${files.length} HTML file(s):\n`);
files.forEach(injectGtm);

console.log(`\nDone. Push your files to Vercel to deploy.\n`);
