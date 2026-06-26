import os, re

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Folders to scan (relative to repo root)
SCAN_DIRS = [
    '',           # root
    'jobs',
    'houston/jobs',
]

# Files to skip entirely
SKIP_FILES = {
    'register.html',
    'login.html',
    'dashboard.html',
}

NAV_CDN    = '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>'
NAV_CONFIG = '<script src="/js/supabase-config.js"></script>'
NAV_SCRIPT = '<script src="/js/bbj-auth-nav.js"></script>'

def patch_file(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()

    # Skip if already has the nav script
    if 'bbj-auth-nav.js' in html:
        return 'skipped (already patched)'

    # Must have </body> to inject
    if '</body>' not in html:
        return 'skipped (no </body>)'

    # Inject before </body>
    inject = f'\n{NAV_CDN}\n{NAV_CONFIG}\n{NAV_SCRIPT}\n'
    patched = html.replace('</body>', inject + '</body>', 1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(patched)

    return 'patched'

results = {'patched': [], 'skipped': [], 'error': []}

for folder in SCAN_DIRS:
    scan_path = os.path.join(REPO_ROOT, folder)
    if not os.path.isdir(scan_path):
        print(f'[skip] folder not found: {scan_path}')
        continue

    for fname in os.listdir(scan_path):
        if not fname.endswith('.html'):
            continue
        if fname in SKIP_FILES:
            print(f'[skip] {fname}')
            continue

        fpath = os.path.join(scan_path, fname)
        try:
            result = patch_file(fpath)
            print(f'[{result}] {os.path.join(folder, fname) if folder else fname}')
            if 'patched' in result:
                results['patched'].append(fname)
            else:
                results['skipped'].append(fname)
        except Exception as e:
            print(f'[error] {fname}: {e}')
            results['error'].append(fname)

print(f'\nDone. Patched: {len(results["patched"])} | Skipped: {len(results["skipped"])} | Errors: {len(results["error"])}')