import os, glob

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

# CSS block to inject before </style> — hides hero image on mobile
MOBILE_HERO_CSS = """
/* ── MOBILE: hide hero image, collapse height ── */
@media (max-width: 639px) {
  .hero-img-wrap, .hero-image-wrap { display: none !important; }
  .hero { min-height: 0 !important; background: #000814 !important; }
}
"""

MARKER = '/* ── MOBILE: hide hero image'

def patch_file(path):
    with open(path, 'r', encoding='utf-8', errors='ignore', newline='') as f:
        raw = f.read()

    html = raw.replace('\r\n', '\n').replace('\r', '\n')

    # Skip if already patched
    if MARKER in html:
        return 'skipped'

    # Inject before closing </style> tag
    if '</style>' not in html:
        return 'no-style-tag'

    html = html.replace('</style>', MOBILE_HERO_CSS + '</style>', 1)

    with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(html)
    return 'patched'


results = {'patched': 0, 'skipped': 0, 'error': 0}

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

print(f'\nDone. Patched: {results["patched"]} | Skipped: {results["skipped"]} | Errors: {results["error"]}')
