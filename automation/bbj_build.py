#!/usr/bin/env python3
"""
bbj_build.py  ·  The build driver for bbj_generator_v5 (Task 0, item 1)

bbj_generator_v5.py is a LIBRARY: it defines generate_page(cfg) and the manifest/
sitemap helpers, but nothing in the repo ever called it, so pages have been hand-
built by clone-and-specialize. This is the missing caller. It turns a JSON page
config (or a list of them) into HTML on disk, and — only when asked — registers the
feed target and adds the sitemap <loc>, reusing the generator's own hooks so nothing
is reimplemented:
    generate_page(cfg)         -> HTML (guardrails + interlinking gate run inside)
    upsert_target_entry(cfg)   -> automation/bbj_page_targets.json entry
    sitemap_upsert(cfg)        -> sitemap.xml <url> block
    next_steps(cfg)            -> the post-build checklist (generator prints it)

Region tokenization (Task 0, item 2): the generator's hero badge, pay heading, and
alert copy already interpolate cfg['region'] (default 'TX'). The driver fills that
token per market from MARKET_REGION, so a Chicago page renders 'Chicago, IL' without
each cfg having to repeat it. It also refuses to build a non-Texas page whose footer/
resource/related links still point at /texas/ security guides — the Texas defaults in
generate_page's res_map/ft_map must be overridden per cfg for a new market.

Config shape: a .json file holding either one cfg object or a list of them. cfg is
exactly what generate_page expects; tuples are written as JSON arrays (related_links
= [[href,emoji,label], ...], pay_entry = [rate, annual], faqs = [[q,a], ...]), which
the generator's builders unpack unchanged.

Usage (from repo root):
  python automation/bbj_build.py <config.json>                    # dry-run: build in
                                                                  #   memory, report only
  python automation/bbj_build.py <config.json> --write            # write HTML to cfg path
  python automation/bbj_build.py <config.json> --write --register --sitemap
  python automation/bbj_build.py <config.json> --write --out-dir /tmp/preview
"""

import argparse, json, os, sys
from pathlib import Path

# The generator prints status with emoji (e.g. the interlinking-warning banner). On a
# Windows cp1252 console that raises UnicodeEncodeError, so force UTF-8 on our streams
# — this is the entry point, so every downstream print() inherits it.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# bbj_generator_v5.py lives at the repo root (parent of this automation/ dir).
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
import bbj_generator_v5 as gen

# Per-market state token for cfg['region'] (the 'TX' the generator defaults to).
# A cfg may still set 'region' explicitly to override.
MARKET_REGION = {
    "DFW": "TX", "Houston": "TX", "San Antonio": "TX", "Austin": "TX",
    "Chicago": "IL",
}

# Texas security guides that must never appear on an out-of-state page.
_TEXAS_MARKER = "/texas/"


def _iter_link_hrefs(cfg):
    """Yield every href the cfg would emit in footer/resource/related link lists, so a
    Texas-guide leak onto a new-market page is caught before the page ships."""
    for key in ("footer_links", "resources"):
        for row in cfg.get(key) or []:
            if row:
                yield key, row[0]
    for row in cfg.get("related_links") or []:
        if row:
            yield "related_links", row[0]


def _guard_no_texas_leak(cfg):
    """Block a non-TX market whose links still carry Texas defaults. The generator's
    res_map/ft_map fall back to DFW/Texas; a new market MUST override them in cfg."""
    region = cfg.get("region") or MARKET_REGION.get(cfg.get("market", ""), "TX")
    if region == "TX":
        return
    offenders = [f"{where}: {href}" for where, href in _iter_link_hrefs(cfg)
                 if _TEXAS_MARKER in href]
    if offenders:
        raise SystemExit(
            "BUILD BLOCKED — %s (region=%s) links to Texas guides; override the "
            "footer_links/resources/related_links in this cfg:\n  - %s"
            % (cfg.get("slug", "?"), region, "\n  - ".join(offenders)))


def _apply_region_default(cfg):
    """Fill cfg['region'] from the market when the cfg omits it (Task 0 item 2)."""
    if not cfg.get("region"):
        market = cfg.get("market", "Houston")
        if market in MARKET_REGION:
            cfg["region"] = MARKET_REGION[market]


def _out_path(cfg, out_dir=None):
    rel = cfg.get("path", cfg["slug"].lstrip("/") + ".html")
    base = Path(out_dir) if out_dir else REPO_ROOT
    return base / rel


def build_one(cfg, write=False, register=False, sitemap=False, out_dir=None):
    _apply_region_default(cfg)
    _guard_no_texas_leak(cfg)

    html = gen.generate_page(cfg)          # runs guardrails + interlinking gate

    dest = _out_path(cfg, out_dir)
    if write:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8", newline="")
        action = "wrote"
    else:
        action = "built (dry-run, not written)"

    if register:
        act, total = gen.upsert_target_entry(cfg,
            targets_path=str(REPO_ROOT / "automation" / "bbj_page_targets.json"))
        print("  target %s (%d total)" % (act, total))
    if sitemap:
        act, loc = gen.sitemap_upsert(cfg, sitemap_path=str(REPO_ROOT / "sitemap.xml"))
        print("  sitemap %s: %s" % (act, loc))

    print("  %s %s  (%d bytes)" % (action, dest, len(html)))
    return html


def load_cfgs(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def main():
    ap = argparse.ArgumentParser(description="Build BBJ pages from JSON configs")
    ap.add_argument("config", help="a .json file: one cfg object or a list of them")
    ap.add_argument("--write", action="store_true", help="write HTML to disk (default: dry-run)")
    ap.add_argument("--register", action="store_true", help="upsert the feed target into the manifest")
    ap.add_argument("--sitemap", action="store_true", help="add/refresh the page's sitemap <loc>")
    ap.add_argument("--out-dir", help="write under this dir instead of the repo root (preview)")
    args = ap.parse_args()

    cfgs = load_cfgs(args.config)
    print("Building %d page(s) from %s%s"
          % (len(cfgs), args.config, "" if args.write else "  [DRY-RUN]"))
    for cfg in cfgs:
        build_one(cfg, write=args.write, register=args.register,
                  sitemap=args.sitemap, out_dir=args.out_dir)
    print("Done: %d page(s)." % len(cfgs))


if __name__ == "__main__":
    main()
