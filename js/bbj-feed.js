/* bbj-feed.js  ·  Phase 5 of the BBJ Supabase feed
 * One shared renderer for both feed containers. Reads the page's static JSON
 * snapshot (written by bbj_feed_snapshot.py) instead of the Google Sheet, and
 * renders into whichever container the page uses:
 *   #jobRows       -> jf-row markup, gated by bbjHandleApply
 *   #indexJobFeed  -> hf-row markup, gated by handleIndexApply
 * The per-page feed key is set inline just above this tag as window.BBJ_FEED_KEY.
 * Behavior and markup match the old inline code exactly, so nothing changes for
 * the visitor except the data source.
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

  /* ── click gates (faithful copies of the originals) ── */
  window.bbjHandleApply = window.bbjHandleApply || function (el) {
    var url = decodeURIComponent(el.dataset.url || "");
    if (!url) return;
    if (document.cookie.indexOf("bbj_registered=1") !== -1) { window.open(url, "_blank"); return; }
    var views = parseInt((document.cookie.match(/bbj_views=(\d+)/) || [0, 0])[1], 10);
    if (views < 2) {
      views++; document.cookie = "bbj_views=" + views + ";path=/;SameSite=Lax";
      window.open(url, "_blank"); return;
    }
    if (typeof bbjAccOpen === "function") { bbjAccOpen(); } else { window.open(url, "_blank"); }
  };

  window.indexViewsThisSession = window.indexViewsThisSession || 0;
  window.handleIndexApply = window.handleIndexApply || function (encodedUrl) {
    var url = decodeURIComponent(encodedUrl);
    if (!url) return;
    if (typeof bbjIsRegistered === "function" && bbjIsRegistered()) { window.open(url, "_blank"); return; }
    window.indexViewsThisSession = (window.indexViewsThisSession || 0) + 1;
    if (window.indexViewsThisSession <= 2) { window.open(url, "_blank"); return; }
    if (typeof bbjAccOpen === "function") { bbjAccOpen(); } else { window.open(url, "_blank"); }
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
          '</div></div><a class="jf-apply">View</a></div>';
    }).join("");
  }

  function renderIndexFeed(c, jobs) {
    c.innerHTML = jobs.map(function (j) {
      var url = encodeURIComponent(j.apply_link || "");
      return '<div class="hf-row" style="display:flex;align-items:center;justify-content:space-between;cursor:pointer;" onclick="handleIndexApply(\'' + url + '\')">' +
        '<div class="hf-body">' +
          '<div class="hf-title">' + esc(j.title) + '</div>' +
          '<div class="hf-meta">' + esc(j.company) + ' &nbsp;&middot;&nbsp; ' + esc(j.location) + (relPosted(j.posted_date) ? ' &nbsp;&middot;&nbsp; <span style="color:#1a6b2e;font-weight:600;">' + esc(relPosted(j.posted_date)) + '</span>' : '') + '</div>' +
        '</div>' +
        '<div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">' +
          '<span style="font-size:0.6rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;background:#1a6b2e;color:#fff;padding:2px 7px;border-radius:3px;">New</span>' +
          '<span style="padding:6px 12px;background:#FFC300;color:#000814;font-family:\'Barlow Condensed\',sans-serif;font-size:0.8rem;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;border-radius:8px;pointer-events:none;">View</span>' +
        '</div></div>';
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
