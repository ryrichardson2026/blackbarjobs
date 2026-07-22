/* bbj-feed.js  ·  Phase 5 of the BBJ Supabase feed
 * One shared renderer for both feed containers. Reads the page's static JSON
 * snapshot (written by bbj_feed_snapshot.py) instead of the Google Sheet, and
 * renders into whichever container the page uses:
 *   #jobRows       -> jf-row markup, gated by bbjHandleApply
 *   #indexJobFeed  -> hf-row markup, gated by handleIndexApply
 * The per-page feed key is set inline just above this tag as window.BBJ_FEED_KEY.
 * Each card is a real <a href> to the employer (crawlable), byte-identical to the
 * markup bbj_feed_bake.py bakes into the static HTML. The registration gate is
 * preserved on the anchor: the click handler returns true to let the href navigate
 * for allowed views and preventDefault()s the gated 3rd view into the register
 * overlay, so the link never bypasses the gate.
 */
(function () {
  var KEY = window.BBJ_FEED_KEY || "";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function relPosted(iso) {
    if (!iso) return "";
    var d = new Date(iso + "T00:00:00");
    if (isNaN(d.getTime())) return "";
    var t = new Date(); t.setHours(0, 0, 0, 0);
    var days = Math.round((t - d) / 86400000);
    if (days <= 0) return "Posted today";
    if (days === 1) return "Posted yesterday";
    if (days < 7) return "Posted " + days + " days ago";
    return "Posted " + d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  /* ── click gates: return true to let the anchor's href navigate (crawlable),
     preventDefault + register-overlay on the gated 3rd view (never bypass) ── */
  window.bbjHandleApply = window.bbjHandleApply || function (arg, event) {
    // arg is the row element (row-body click; url read from data-url) or the CTA
    // anchor's href string. On an allowed view we let the anchor's href follow
    // natively (return true) or window.open for the element path; on the gated
    // 3rd view we preventDefault the anchor and open the register overlay so the
    // real <a href> stays crawlable without ever bypassing the gate.
    var isHref = typeof arg === "string";
    var url = isHref ? arg : decodeURIComponent((arg && arg.dataset && arg.dataset.url) || "");
    if (!url) return false;
    if (event) event.stopPropagation();          // CTA click must not also fire the row onclick
    var registered = document.cookie.indexOf("bbj_registered=1") !== -1;
    var views = parseInt((document.cookie.match(/bbj_views=(\d+)/) || [0, 0])[1], 10);
    if (registered || views < 2) {
      if (!registered) { document.cookie = "bbj_views=" + (views + 1) + ";path=/;SameSite=Lax"; }
      var a = event && event.currentTarget;       // same tab on mobile, new tab on desktop:
      if (a && a.tagName === "A") {                // keeps BBJ in the back stack after app hand-off
        a.target = window.matchMedia("(max-width: 820px)").matches ? "_self" : "_blank";
      }
      if (isHref) { return true; }                // let the anchor href open the employer
      window.open(url, "_blank"); return false;   // row-body click has no href to follow
    }
    if (event) event.preventDefault();            // gate: stop the anchor navigating
    if (typeof bbjAccOpen === "function") { bbjAccOpen(); } else { window.open(url, "_blank"); }
    return false;
  };

  window.indexViewsThisSession = window.indexViewsThisSession || 0;
  window.handleIndexApply = window.handleIndexApply || function (href, event) {
    // href is the anchor's resolved apply URL. Allowed views (registered, or the
    // first two this session) let the href navigate natively (return true); the
    // gated 3rd view preventDefaults the anchor and opens the register overlay.
    var url = href || "";
    if (!url) return false;
    var a = event && event.currentTarget;         // same tab on mobile, new tab on desktop
    if (a && a.tagName === "A") {
      a.target = window.matchMedia("(max-width: 820px)").matches ? "_self" : "_blank";
    }
    if (typeof bbjIsRegistered === "function" && bbjIsRegistered()) { return true; }
    window.indexViewsThisSession = (window.indexViewsThisSession || 0) + 1;
    if (window.indexViewsThisSession <= 2) { return true; }
    if (event) event.preventDefault();
    if (typeof bbjAccOpen === "function") { bbjAccOpen(); } else { window.open(url, "_blank"); }
    return false;
  };

  /* ── renderers ── */
  function renderJobRows(c, jobs) {
    c.innerHTML = jobs.map(function (j) {
      var url = encodeURIComponent(j.apply_link || "");
      return '<div class="jf-row" style="cursor:pointer;" onclick="bbjHandleApply(this)" data-url="' + url + '">' +
        '<div class="jf-body">' +
          '<div class="jf-title">' + esc(j.title) + '</div>' +
          '<div class="jf-meta"><span class="jf-company">' + esc(j.company) + '</span>' +
          (j.location ? '<span class="jf-sep">&middot;</span><span class="jf-loc">' + esc(j.location) + '</span>' : '') +
          (j.pay ? '<span class="jf-pay">' + esc(j.pay) + '</span>' : '') +
          (relPosted(j.posted_date) ? '<span class="jf-sep">&middot;</span><span class="jf-date" style="color:#1a6b2e;font-weight:600;">' + esc(relPosted(j.posted_date)) + '</span>' : '') +
          '</div></div><a class="jf-apply" href="' + esc(j.apply_link || "") + '"' +
          ' rel="nofollow sponsored noopener" target="_blank" onclick="return bbjHandleApply(this.href, event)">Apply</a></div>';
    }).join("");
  }

  function renderIndexFeed(c, jobs) {
    c.innerHTML = jobs.map(function (j) {
      return '<a class="hf-row" href="' + esc(j.apply_link || "") + '"' +
        ' rel="nofollow sponsored noopener" target="_blank"' +
        ' style="display:flex;align-items:center;justify-content:space-between;cursor:pointer;text-decoration:none;color:inherit;"' +
        ' onclick="return handleIndexApply(this.href, event)">' +
        '<div class="hf-body">' +
          '<div class="hf-title">' + esc(j.title) + '</div>' +
          '<div class="hf-meta">' + esc(j.company) + ' &nbsp;&middot;&nbsp; ' + esc(j.location) + (relPosted(j.posted_date) ? ' &nbsp;&middot;&nbsp; <span style="color:#1a6b2e;font-weight:600;">' + esc(relPosted(j.posted_date)) + '</span>' : '') + '</div>' +
        '</div>' +
        '<div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">' +
          '<span style="font-size:0.6rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;background:#1a6b2e;color:#fff;padding:2px 7px;border-radius:3px;">New</span>' +
          '<span style="padding:6px 12px;background:#FFC300;color:#000814;font-family:\'Barlow Condensed\',sans-serif;font-size:0.8rem;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;border-radius:8px;pointer-events:none;">Apply</span>' +
        '</div></a>';
    }).join("");
  }

  var EMPTY_JR = '<div style="padding:12px;color:#999;font-size:0.85rem;">No listings right now. Check back soon.</div>';
  var ERR_JR   = '<div style="padding:12px;color:#999;font-size:0.85rem;">Could not load jobs.</div>';
  var EMPTY_HF = '<div class="hf-row"><div class="hf-body"><div class="hf-title" style="color:#5a6474;">No listings right now. Check back soon.</div></div></div>';
  var ERR_HF   = '<div class="hf-row"><div class="hf-body"><div class="hf-title" style="color:#5a6474;">Check back soon for open positions.</div></div></div>';

  function run() {
    var jr = document.getElementById("jobRows");
    var idx = document.getElementById("indexJobFeed");
    if (!jr && !idx) return;
    if (!KEY) { if (jr) jr.innerHTML = ERR_JR; if (idx) idx.innerHTML = ERR_HF; return; }

    fetch("/feed/" + KEY + ".json", { cache: "no-cache" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        var jobs = (data && data.jobs ? data.jobs : []).slice(0, 10);
        if (jr) { jobs.length ? renderJobRows(jr, jobs) : (jr.innerHTML = EMPTY_JR); }
        if (idx) { jobs.length ? renderIndexFeed(idx, jobs) : (idx.innerHTML = EMPTY_HF); }
      })
      .catch(function () {
        if (jr) jr.innerHTML = ERR_JR;
        if (idx) idx.innerHTML = ERR_HF;
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
