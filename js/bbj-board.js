/* ───────────────── CONFIG ───────────────── */
  // Job source: static /feed/board.json (all active jobs), written by bbj_feed_snapshot.py. Google Sheet retired.
  var PAGE_SIZE = 10;
  var FREE_VIEWS = 0;       // registration required: gate fires on the first job-card click (0 free views)

  /* ───────────────── STATE ───────────────── */
  var ALL_JOBS = [];
  var FILTERED = [];
  var shown = 0;
  var pendingUrl = '';
  var pendingJob = null;
  var registered = false;
  function bbjHasSupabaseSession(){
    // Validate the token, do NOT trust mere existence: supabase-js writes an
    // sb-<ref>-auth-token key for anonymous visitors too, so an existence check
    // reads every guest as logged-in and bypasses the click gate. Require a
    // parseable session with a real access_token, a user id, and (if stamped) an
    // expiry in the future.
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (!k || !/^sb-.*-auth-token$/.test(k)) continue;
        var raw = localStorage.getItem(k);
        if (!raw || raw === 'null') continue;
        var obj;
        try { obj = JSON.parse(raw); } catch(e) { continue; }   // unparseable -> not a session
        if (!obj || typeof obj !== 'object') continue;
        var s = obj.currentSession || obj.session || obj;        // tolerate wrapper shapes
        if (!s.access_token) continue;                           // "", null, {} all fail here
        if (!s.user || !s.user.id) continue;                     // needs a real user
        if (s.expires_at && (s.expires_at * 1000) <= Date.now()) continue;  // expired
        return true;
      }
    } catch(e){}
    return false;
  }
  function bbjHideRegCtas(){
    var nc = document.querySelector('.nav-cta');
    if(nc) nc.style.display = 'none';
    document.querySelectorAll('.hero-btn.gold').forEach(function(b){ b.style.display = 'none'; });
  }
  // Live registration check — re-read on every call. An in-session signup (the overlay
  // sets bbj_registered=1) unlocks immediately, so a returning/just-registered user is
  // never re-gated or asked to register/login again.
  function isRegistered(){
    return registered
      || document.cookie.indexOf('bbj_registered=1') !== -1
      || bbjHasSupabaseSession();
  }
  if (isRegistered()) {
    registered = true;
    document.addEventListener('DOMContentLoaded', bbjHideRegCtas);
  }
  var sbClient = window.supabase ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;
  if (sbClient) {
    sbClient.auth.getSession().then(function(res){
      if (res.data && res.data.session) {
        registered = true;
        try { document.cookie = 'bbj_registered=1; max-age=2592000; path=/; SameSite=Lax'; } catch(e){}
        bbjHideRegCtas();
      }
    });
  }
  // reqs (multi) + payMin (hourly-equiv floor) are new drawer axes; the rest is unchanged.
  var filters = { q: '', loc: '', vertical: '', role: '', shift: '', reqs: [], payMin: 0, pay: false, posted: '', sort: 'newest' };
  // URL-derived presets from a hub deep link; clearFilters() resets to THESE, never to
  // an empty (all-verticals) state, so clearing never drops a warehouse visitor onto
  // security jobs. Populated by applyUrlFilters().
  var PRESET = { loc: '', vertical: '', role: '', shift: '' };
  var DEFAULT_LOC = '';
  var METRO_FRIENDLY = { 'DFW': 'Dallas–Fort Worth', 'Houston': 'Houston', 'Austin': 'Austin', 'San Antonio': 'San Antonio', 'El Paso': 'El Paso', 'Chicago': 'Chicago' };
  var POSTED_OPTS = [ {v:'',label:'Any time'}, {v:'1',label:'Today'}, {v:'3',label:'Past 3 days'}, {v:'week',label:'This week'} ];

  // Hourly-equivalent so "Highest pay" ranks an $90k/yr role above a $20/hr one.
  var PAY_TO_HOURLY = { HOUR:1, DAY:1/8, WEEK:1/40, MONTH:12/2080, YEAR:1/2080 };
  function payValue(job) {
    var unit = (job.pay_unit || '').toUpperCase();
    if (job.pay_min != null && PAY_TO_HOURLY[unit]) {
      var amt = (job.pay_max != null ? job.pay_max : job.pay_min);
      return amt * PAY_TO_HOURLY[unit];
    }
    // fallback for the ~65% without structured pay: parse the string, and if a number
    // looks annual (>= 1000) convert to hourly so it doesn't dwarf real hourly rows.
    var nums = (job.pay || '').replace(/,/g,'').match(/\d+(\.\d+)?/g);
    if (!nums) return -1;
    var mx = Math.max.apply(null, nums.map(parseFloat));
    return mx >= 1000 ? mx / 2080 : mx;
  }
  function sortJobs(arr) {
    if (filters.sort === 'pay') {
      arr.sort(function(a, b){ return payValue(b) - payValue(a); });
    } else if (filters.sort === 'company') {
      arr.sort(function(a, b){ return (a.company || '').localeCompare(b.company || ''); });
    } else {
      arr.sort(function(a, b){ return bestDate(b) - bestDate(a); });
    }
  }

  /* ───────────────── TAXONOMY (single source of truth) ─────────────────
     Two axes: (1) vertical + role, (2) cross-vertical shift + attribute.
     Every role and shift is defined ONCE here; deriveRoles / deriveShifts /
     roleLabel / roleFromString / shiftFromString all read this object. This
     replaces the four functions that used to disagree (deriveRoles,
     roleFromCategory, roleKeyword, roleLabel). `title` matches a job's
     title+company; `slug` matches a hub deep-link (?role=armed-security-dfw). */
  var TAXONOMY = {
    security: { label:'Security', roles:[
      { key:'unarmed',        label:'Unarmed',         title:/\bun-?armed\b/,                                   slug:/unarmed/ },
      { key:'armed',          label:'Armed',           title:/\barmed\b/,                                       slug:/\barmed/ },
      { key:'patrol',         label:'Patrol',          title:/patrol|mobile|response agent|roving/,             slug:/mobile-patrol|patrol/ },
      { key:'event',          label:'Event',           title:/\bevent|concert|stadium|venue|game day/,          slug:/event|festival|sporting/ },
      { key:'frontdesk',      label:'Front Desk',      title:/front desk|lobby|concierge|gatehouse|access control|access gate|reception|console|dispatch/, slug:/front-?desk|dispatch|concierge/ },
      { key:'hospital',       label:'Healthcare',      title:/hospital|medical|health|children|clinic|patient/, slug:/hospital|healthcare|medical/ },
      { key:'lossprevention', label:'Loss Prevention', title:/loss prevention|asset protection|\blp\b|retail|grocery|store|shopping/, slug:/loss-prevention|asset-protection/ },
      { key:'tsa',            label:'TSA / Airport',   title:/\btsa\b|airport|aviation/,                        slug:/tsa|airport|aviation/ }
    ]},
    warehouse: { label:'Warehouse', roles:[
      { key:'forklift',        label:'Forklift',            title:/forklift|lift truck|reach truck|cherry picker|order picker/, slug:/forklift/ },
      { key:'package-handler', label:'Package Handler',     title:/package handler|package|parcel|sorter|loader|unloader|\bdock\b/, slug:/package-handler/ },
      { key:'associate',       label:'Warehouse Associate', title:/warehouse associate|warehouse worker|warehouse|picker|packer|material handler|distribution|fulfillment/, slug:/warehouse-associate|warehouse-general|warehouse/ }
    ]}
  };
  var SHIFTS = [
    { key:'overnight',     label:'Overnight',     title:/overnight|graveyard|11:00\s*pm|11pm|3:00pm-11|10pm|grave shift|\bnight\b/ },
    { key:'weekend',       label:'Weekend',       title:/weekend|saturday|sunday/ },
    { key:'part-time',     label:'Part-time',     title:/part[\s-]?time/,  jt:'part' },
    { key:'full-time',     label:'Full-time',     title:/full[\s-]?time/,  jt:'full' },
    { key:'no-experience', label:'No Experience', title:/no experience|no[\s-]?exp|entry[\s-]?level|will train/ },
    // Warehouse-only attributes (wh:true). deriveShifts skips them for other verticals, so
    // they never appear on the security board. They match the description (see deriveShifts),
    // which is where "pays weekly" / "hiring immediately" actually live.
    { key:'hiring-immediately', label:'Hiring immediately', title:/immediate|hiring now|now hiring|urgently hiring|start (?:today|now|this week)/, wh:true },
    { key:'pay-weekly',    label:'Weekly pay',    title:/weekly pay|paid weekly|pays? weekly|weekly paycheck|paid every week/, wh:true }
  ];
  // Requirements axis (multi-select) — derived from title + job_highlights text.
  var REQS = [
    { key:'noexp',         label:'No experience',    re:/no experience|no[\s-]?exp\b|entry[\s-]?level|will train|no prior experience/i },
    { key:'forklift-cert', label:'Forklift certified', re:/forklift certif|certified forklift|forklift (?:license|operator certif)|certified to operate a forklift/i },
    { key:'diploma',       label:'HS diploma / GED', re:/high school (?:diploma|graduate)|\bged\b|diploma or equivalent/i }
  ];
  function reqLabel(key){ for(var i=0;i<REQS.length;i++){ if(REQS[i].key===key) return REQS[i].label; } return key; }
  function allRoles(){ var out=[]; Object.keys(TAXONOMY).forEach(function(v){ TAXONOMY[v].roles.forEach(function(r){ out.push(r); }); }); return out; }
  function rolesForVertical(v){ return (v && TAXONOMY[v]) ? TAXONOMY[v].roles : allRoles(); }

  function deriveRoles(job) {
    var t = ((job.title || '') + ' ' + (job.company || '')).toLowerCase();
    var v = job._vertical || job.vertical || '';
    var pool = (v && TAXONOMY[v]) ? TAXONOMY[v].roles : allRoles();
    var unarmed = /\bun-?armed\b/.test(t);
    var roles = [];
    pool.forEach(function(r){
      if (r.key === 'armed' && unarmed) return;        // unarmed-before-armed guard
      if (r.title.test(t)) roles.push(r.key);
    });
    return roles;
  }
  function deriveShifts(job) {
    var v = job._vertical || job.vertical || '';
    var t = ((job.title || '') + ' ' + (job.company || '')).toLowerCase();
    // Warehouse shift/attribute matching is description-aware (board parity with the Python
    // feed deriver): "weekend", "pays weekly", "hiring immediately" live in the description,
    // not the title. Other verticals stay title+company only, so security is unchanged.
    if (v === 'warehouse') t += ' ' + (job.description || '').toLowerCase();
    var jt = (job.schedule || job.job_type || '').toLowerCase();
    var out = [];
    SHIFTS.forEach(function(s){
      if (s.wh && v !== 'warehouse') return;              // warehouse-only attributes
      if (s.title.test(t) || (s.jt && jt.indexOf(s.jt) !== -1)) out.push(s.key);
    });
    return out;
  }
  // full searchable text incl. job_highlights (drives Requirements derivation)
  function jobText(job){
    var t = (job.title || '') + ' ' + (job.company || '');
    var b = job.job_highlights;
    if (Array.isArray(b)) b.forEach(function(x){ (x && x.items || []).forEach(function(it){ t += ' ' + it; }); });
    return t.toLowerCase();
  }
  function deriveReqs(job){ var t = jobText(job); return REQS.filter(function(r){ return r.re.test(t); }).map(function(r){ return r.key; }); }
  function roleLabel(key) {
    var all = allRoles(), i;
    for (i=0;i<all.length;i++){ if(all[i].key===key) return all[i].label; }
    for (i=0;i<SHIFTS.length;i++){ if(SHIFTS[i].key===key) return SHIFTS[i].label; }
    return key;
  }
  // slug or free text -> role key, optionally scoped to one vertical's roles
  function roleFromString(s, vertical) {
    s = (s||'').toLowerCase(); if(!s) return null;
    var pool = (vertical && TAXONOMY[vertical]) ? TAXONOMY[vertical].roles : allRoles(), i;
    for (i=0;i<pool.length;i++){ if(pool[i].slug.test(s)) return pool[i].key; }
    for (i=0;i<pool.length;i++){ if(pool[i].title.test(s)) return pool[i].key; }
    return null;
  }
  function shiftFromString(s) {
    s = (s||'').toLowerCase(); if(!s) return null;
    for (var i=0;i<SHIFTS.length;i++){ if(SHIFTS[i].title.test(s)) return SHIFTS[i].key; }
    return null;
  }
  // security signal wins over warehouse so "warehouse-security" resolves to security
  function verticalFromString(s) {
    s = (s||'').toLowerCase(); if(!s) return null;
    if (/security|guard|officer|patrol|unarmed|\barmed/.test(s)) return 'security';
    if (/warehouse|forklift|package|parcel|logistics|distribution|fulfillment/.test(s)) return 'warehouse';
    return null;
  }

  /* ───────────────── DATES ───────────────── */
  function bestDate(job) {
    var d = job.date_pulled || job.posted || '';
    var t = Date.parse(d);
    return isNaN(t) ? 0 : t;
  }
  function isNew(job) {
    var t = Date.parse(job.posted || job.date_pulled || '');
    if (isNaN(t)) return false;
    return (Date.now() - t) <= (10 * 24 * 60 * 60 * 1000);
  }
  // "New" badge in the mock is TODAY only.
  function isToday(job) {
    var t = Date.parse(job.posted || job.date_pulled || '');
    if (isNaN(t)) return false;
    return (Date.now() - t) < (24 * 60 * 60 * 1000);
  }
  function postedTime(job) {
    var t = Date.parse(job.posted || job.date_pulled || '');
    return isNaN(t) ? 0 : t;
  }
  function withinDays(job, days) {
    var t = postedTime(job);
    if (!t) return false;
    return (Date.now() - t) <= (days * 24 * 60 * 60 * 1000);
  }
  function agoLabel(job){
    var t = postedTime(job); if(!t) return '';
    var days = Math.floor((Date.now() - t) / 864e5);
    if (days <= 0) return 'today';
    if (days === 1) return '1 day ago';
    if (days < 7) return days + ' days ago';
    if (days < 14) return '1 week ago';
    if (days < 30) return Math.floor(days/7) + ' weeks ago';
    if (days < 60) return '1 month ago';
    return Math.floor(days/30) + ' months ago';
  }

  /* ───────────────── MATCHERS ───────────────── */
  function postedDays(v){ return v === 'week' ? 7 : (v === '3' ? 3 : (v === '1' ? 1 : 0)); }
  function qMatch(job){ var q = filters.q.toLowerCase().trim(); if(!q) return true; return ((job.title||'')+' '+(job.company||'')).toLowerCase().indexOf(q) !== -1; }
  function locChipValue(){ var v = filters.loc||''; if(v.indexOf('metro:')===0) return v; if(v.indexOf('loc:')===0){ var rest=v.slice(4), s=rest.indexOf('::'); return 'metro:'+(s===-1?rest:rest.slice(0,s)); } return ''; }
  function locMatch(job, val){ if(!val) return true; if(val.indexOf('metro:')===0) return job._metro === val.slice(6); if(val.indexOf('loc:')===0){ var rest=val.slice(4), s=rest.indexOf('::'); if(s===-1) return job._locCity === rest; return job._metro === rest.slice(0,s) && job._locCity === rest.slice(s+2); } return true; }
  function verticalMatch(job){ return !filters.vertical || job._vertical === filters.vertical; }
  function shiftMatch(job){ return !filters.shift || (job._shifts||[]).indexOf(filters.shift) !== -1; }
  function reqMatch(job){ if(!filters.reqs.length) return true; var r = job._reqs||[]; return filters.reqs.every(function(k){ return r.indexOf(k) !== -1; }); }
  function payMatch(job){
    if(filters.pay && !((job.pay_min != null) || !!(job.pay||'').trim())) return false;
    if(filters.payMin){ var v = payValue(job); if(!(v >= filters.payMin)) return false; }
    return true;
  }
  function postedMatch(job){ if(!filters.posted) return true; var d = postedDays(filters.posted); return !d || withinDays(job, d); }
  function roleMatch(job){ return !filters.role || job._roles.indexOf(filters.role) !== -1; }

  function jobsMatching(except){
    return ALL_JOBS.filter(function(job){
      if(except !== 'q' && !qMatch(job)) return false;
      if(except !== 'loc' && !locMatch(job, filters.loc)) return false;
      if(except !== 'vertical' && !verticalMatch(job)) return false;
      if(except !== 'shift' && !shiftMatch(job)) return false;
      if(except !== 'req' && !reqMatch(job)) return false;
      if(except !== 'pay' && !payMatch(job)) return false;
      if(except !== 'posted' && !postedMatch(job)) return false;
      if(except !== 'role' && !roleMatch(job)) return false;
      return true;
    });
  }

  /* ───────────────── FILTER + RENDER ───────────────── */
  function applyFilters(repass){
    FILTERED = jobsMatching(null);
    sortJobs(FILTERED);
    shown = 0;
    renderRows(true);
    updateMeta();
    renderActive();
    renderPayPanel();
    var corrected = refreshFacets();
    if (corrected && !repass) applyFilters(true);
  }

  function esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  // Clean display pay: prefer the structured pay_min/max/unit (parsed + validated at
  // ingest) so the row never shows the raw string's upstream mojibake (e.g. "36K�48K").
  var PAY_UNIT_WORD = { HOUR:'per hour', DAY:'per day', WEEK:'per week', MONTH:'per month', YEAR:'per year' };
  function fmtMoney(v){ return v >= 1000 ? '$' + Math.round(v/1000) + 'K' : '$' + (v % 1 === 0 ? v : v.toFixed(2)); }
  // -> { big:'$18–$22', unit:'per hour' } or null when there's no clean pay.
  function displayPaySplit(job){
    var unit = (job.pay_unit || '').toUpperCase();
    if (job.pay_min != null && PAY_UNIT_WORD[unit]) {
      var lo = fmtMoney(job.pay_min);
      var big = (job.pay_max != null && job.pay_max !== job.pay_min) ? lo + '–' + fmtMoney(job.pay_max) : lo;
      return { big: big, unit: PAY_UNIT_WORD[unit] };
    }
    var raw = (job.pay || '').trim();
    if (raw && raw.indexOf('�') === -1) return { big: raw, unit: '' };
    return null;   // hide unrepairable mojibake / no pay
  }

  // One plain-prose line from job_highlights: a responsibility · a qualification.
  // Row closes up cleanly (returns '') when highlights are absent (~5%).
  function cleanItem(s){
    s = (s||'').replace(/�/g,'').replace(/\s+/g,' ').trim();
    if(!s) return '';
    if(/more items?\(s\)/i.test(s)) return '';                 // "19 more items(s)" noise
    if(s.length < 14) return '';                               // headers like "SAP"
    if(/[:]\s*$/.test(s)) return '';                           // section header ending with ':'
    if(s === s.toUpperCase() && /^[A-Z0-9 /&,.-]+$/.test(s)) return '';  // ALLCAPS header
    // capitalized words joined by / or & with no sentence body ("Background / Experience / Skills")
    if(s.split(' ').length <= 6 && /^[A-Za-z][\w.-]*(?:\s*[/&]\s*[A-Za-z][\w.-]*)+$/.test(s)) return '';
    s = s.replace(/^job summary:\s*/i,'').replace(/^summary:\s*/i,'');
    if(s.length > 150) s = s.slice(0,148).replace(/\s+\S*$/,'') + '…';
    return s;
  }
  function highlightParts(job){
    var blocks = job.job_highlights;
    if(!Array.isArray(blocks) || !blocks.length) return null;
    function pick(names){
      for(var i=0;i<blocks.length;i++){
        var t = ((blocks[i] && blocks[i].title) || '').toLowerCase();
        if(names.some(function(n){ return t.indexOf(n) !== -1; })){
          var items = (blocks[i] && blocks[i].items) || [];
          for(var k=0;k<items.length;k++){ var c = cleanItem(items[k]); if(c) return c; }
        }
      }
      return '';
    }
    var resp = pick(['responsibilit','duties','summary','what you']);
    var qual = pick(['qualif','require','skills','experience']);
    if(resp && qual && resp !== qual) return { a: resp, b: qual };
    var one = resp || qual;
    return one ? { a: one, b: '' } : null;
  }

  var SHIFT_CLASS = { 'overnight':'night', 'weekend':'wknd', 'part-time':'part', 'full-time':'full', 'no-experience':'noexp' };
  function rowHTML(job) {
    var href = esc((job.apply_link || '').trim()) || '#';
    var loc = esc(job.location || job.city || '');
    var age = agoLabel(job);
    var sub = (isToday(job) ? '<span class="new">New</span>' : '') +
      '<b>' + esc(job.company || 'Employer') + '</b>' +
      (loc ? ' · ' + loc : '') + (age ? ' · ' + age : '');
    var hp = highlightParts(job);
    var hl = hp ? '<div class="hl">' + esc(hp.a) + (hp.b ? '<span>·</span>' + esc(hp.b) : '') + '</div>' : '';
    var tags = '';
    (job._shifts||[]).forEach(function(s){ var c = SHIFT_CLASS[s]; if(c) tags += '<span class="tag ' + c + '">' + esc(roleLabel(s)) + '</span>'; });
    if(job._roles[0]) tags += '<span class="tag">' + esc(roleLabel(job._roles[0])) + '</span>';
    var pp = displayPaySplit(job);
    var pay = pp
      ? '<div class="pay"><b>' + esc(pp.big) + '</b>' + (pp.unit ? '<i>' + esc(pp.unit) + '</i>' : '') + '</div>'
      : '<div class="pay none"><b>Pay not listed</b></div>';
    var linkAttrs = ' target="_blank" rel="noopener noreferrer" data-i="' + job._i + '" onclick="return bbjCardApply(this, event)"';
    return '<li class="row">' +
        '<div class="rowmain">' +
          '<div class="rowtitle"><a href="' + href + '"' + linkAttrs + '>' + esc(job.title) + '</a></div>' +
          '<div class="rowsub">' + sub + '</div>' +
          hl +
          (tags ? '<div class="tags">' + tags + '</div>' : '') +
        '</div>' +
        pay +
        '<a class="view" href="' + href + '"' + linkAttrs + ' aria-label="View and apply: ' + esc(job.title) + '">View</a>' +
      '</li>';
  }

  function renderRows(reset) {
    var rows = document.getElementById('rows');
    if(!rows) return;
    if (!FILTERED.length) {
      rows.innerHTML = '<li class="feed-msg">' +
        '<div class="fm-title">No matching jobs right now</div>' +
        '<div class="fm-sub">Try clearing a filter, or get alerted the moment a match posts.</div>' +
        '<a href="#" class="view" onclick="openAlerts();return false;" style="display:inline-block;margin-top:14px;padding:11px 26px;">Get Job Alerts</a>' +
      '</li>';
      var lm0 = document.getElementById('loadMoreWrap'); if(lm0) lm0.style.display = 'none';
      return;
    }
    var next = FILTERED.slice(shown, shown + PAGE_SIZE);
    var html = next.map(rowHTML).join('');
    if (reset) rows.innerHTML = html; else rows.insertAdjacentHTML('beforeend', html);
    shown += next.length;
    var lm = document.getElementById('loadMoreWrap');
    if(lm) lm.style.display = (shown < FILTERED.length) ? 'block' : 'none';
    var lb = document.getElementById('loadMoreBtn');
    if(lb) lb.textContent = 'Load more jobs (' + (FILTERED.length - shown) + ' more)';
  }
  function loadMore() { renderRows(false); }

  function updateMeta() {
    var el = document.getElementById('resultsCount');
    var n = FILTERED.length;
    if(el){
      el.innerHTML = n + ' <span>' + (n === 1 ? 'open position' : 'open positions') + '</span>';
    }
    // Keep the hub "End of N openings" rule in sync with the live filtered count (present
    // only on baked hub pages). Guarded, so the general board is unaffected.
    var er = document.getElementById('endCount');
    if(er){ er.textContent = n; }
    // "Filters" badge = active drawer filters
    var badge = (!PRESET.role && filters.role ? 1 : 0) +
                (filters.shift && filters.shift !== PRESET.shift ? 1 : 0) +
                filters.reqs.length + (filters.payMin ? 1 : 0) + (filters.pay ? 1 : 0) + (filters.posted ? 1 : 0);
    var dot = document.getElementById('moreDot'), mb = document.getElementById('moreBtn');
    if(dot) dot.textContent = badge;
    if(mb) mb.classList.toggle('has', badge > 0);
    // sort buttons
    var sn = document.getElementById('sortNew'), sp = document.getElementById('sortPay');
    if(sn) sn.setAttribute('aria-pressed', filters.sort === 'newest');
    if(sp) sp.setAttribute('aria-pressed', filters.sort === 'pay');
  }

  /* ───────────────── ACTIVE PILLS ───────────────── */
  function metroFromLoc(v){
    if(!v) return '';
    if(v.indexOf('metro:')===0) return metroLabel(v.slice(6));
    if(v.indexOf('loc:')===0){ var rest=v.slice(4).split('::'); return rest[1] || metroLabel(rest[0]); }
    return v;
  }
  function lockedPill(label){ return '<span class="pill locked">' + esc(label) + '</span>'; }
  function userPill(label, g, v){
    return '<span class="pill">' + esc(label) +
      '<button type="button" aria-label="Remove filter" onclick="removeFilter(\'' + g + '\',\'' + esc(v).replace(/'/g,'') + '\')">×</button></span>';
  }
  function renderActive(){
    var el = document.getElementById('active'); if(!el) return;
    var html = '';
    // locked preset context (no remove control)
    if(PRESET.vertical && TAXONOMY[PRESET.vertical]) html += lockedPill(TAXONOMY[PRESET.vertical].label);
    if(PRESET.loc) html += lockedPill(metroFromLoc(PRESET.loc));
    if(PRESET.role) html += lockedPill(roleLabel(PRESET.role));
    if(PRESET.shift) html += lockedPill(roleLabel(PRESET.shift));
    // user-added filters (removable)
    var user = [];
    if(filters.q) user.push(userPill('“' + filters.q + '”', 'q', ''));
    if(filters.vertical && filters.vertical !== PRESET.vertical && TAXONOMY[filters.vertical]) user.push(userPill(TAXONOMY[filters.vertical].label, 'vertical', ''));
    if(filters.loc && filters.loc !== PRESET.loc) user.push(userPill(metroFromLoc(filters.loc), 'loc', ''));
    if(filters.role && filters.role !== PRESET.role) user.push(userPill(roleLabel(filters.role), 'role', ''));
    if(filters.shift && filters.shift !== PRESET.shift) user.push(userPill(roleLabel(filters.shift), 'shift', ''));
    filters.reqs.forEach(function(r){ user.push(userPill(reqLabel(r), 'req', r)); });
    if(filters.payMin) user.push(userPill('$' + filters.payMin + '+/hr', 'paymin', ''));
    if(filters.pay) user.push(userPill('Pay listed', 'pay', ''));
    if(filters.posted) user.push(userPill(postedLabel(filters.posted), 'posted', ''));
    html += user.join('');
    if(user.length) html += '<button type="button" class="clearall" onclick="clearFilters()">Clear filters</button>';
    el.innerHTML = html;
  }
  function postedLabel(v){ for(var i=0;i<POSTED_OPTS.length;i++){ if(POSTED_OPTS[i].v===v) return POSTED_OPTS[i].label; } return v; }
  function removeFilter(g, v){
    if(g==='q'){ filters.q=''; var si=document.getElementById('searchInput'); if(si) si.value=''; }
    else if(g==='vertical'){ filters.vertical = PRESET.vertical || ''; if(!rolesForVertical(filters.vertical).some(function(r){return r.key===filters.role;})) filters.role = PRESET.role || ''; }
    else if(g==='loc'){ filters.loc = PRESET.loc || DEFAULT_LOC; }
    else if(g==='role'){ filters.role = PRESET.role || ''; }
    else if(g==='shift'){ filters.shift = PRESET.shift || ''; }
    else if(g==='req'){ var i=filters.reqs.indexOf(v); if(i!==-1) filters.reqs.splice(i,1); }
    else if(g==='paymin'){ filters.payMin = 0; }
    else if(g==='pay'){ filters.pay = false; }
    else if(g==='posted'){ filters.posted = ''; }
    syncRail();
    applyFilters();
  }

  /* ───────────────── LOCATION FACET HELPERS ───────────────── */
  function metrosFrom(base){
    var m = {};
    base.forEach(function(j){
      var k = j._metro || 'Other';
      if(!m[k]) m[k] = { count:0, cities:{} };
      m[k].count++;
      var L = j._locCity || j._loc;
      if(L){ if(!m[k].cities[L]) m[k].cities[L] = { city: L, count:0 }; m[k].cities[L].count++; }
    });
    return m;
  }
  function metroOrder(m){
    return Object.keys(m).sort(function(a,b){ if(a==='DFW') return -1; if(b==='DFW') return 1; return (m[b].count-m[a].count) || a.localeCompare(b); });
  }
  function buildLocationOptions(base){
    var m = metrosFrom(base), names = metroOrder(m), html = '';
    html += '<option value="">All locations ('+base.length+')</option>';
    names.forEach(function(name){
      var friendly = METRO_FRIENDLY[name] || (name + ' Area');
      html += '<optgroup label="'+esc(friendly)+'">';
      html += '<option value="metro:'+esc(name)+'">'+esc(name)+' — all ('+m[name].count+')</option>';
      var locs = Object.keys(m[name].cities).sort(function(a,b){ return m[name].cities[a].city.localeCompare(m[name].cities[b].city); });
      locs.forEach(function(L){ var c = m[name].cities[L]; html += '<option value="loc:'+esc(name)+'::'+esc(L)+'">'+esc(c.city)+' ('+c.count+')</option>'; });
      html += '</optgroup>';
    });
    return html || '<option value="">No locations available</option>';
  }
  function metroLabel(name){
    var keys = Object.keys(METRO_FRIENDLY), i;
    for(i=0;i<keys.length;i++){ if(keys[i].toLowerCase() === String(name).toLowerCase()) return METRO_FRIENDLY[keys[i]]; }
    return String(name).replace(/\S+/g, function(w){ return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); });
  }

  /* ───────────────── RAIL DROPDOWNS ───────────────── */
  function buildVerticalOptions(base){
    var counts = { security:0, warehouse:0 };
    base.forEach(function(j){ if(counts[j._vertical] != null) counts[j._vertical]++; });
    var html = '<option value="">All categories ('+base.length+')</option>';
    Object.keys(TAXONOMY).forEach(function(v){ html += '<option value="'+v+'">'+esc(TAXONOMY[v].label)+' ('+counts[v]+')</option>'; });
    return html;
  }
  function buildShiftOptions(base){
    var html = '<option value="">Any shift</option>';   // NEVER defaults to full-time
    SHIFTS.forEach(function(s){
      var n = base.filter(function(j){ return (j._shifts||[]).indexOf(s.key) !== -1; }).length;
      if (s.wh && n === 0) return;                        // hide warehouse-only attrs off-context
      html += '<option value="'+s.key+'">'+esc(s.label)+' ('+n+')</option>';
    });
    return html;
  }
  function syncRail(){
    var ls = document.getElementById('locSelect');   if(ls){ ls.value = filters.loc || '';         ls.disabled = !!PRESET.loc; }
    var vs = document.getElementById('vertSelect');  if(vs){ vs.value = filters.vertical || '';    vs.disabled = !!PRESET.vertical; }
    var ss = document.getElementById('shiftSelect'); if(ss){ ss.value = filters.shift || '';       ss.disabled = !!PRESET.shift; }
  }
  function refreshFacets(){
    var corrected = false;
    // LOCATION options (counts reflect everything except loc itself)
    var ls = document.getElementById('locSelect');
    if(ls){ ls.innerHTML = buildLocationOptions(jobsMatching('loc')); ls.value = filters.loc || ''; if(ls.value !== (filters.loc||'')){ /* selection vanished */ } }
    // VERTICAL options
    var vs = document.getElementById('vertSelect');
    if(vs){ vs.innerHTML = buildVerticalOptions(jobsMatching('vertical')); vs.value = filters.vertical || ''; }
    // SHIFT options
    var ss = document.getElementById('shiftSelect');
    if(ss){ ss.innerHTML = buildShiftOptions(jobsMatching('shift')); ss.value = filters.shift || ''; }
    syncRail();
    return corrected;
  }

  /* ───────────────── DRAWER ───────────────── */
  function optHTML(g, v, label, pressed){
    return '<button type="button" class="opt" data-g="'+g+'" data-v="'+esc(v)+'" aria-pressed="'+(pressed?'true':'false')+'">'+esc(label)+'</button>';
  }
  function renderDrawer(){
    var body = document.getElementById('drawerBody'); if(!body) return;
    var base = jobsMatching(null), html = '';
    // ROLE — hidden when a hub locks the role
    if(!PRESET.role){
      var roles = rolesForVertical(filters.vertical);
      html += '<div class="fgroup"><div class="flabel">Role</div><div class="opts">';
      html += optHTML('role','', 'Any role', !filters.role);
      roles.forEach(function(r){ html += optHTML('role', r.key, r.label, filters.role===r.key); });
      html += '</div></div>';
    }
    // SHIFT (mirrors the rail dropdown)
    if(!PRESET.shift){
      html += '<div class="fgroup"><div class="flabel">Shift &amp; schedule</div><div class="opts">';
      html += optHTML('shift','', 'Any shift', !filters.shift);
      SHIFTS.forEach(function(s){ if(s.wh && filters.vertical!=='warehouse') return; html += optHTML('shift', s.key, s.label, filters.shift===s.key); });
      html += '</div></div>';
    }
    // REQUIREMENTS (multi)
    html += '<div class="fgroup"><div class="flabel">Requirements</div><div class="opts">';
    REQS.forEach(function(r){ html += optHTML('req', r.key, r.label, filters.reqs.indexOf(r.key)!==-1); });
    html += '</div></div>';
    // PAY
    html += '<div class="fgroup"><div class="flabel">Pay</div><div class="opts">';
    [18,22,26].forEach(function(n){ html += optHTML('paymin', String(n), '$'+n+'+/hr', filters.payMin===n); });
    html += optHTML('pay','on','Pay listed only', filters.pay);
    html += '</div></div>';
    // POSTED
    html += '<div class="fgroup"><div class="flabel">Date posted</div><div class="opts">';
    POSTED_OPTS.forEach(function(o){ if(o.v==='') return; html += optHTML('posted', o.v, o.label, filters.posted===o.v); });
    html += '</div></div>';
    body.innerHTML = html;
  }
  function openDrawer(){ renderDrawer(); document.getElementById('drawer').classList.add('open'); document.getElementById('scrim').classList.add('open'); document.body.style.overflow='hidden'; }
  function closeDrawer(){ document.getElementById('drawer').classList.remove('open'); document.getElementById('scrim').classList.remove('open'); document.body.style.overflow=''; }

  /* ───────────────── FILTER HANDLERS ───────────────── */
  function wire(id, ev, fn){ var el = document.getElementById(id); if(el) el.addEventListener(ev, fn); }
  wire('searchInput','input', function(e){ filters.q = e.target.value; applyFilters(); });
  wire('locSelect','change', function(e){ filters.loc = e.target.value; applyFilters(); });
  wire('vertSelect','change', function(e){
    filters.vertical = e.target.value;
    if(!rolesForVertical(filters.vertical).some(function(r){ return r.key===filters.role; })) filters.role = '';
    applyFilters();
  });
  wire('shiftSelect','change', function(e){ filters.shift = e.target.value; applyFilters(); });
  (function(){
    var db = document.getElementById('drawerBody');
    if(!db) return;
    db.addEventListener('click', function(e){
      var b = e.target.closest('.opt'); if(!b) return;
      var g = b.getAttribute('data-g'), v = b.getAttribute('data-v');
      if(g==='req'){ var i=filters.reqs.indexOf(v); if(i===-1) filters.reqs.push(v); else filters.reqs.splice(i,1); }
      else if(g==='pay'){ filters.pay = !filters.pay; }
      else if(g==='paymin'){ var n=parseInt(v,10); filters.payMin = (filters.payMin===n) ? 0 : n; }
      else if(g==='role'){ filters.role = v; }
      else if(g==='shift'){ filters.shift = v; }
      else if(g==='posted'){ filters.posted = v; }
      renderDrawer();
      applyFilters();
    });
  })();
  function setSort(s){ filters.sort = s; updateMeta(); applyFilters(); }

  function clearFilters() {
    // Reset to the hub PRESET (or the neutral all-verticals state if no preset), NOT to
    // an empty state — so clearing on a warehouse hub never reveals security jobs.
    filters = { q:'', loc:(PRESET.loc||DEFAULT_LOC), vertical:(PRESET.vertical||''),
                role:(PRESET.role||''), shift:(PRESET.shift||''), reqs:[], payMin:0, pay:false, posted:'', sort:'newest' };
    var si = document.getElementById('searchInput'); if(si) si.value = '';
    syncRail();
    applyFilters();
    var b = document.getElementById('board');
    if(b) window.scrollTo({ top: b.offsetTop - 60, behavior: 'smooth' });
  }

  /* ───────────────── PAY PANEL (general board only; hubs bake it) ───────────────── */
  function pctl(sorted, p){ if(!sorted.length) return 0; var idx = Math.min(sorted.length-1, Math.max(0, Math.round((p/100)*(sorted.length-1)))); return sorted[idx]; }
  function payRangeStats(set){
    var vals = set.map(payValue).filter(function(v){ return v > 0; }).sort(function(a,b){ return a-b; });
    if(vals.length < 4) return null;
    return { n: vals.length, total: set.length,
             lo: pctl(vals,10), q1: pctl(vals,25), med: pctl(vals,50), q3: pctl(vals,75), hi: pctl(vals,90) };
  }
  function money0(v){ return '$' + Math.round(v); }
  function payRangeHTML(st, title){
    var span = (st.hi - st.lo) || 1;
    var fL = Math.max(0, (st.q1 - st.lo) / span * 100);
    var fR = Math.max(0, (st.hi - st.q3) / span * 100);
    var mid = Math.min(100, Math.max(0, (st.med - st.lo) / span * 100));
    return '<h2>' + esc(title) + '</h2>' +
      '<p class="note">Hourly-equivalent pay across ' + st.n + ' of ' + st.total + ' current listings that publish a rate.</p>' +
      '<div class="range"><div class="rangebar">' +
        '<div class="rangefill" style="left:' + fL.toFixed(1) + '%;right:' + fR.toFixed(1) + '%"></div>' +
        '<div class="rangemid" style="left:' + mid.toFixed(1) + '%"></div>' +
      '</div><div class="rangelabels">' +
        '<div class="rl lo"><div class="v">' + money0(st.lo) + '</div><div class="k">Low</div></div>' +
        '<div class="rl mid"><div class="v">' + money0(st.med) + '</div><div class="k">Median /hr</div></div>' +
        '<div class="rl hi"><div class="v">' + money0(st.hi) + '</div><div class="k">High</div></div>' +
      '</div></div>';
  }
  function renderPayPanel(){
    if(window.BBJ_BOARD_PRESET) return;   // hubs ship a baked panel; never overwrite it
    var wrap = document.getElementById('payWrap'); if(!wrap) return;
    var metro = locChipValue();
    if(!filters.vertical || !metro){ wrap.style.display = 'none'; return; }
    var set = ALL_JOBS.filter(function(j){ return j._vertical === filters.vertical && ('metro:'+j._metro) === metro; });
    var st = payRangeStats(set);
    if(!st){ wrap.style.display = 'none'; return; }
    var label = (TAXONOMY[filters.vertical] ? TAXONOMY[filters.vertical].label : '') + ' pay in ' + metroLabel(metro.slice(6));
    document.getElementById('payPanel').innerHTML = payRangeHTML(st, label);
    wrap.style.display = '';
  }

  /* ───────────────── APPLY + GATE ───────────────── */
  function getViews() { var m = document.cookie.match(/bbj_views=(\d+)/); return m ? parseInt(m[1],10) : 0; }
  function setViews(n) { document.cookie = 'bbj_views=' + n + '; max-age=2592000; path=/; SameSite=Lax'; }

  function pushApplyDL() {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'job_apply_click',
      job_title: pendingJob && pendingJob.title,
      company: pendingJob && pendingJob.company,
      role: (pendingJob && pendingJob._roles && pendingJob._roles[0]) || 'general',
      source: pendingJob && pendingJob.via,
      apply_link: pendingUrl,
      page_url: window.location.href
    });
  }
  // Row anchor onclick. Return true to let the href open the employer (crawlable) on an
  // allowed view (registered, or the first FREE_VIEWS this session); otherwise block the
  // navigation and open the gate. Mirrors handleIndexApply() in js/bbj-feed.js.
  window.bbjCardApply = function(el, event){
    var i = parseInt(el.getAttribute('data-i'), 10);
    pendingJob = ALL_JOBS[i] || null;
    pendingUrl = (el.getAttribute('href') || '').trim();
    if (!pendingUrl || pendingUrl === '#') { if(event) event.preventDefault(); return false; }
    if (isRegistered()) { pushApplyDL(); return true; }
    var v = getViews();
    if (v < FREE_VIEWS) { setViews(v + 1); pushApplyDL(); return true; }
    if (event) event.preventDefault();
    openGate();
    return false;
  };

  function openGate() {
    if (pendingUrl) {
      try { sessionStorage.setItem('bbj_pending_job', pendingUrl); } catch(e) {}
    }
    // Inline overlay — same 2-click gate as the landing pages.
    // Falls back to the register page only if the overlay script failed to load.
    if (typeof bbjAccOpen === 'function') { bbjAccOpen(); return; }
    var btn = document.getElementById('gateCtaBtn');
    var loginLink = document.getElementById('gateLoginLink');
    if (btn) btn.href = '/register.html?return=job-board';
    if (loginLink) loginLink.href = '/login.html?return=job-board';
    document.getElementById('gateModal').classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  function closeGate() { var g=document.getElementById('gateModal'); if(g) g.classList.remove('open'); document.body.style.overflow=''; }
  function toggleGateSms() {}
  function submitGate() {}

  /* ───────────────── ALERTS MODAL ───────────────── */
  function openAlerts() {
    // Already registered/signed in — never gate; send to dashboard.
    if (isRegistered()) { window.location.href = '/dashboard.html'; return; }
    // Inline alerts overlay — same flow as the landing pages.
    // Falls back to the modal only if the overlay script failed to load.
    if (typeof bbjAlertOpen === 'function') { bbjAlertOpen(); return; }
    var btn = document.getElementById('alertsCtaBtn');
    if (btn) { btn.href = '/register.html'; btn.textContent = 'Create Free Account →'; }
    var a=document.getElementById('alertsModal'); if(a) a.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  function closeAlerts() { var a=document.getElementById('alertsModal'); if(a) a.classList.remove('open'); document.body.style.overflow=''; }
  function submitAlerts() {}

  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') { closeGate(); closeAlerts(); closeDrawer(); } });

  /* ───────────────── JOB POSTING STRUCTURED DATA (schema.org / Google for Jobs) ───────────────── */
  function parseLoc(loc) {
    var parts = (loc || '').split(',').map(function(s){ return s.trim(); });
    return { city: parts[0] || '', region: parts[1] || '', country: 'US' };
  }
  // Prefer the structured pay_min/max/unit from the feed; more accurate than string parse.
  function structuredSalary(job) {
    if (job.pay_min == null || !job.pay_unit) return null;
    var unit = ({HOUR:'HOUR',DAY:'DAY',WEEK:'WEEK',MONTH:'MONTH',YEAR:'YEAR'})[String(job.pay_unit).toUpperCase()];
    if (!unit) return null;
    var qv = { '@type':'QuantitativeValue', unitText: unit };
    if (job.pay_max != null && job.pay_max !== job.pay_min) { qv.minValue = job.pay_min; qv.maxValue = job.pay_max; }
    else { qv.value = job.pay_min; }
    return { '@type':'MonetaryAmount', currency:'USD', value: qv };
  }
  function parseSalary(pay) {
    if (!pay || !pay.trim()) return null;
    var unit = /year|annual|\/yr|yr\b/i.test(pay) ? 'YEAR' : (/week/i.test(pay) ? 'WEEK' : (/month/i.test(pay) ? 'MONTH' : 'HOUR'));
    var nums = (pay.match(/\d+(\.\d+)?/g) || []).map(parseFloat);
    if (!nums.length) return null;
    var qv = { '@type': 'QuantitativeValue', unitText: unit };
    if (nums.length >= 2) { qv.minValue = nums[0]; qv.maxValue = nums[1]; } else { qv.value = nums[0]; }
    return { '@type': 'MonetaryAmount', currency: 'USD', value: qv };
  }
  function empType(jt) {
    var t = (jt || '').toLowerCase(); var arr = [];
    if (t.indexOf('full') !== -1) arr.push('FULL_TIME');
    if (t.indexOf('part') !== -1) arr.push('PART_TIME');
    if (t.indexOf('contract') !== -1) arr.push('CONTRACTOR');
    if (t.indexOf('temp') !== -1) arr.push('TEMPORARY');
    if (!arr.length) return undefined;
    return arr.length === 1 ? arr[0] : arr;
  }
  function isoDate(d) { var t = Date.parse(d); return isNaN(t) ? null : new Date(t).toISOString().slice(0, 10); }
  function addDaysISO(d, days) { var t = Date.parse(d); return isNaN(t) ? null : new Date(t + days * 864e5).toISOString().slice(0, 10); }

  function buildJobPosting(job) {
    if (!(job.title || '').trim()) return null;
    var posted = isoDate(job.posted) || isoDate(job.date_pulled);
    var loc = parseLoc(job.location || job.city || '');
    var desc = (job.description && job.description.trim())
      ? job.description.trim()
      : (job.title + (job.company ? ' with ' + job.company : '') + (job.location ? ' in ' + job.location : '') + '. '
         + ((job.job_type || '').trim() ? job.job_type + ' security position. ' : 'Security officer position. ')
         + ((job.pay || '').trim() ? 'Pay: ' + job.pay + '. ' : '')
         + 'Apply now through BlackBarJobs.');
    var obj = {
      '@context': 'https://schema.org/',
      '@type': 'JobPosting',
      'title': job.title,
      'description': desc,
      'hiringOrganization': { '@type': 'Organization', 'name': job.company || 'Confidential' },
      'jobLocation': { '@type': 'Place', 'address': { '@type': 'PostalAddress', 'addressLocality': loc.city, 'addressRegion': loc.region, 'addressCountry': 'US' } },
      'identifier': { '@type': 'PropertyValue', 'name': job.company || 'BlackBarJobs', 'value': job.job_id || job.apply_link || job.title },
      'directApply': false
    };
    if (posted) { obj.datePosted = posted; obj.validThrough = addDaysISO(posted, 60); }
    var et = empType(job.job_type); if (et) obj.employmentType = et;
    var sal = structuredSalary(job) || parseSalary(job.pay); if (sal) obj.baseSalary = sal;
    if (job.apply_link) obj.url = job.apply_link;
    return obj;
  }

  function injectJsonLd(jobs) {
    var box = document.getElementById('jsonld');
    if (!box) return;
    box.textContent = '';
    jobs.forEach(function(j){
      var obj = buildJobPosting(j); if (!obj) return;
      var s = document.createElement('script');
      s.type = 'application/ld+json';
      s.textContent = JSON.stringify(obj);
      box.appendChild(s);
    });
  }

  /* ───────────────── BOOT (merge + de-dupe all tabs) ───────────────── */
  function normApply(u){ return (u||'').trim().toLowerCase().replace(/\/+$/,''); }

  /* ───────────────── DEEP LINKS (UTM / query params) ───────────────── */
  function resolveLocation(s){
    if(!s) return null;
    s = String(s).trim().toLowerCase(); if(!s) return null;
    var m = metrosFrom(ALL_JOBS), names = Object.keys(m), i, k;
    for(i=0;i<names.length;i++){ if(names[i].toLowerCase() === s) return 'metro:'+names[i]; }
    for(i=0;i<names.length;i++){ var fr=(METRO_FRIENDLY[names[i]]||'').toLowerCase(); if(fr && fr === s) return 'metro:'+names[i]; }
    for(i=0;i<names.length;i++){ var cs=Object.keys(m[names[i]].cities); for(k=0;k<cs.length;k++){ if(cs[k].toLowerCase() === s) return 'loc:'+names[i]+'::'+cs[k]; } }
    for(i=0;i<names.length;i++){ var cs2=Object.keys(m[names[i]].cities); for(k=0;k<cs2.length;k++){ if(cs2[k].toLowerCase().indexOf(s) !== -1) return 'loc:'+names[i]+'::'+cs2[k]; } }
    return null;
  }
  function resolveLocationFromHint(hint){
    if(!hint) return null;
    var m = metrosFrom(ALL_JOBS), names = Object.keys(m), i, k;
    for(i=0;i<names.length;i++){ var cs=Object.keys(m[names[i]].cities); for(k=0;k<cs.length;k++){ if(hint.indexOf(cs[k].toLowerCase()) !== -1) return 'loc:'+names[i]+'::'+cs[k]; } }
    for(i=0;i<names.length;i++){ if(hint.indexOf(names[i].toLowerCase()) !== -1) return 'metro:'+names[i]; var fr=(METRO_FRIENDLY[names[i]]||'').toLowerCase(); if(fr && hint.indexOf(fr) !== -1) return 'metro:'+names[i]; }
    return null;
  }

  function applyUrlFilters(){
    var p; try { p = new URLSearchParams(window.location.search); } catch(e){ p = new URLSearchParams(''); }
    // A hub page sets window.BBJ_BOARD_PRESET = {vertical, metro, role, shift, q}. It is
    // the base filter state; any real URL param overrides it. This is what pre-filters a
    // hub to its vertical+metro+modifier and (via PRESET) locks clearFilters to it, so
    // clearing never drops a warehouse visitor onto security jobs.
    var PB = window.BBJ_BOARD_PRESET || {};
    function gp(k){ var v = p.get(k); if(v!=null && v!=='') return v; return (PB[k]!=null && PB[k]!=='') ? String(PB[k]) : null; }
    var changed = false;

    var q = gp('q') || gp('search');
    if(q){ filters.q = q; var si=document.getElementById('searchInput'); if(si) si.value = q; changed = true; }

    var posted = (gp('posted') || '').toLowerCase();
    if(posted==='week'||posted==='7'){ filters.posted='week'; changed=true; }
    else if(posted==='3'){ filters.posted='3'; changed=true; }
    else if(posted==='1'||posted==='today'){ filters.posted='1'; changed=true; }

    if(/^(1|true|yes)$/i.test(gp('pay')||'')){ filters.pay = true; changed=true; }

    var sort = (gp('sort')||'').toLowerCase();
    if(sort==='pay'||sort==='company'||sort==='newest'){ filters.sort=sort; changed=true; }

    var roleParam = gp('role') || '';
    var hint = [roleParam, gp('city'), gp('metro'), gp('location'), p.get('utm_campaign'), p.get('utm_content'), p.get('utm_term')].filter(Boolean).join(' ').toLowerCase();

    // VERTICAL — explicit ?vertical/preset, else inferred from the role slug / hint (security wins)
    var vertical = (gp('vertical')||'').toLowerCase();
    if(!(vertical in TAXONOMY)) vertical = verticalFromString(roleParam) || verticalFromString(hint) || '';
    if(vertical){ filters.vertical = vertical; PRESET.vertical = vertical; changed = true; }

    // ROLE — scoped to the resolved vertical so "warehouse-security" never -> warehouse associate
    var role = roleFromString(roleParam, filters.vertical) || roleFromString(hint, filters.vertical);
    if(role){ filters.role = role; PRESET.role = role; changed = true; }

    // SHIFT & attribute — explicit ?shift/preset, then ?schedule full/part, then the hint
    var shiftParam = (gp('shift')||'').toLowerCase();
    var shift = null;
    for(var k=0;k<SHIFTS.length;k++){ if(SHIFTS[k].key===shiftParam){ shift=shiftParam; break; } }
    if(!shift){ var sched=(gp('schedule')||gp('type')||'').toLowerCase(); shift = sched.indexOf('full')!==-1?'full-time':(sched.indexOf('part')!==-1?'part-time':null); }
    if(!shift) shift = shiftFromString(roleParam) || shiftFromString(hint);
    if(shift){ filters.shift = shift; PRESET.shift = shift; changed = true; }

    // LOCATION — metro/city to the two-level loc value
    var locVal = resolveLocation(gp('metro') || gp('city') || gp('location')) || resolveLocationFromHint(hint);
    if(locVal){ filters.loc = locVal; PRESET.loc = locVal; changed = true; }

    if(changed){
      syncRail();
      applyFilters();
    }
  }

  function boot(rawJobs) {
    var active = rawJobs.filter(function(j){ return (j.active||'').toLowerCase() === 'yes'; });
    // group duplicates that appear across tabs (same job, multiple search buckets)
    var groups = {};
    active.forEach(function(j){
      var key = normApply(j.apply_link) || ('id:' + (j.job_id||'')) || ((j.title||'') + '|' + (j.company||'')).toLowerCase();
      (groups[key] = groups[key] || []).push(j);
    });
    ALL_JOBS = Object.keys(groups).map(function(k){
      var g = groups[k];
      g.sort(function(a,b){ return bestDate(b) - bestDate(a); });
      var base = g[0];
      // richest description across the duplicates
      var desc = ''; g.forEach(function(x){ if((x.description||'').length > desc.length) desc = x.description; });
      if(desc) base.description = desc;
      // richest job_highlights across the duplicates
      g.forEach(function(x){ if(Array.isArray(x.job_highlights) && (!Array.isArray(base.job_highlights) || x.job_highlights.length > base.job_highlights.length)) base.job_highlights = x.job_highlights; });
      base._vertical = (base.vertical || 'security').toLowerCase();   // board.json vertical; legacy rows default to security
      // roles (vertical-scoped): title-derived + the stored role slug of every dup this job merged
      base._roles = deriveRoles(base);
      g.forEach(function(x){ var r = roleFromString(x.role || x.role_category, base._vertical); if(r && base._roles.indexOf(r) === -1) base._roles.unshift(r); });
      base._shifts = deriveShifts(base);                              // cross-vertical shift+attribute axis
      base._reqs = deriveReqs(base);                                  // requirements axis (title + highlights)
      base._tabs = g.length;
      base._metro = (base.city||'').trim() || 'Other';
      base._loc = (base.location||'').trim();
      base._locCity = parseLoc(base._loc).city || base._loc;
      return base;
    });
    ALL_JOBS.sort(function(a,b){ return bestDate(b) - bestDate(a); });
    ALL_JOBS.forEach(function(j, i){ j._i = i; });
    DEFAULT_LOC = '';                 // All Locations by default (national master board)
    filters.loc = DEFAULT_LOC;
    // On a hub page (BBJ_BOARD_PRESET set) the crawlable JobPosting schema is baked into
    // the <head> for the hub's own jobs; do NOT also inject 1800+ postings for every
    // board job. On /job-board (no preset) inject the full set as before.
    if (!window.BBJ_BOARD_PRESET) injectJsonLd(ALL_JOBS);
    applyFilters();
    applyUrlFilters();                // deep-link via UTM / query params (?vertical=warehouse&role=forklift&city=chicago)
  }

  /* ───────────────── FEED LOADER (master static JSON) ───────────────── */
  var FEED_URL = '/feed/board.json';   // all active jobs, written by bbj_feed_snapshot.py

  // Map the snapshot job shape -> the object shape boot() expects.
  function mapFeedJob(j) {
    var loc = (j.location || '').trim();
    return {
      active: 'yes',                                  // snapshot only contains live jobs
      apply_link: j.apply_link || '',
      title: j.title || '',
      company: j.company || '',
      location: loc,
      city: (j.market || (loc.split(',')[0] || '')).trim(),  // metro grouping
      vertical: (j.vertical || '').toLowerCase(),
      role: j.role || '',
      posted: j.posted_date || '',
      pay: j.pay || '',
      pay_min: (j.pay_min != null ? j.pay_min : null),
      pay_max: (j.pay_max != null ? j.pay_max : null),
      pay_unit: j.pay_unit || '',
      via: j.via || '',
      schedule: j.schedule || '',
      job_highlights: (Array.isArray(j.job_highlights) ? j.job_highlights : null),
      description: j.description || ''
    };
  }

  function loadFeed(){
    fetch(FEED_URL, { cache: 'no-cache' })
      .then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); })
      .then(function(data){
        var jobs = (data && data.jobs ? data.jobs : []).map(mapFeedJob);
        if(!jobs.length) throw new Error('empty');
        boot(jobs);
      })
      .catch(function(){
        var rows = document.getElementById('rows');
        if(rows) rows.innerHTML = '<li class="feed-msg"><div class="fm-title">Couldn\'t load openings</div><div class="fm-sub">Please refresh in a moment, or get job alerts and we\'ll come to you.</div><a href="#" class="view" onclick="openAlerts();return false;" style="display:inline-block;margin-top:14px;padding:11px 26px;">Get Job Alerts</a></li>';
        var rc = document.getElementById('resultsCount'); if(rc) rc.textContent = 'Listings temporarily unavailable';
      });
  }
  loadFeed();
