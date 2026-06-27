import re, os, glob

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

SCAN_DIRS = [
    'jobs',
    'houston/jobs',
    'san antonio/jobs',
]

SKIP_FILES = {
    'register.html', 'login.html', 'dashboard.html',
    'job-board.html', 'index.html',
}

# ── 1. ALERT CTA REPLACEMENTS ────────────────────────────────────────────────

# submitAlert() buttons
ALERT_BTN_PATTERNS = [
    r'<button[^>]*onclick="submitAlert\(\)"[^>]*>.*?</button>',
    r'<button[^>]*onclick=\'submitAlert\(\)\'[^>]*>.*?</button>',
    r'<button[^>]*onclick="[^"]*scrollIntoView[^"]*"[^>]*>Get Free Job Alerts[^<]*</button>',
]
ALERT_BTN_REPLACEMENT = '<a href="/register.html" class="btn-primary" style="display:block;text-align:center;text-decoration:none;max-width:360px;margin:0 auto;">Get Job Alerts →</a>'

# submitModal() buttons (gate modal alert buttons)
MODAL_BTN_PATTERNS = [
    r'<button[^>]*onclick="submitModal\(\)"[^>]*>Get Free Job Alerts[^<]*</button>',
]

# ── 2. STYLE FIXES ───────────────────────────────────────────────────────────

# H1 mobile — all variants → standard
H1_MOBILE_PATTERNS = [
    # Most common — 185 pages
    (r"\.hero h1 \{ font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp\(2\.8rem, 4vw, 3\.8rem\); line-height: 1\.05; letter-spacing: -0\.01em; color: var\(--white\); margin-bottom: 10px; \}",
     ".hero h1 { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp(2.4rem, 9vw, 3.2rem); line-height: 1.05; letter-spacing: -0.01em; color: var(--white); margin-bottom: 10px; }"),
    # Old unarmed/armed style — 5 pages
    (r"\.hero h1 \{ font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp\(2\.1rem, 7vw, 3rem\); line-height: 1\.0; color: var\(--white\); margin-bottom: 8px; \}",
     ".hero h1 { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp(2.4rem, 9vw, 3.2rem); line-height: 1.05; letter-spacing: -0.01em; color: var(--white); margin-bottom: 10px; }"),
    # Minified — 1 page
    (r"\.hero h1 \{ font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:clamp\(2rem,7vw,3rem\);line-height:1\.0;color:var\(--white\);margin-bottom:8px; \}",
     ".hero h1 { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp(2.4rem, 9vw, 3.2rem); line-height: 1.05; letter-spacing: -0.01em; color: var(--white); margin-bottom: 10px; }"),
]

# H1 desktop — 185 pages
H1_DESKTOP_OLD = r'    \.hero h1 \{ font-size: clamp\(2\.8rem, 4vw, 3\.8rem\); \}'
H1_DESKTOP_NEW = '    .hero h1 { font-size: clamp(3rem, 4.5vw, 4.4rem); }'

# hf-row — add cursor:pointer
HF_ROW_OLD = r'(\.hf-row\s*\{[^}]*?)background:\s*transparent;(\s*\})'
HF_ROW_NEW = r'\1background: transparent; cursor: pointer;\2'

# View button — replace hf-apply span with gold inline style + NEW pill
VIEW_BTN_OLD = r"\+'<span class=\"hf-apply\">View</span>'"
VIEW_BTN_NEW = (
    "+'<div style=\"display:flex;align-items:center;gap:6px;flex-shrink:0;\">'"
    "+'<span style=\"font-size:0.6rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;background:#1a6b2e;color:#fff;padding:2px 7px;border-radius:3px;\">New</span>'"
    "+'<span style=\"padding:6px 12px;background:#FFC300;color:#000814;font-family:\\'Barlow Condensed\\',sans-serif;font-size:0.8rem;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;border-radius:8px;pointer-events:none;\">View</span>'"
    "+'</div>'"
)


def patch_file(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()

    original = html

    # 1. Alert CTA buttons
    for pattern in ALERT_BTN_PATTERNS:
        html = re.sub(pattern, ALERT_BTN_REPLACEMENT, html, flags=re.DOTALL)

    for pattern in MODAL_BTN_PATTERNS:
        html = re.sub(pattern, ALERT_BTN_REPLACEMENT, html, flags=re.DOTALL)

    # 2. H1 mobile font size
    for old, new in H1_MOBILE_PATTERNS:
        html = re.sub(old, new, html)

    # 3. H1 desktop font size
    html = re.sub(H1_DESKTOP_OLD, H1_DESKTOP_NEW, html)

    # 4. hf-row cursor pointer (only if not already there)
    if 'cursor: pointer' not in html.split('.hf-row')[1][:200] if '.hf-row' in html else True:
        html = re.sub(HF_ROW_OLD, HF_ROW_NEW, html)

    # 5. View button → gold + NEW pill (only if hf-apply still present)
    if '<span class="hf-apply">View</span>' in html:
        html = html.replace("+'<span class=\"hf-apply\">View</span>'", VIEW_BTN_NEW)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)

    return 'patched' if html != original else 'unchanged'


results = {'patched': 0, 'unchanged': 0, 'error': 0}

for folder in SCAN_DIRS:
    scan_path = os.path.join(REPO_ROOT, folder)
    if not os.path.isdir(scan_path):
        print(f'[skip] folder not found: {scan_path}')
        continue

    for fpath in glob.glob(os.path.join(scan_path, '**', '*.html'), recursive=True):
        fname = os.path.basename(fpath)
        if fname in SKIP_FILES:
            continue
        try:
            result = patch_file(fpath)
            rel = os.path.relpath(fpath, REPO_ROOT)
            print(f'[{result}] {rel}')
            results[result] += 1
        except Exception as e:
            print(f'[error] {fpath}: {e}')
            results['error'] += 1

print(f'\nDone. Patched: {results["patched"]} | Unchanged: {results["unchanged"]} | Errors: {results["error"]}')
