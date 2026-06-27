import re, os, glob

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
print(f'Repo root: {REPO_ROOT}')

SCAN_ROOT = True
SCAN_DIRS = [
    'jobs',
    'houston/jobs',
    'san antonio/jobs',
]

SKIP_FILES = {
    'register.html', 'login.html', 'dashboard.html',
    'job-board.html', 'index.html', 'about.html', 'terms.html',
    'employers-dfw.html', 'sitemap.xml', 'robots.txt',
}

ALERT_BTN_PATTERNS = [
    r'<button[^>]*onclick="submitAlert\(\)"[^>]*>.*?</button>',
    r"<button[^>]*onclick='submitAlert\(\)'[^>]*>.*?</button>",
    r'<button[^>]*onclick="[^"]*scrollIntoView[^"]*"[^>]*>Get Free Job Alerts[^<]*</button>',
    r'<button[^>]*onclick="submitModal\(\)"[^>]*>Get Free Job Alerts[^<]*</button>',
]

# Handles both attribute orders: class before href, href before class
JOB_BOARD_CTA_PATTERN = (
    r'<a\b[^>]*\bclass="btn-(?:primary|gold)"[^>]*\bhref="/job-board[^"]*"[^>]*>(?:(?!</a>).)*</a>'
    r'|'
    r'<a\b[^>]*\bhref="/job-board[^"]*"[^>]*\bclass="btn-(?:primary|gold)"[^>]*>(?:(?!</a>).)*</a>'
)

CTA_REPLACEMENT = '<a href="/register.html" class="btn-primary" style="display:block;text-align:center;text-decoration:none;max-width:360px;margin:0 auto;">Get Job Alerts \u2192</a>'

H1_MOBILE_PATTERNS = [
    (r"\.hero h1 \{ font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp\(2\.8rem, 4vw, 3\.8rem\); line-height: 1\.05; letter-spacing: -0\.01em; color: var\(--white\); margin-bottom: 10px; \}",
     ".hero h1 { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp(2.4rem, 9vw, 3.2rem); line-height: 1.05; letter-spacing: -0.01em; color: var(--white); margin-bottom: 10px; }"),
    (r"\.hero h1 \{ font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp\(2\.1rem, 7vw, 3rem\); line-height: 1\.0; color: var\(--white\); margin-bottom: 8px; \}",
     ".hero h1 { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp(2.4rem, 9vw, 3.2rem); line-height: 1.05; letter-spacing: -0.01em; color: var(--white); margin-bottom: 10px; }"),
    (r"\.hero h1 \{ font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:clamp\(2rem,7vw,3rem\);line-height:1\.0;color:var\(--white\);margin-bottom:8px; \}",
     ".hero h1 { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: clamp(2.4rem, 9vw, 3.2rem); line-height: 1.05; letter-spacing: -0.01em; color: var(--white); margin-bottom: 10px; }"),
]

H1_DESKTOP_OLD = r'    \.hero h1 \{ font-size: clamp\(2\.8rem, 4vw, 3\.8rem\); \}'
H1_DESKTOP_NEW = '    .hero h1 { font-size: clamp(3rem, 4.5vw, 4.4rem); }'

VIEW_BTN_OLD = '\'<span class="hf-apply">View</span>\''
VIEW_BTN_NEW = (
    '\'<div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">\''
    '+\'<span style="font-size:0.6rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;background:#1a6b2e;color:#fff;padding:2px 7px;border-radius:3px;">New</span>\''
    '+\'<span style="padding:6px 12px;background:#FFC300;color:#000814;font-family:\\\'Barlow Condensed\\\',sans-serif;font-size:0.8rem;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;border-radius:8px;pointer-events:none;">View</span>\''
    '+\'</div>\''
)


def patch_file(path):
    with open(path, 'r', encoding='utf-8', errors='ignore', newline='') as f:
        raw = f.read()

    html = raw.replace('\r\n', '\n').replace('\r', '\n')
    original = html

    for pattern in ALERT_BTN_PATTERNS:
        html = re.sub(pattern, CTA_REPLACEMENT, html, flags=re.DOTALL)

    html = re.sub(JOB_BOARD_CTA_PATTERN, CTA_REPLACEMENT, html, flags=re.DOTALL)

    for old, new in H1_MOBILE_PATTERNS:
        html = re.sub(old, new, html)

    html = re.sub(H1_DESKTOP_OLD, H1_DESKTOP_NEW, html)

    if VIEW_BTN_OLD in html:
        html = html.replace('+' + VIEW_BTN_OLD, '+' + VIEW_BTN_NEW)

    if html != original:
        with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(html)
        return 'patched'
    return 'unchanged'


results = {'patched': 0, 'unchanged': 0, 'error': 0}

if SCAN_ROOT:
    root_files = glob.glob(os.path.join(REPO_ROOT, '*.html'))
    print(f'Scanning root — found {len(root_files)} HTML files')
    for fpath in root_files:
        fname = os.path.basename(fpath)
        if fname in SKIP_FILES:
            continue
        try:
            result = patch_file(fpath)
            print(f'[{result}] {fname}')
            results[result] += 1
        except Exception as e:
            print(f'[error] {fname}: {e}')
            results['error'] += 1

for folder in SCAN_DIRS:
    scan_path = os.path.join(REPO_ROOT, folder)
    if not os.path.isdir(scan_path):
        print(f'[skip] folder not found: {scan_path}')
        continue
    files = glob.glob(os.path.join(scan_path, '**', '*.html'), recursive=True)
    print(f'Scanning {folder} — found {len(files)} HTML files')
    for fpath in files:
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
