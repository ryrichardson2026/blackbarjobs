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
  var filters = { q: '', loc: '', vertical: '', role: '', shift: '', pay: false, posted: '', sort: 'newest' };
  // URL-derived presets from a hub deep link; clearFilters() resets to THESE, never to
  // an empty (all-verticals) state, so clearing never drops a warehouse visitor onto
  // security jobs. Populated by applyUrlFilters().
  var PRESET = { loc: '', vertical: '', role: '', shift: '' };
  var DEFAULT_LOC = '';
  var METRO_FRIENDLY = { 'DFW': 'Dallas–Fort Worth', 'Houston': 'Houston', 'Austin': 'Austin', 'San Antonio': 'San Antonio', 'El Paso': 'El Paso', 'Chicago': 'Chicago' };
  var TYPE_OPTS = [ {v:'',label:'Any Schedule'}, {v:'full-time',label:'Full-time'}, {v:'part-time',label:'Part-time'} ];
  var POSTED_OPTS = [ {v:'',label:'Any Time'}, {v:'week',label:'Posted This Week'}, {v:'3',label:'Past 3 Days'}, {v:'1',label:'Posted Today'} ];

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
    { key:'no-experience', label:'No Experience', title:/no experience|no[\s-]?exp|entry[\s-]?level|will train/ }
  ];
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
    var t = ((job.title || '') + ' ' + (job.company || '')).toLowerCase();
    var jt = (job.schedule || job.job_type || '').toLowerCase();
    var out = [];
    SHIFTS.forEach(function(s){
      if (s.title.test(t) || (s.jt && jt.indexOf(s.jt) !== -1)) out.push(s.key);
    });
    return out;
  }
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
  function postedTime(job) {
    var t = Date.parse(job.posted || job.date_pulled || '');
    return isNaN(t) ? 0 : t;
  }
  function withinDays(job, days) {
    var t = postedTime(job);
    if (!t) return false;
    return (Date.now() - t) <= (days * 24 * 60 * 60 * 1000);
  }

  /* ───────────────── MATCHERS ───────────────── */
  function postedDays(v){ return v === 'week' ? 7 : (v === '3' ? 3 : (v === '1' ? 1 : 0)); }
  function qMatch(job){ var q = filters.q.toLowerCase().trim(); if(!q) return true; return ((job.title||'')+' '+(job.company||'')).toLowerCase().indexOf(q) !== -1; }
  function locChipValue(){ var v = filters.loc||''; if(v.indexOf('metro:')===0) return v; if(v.indexOf('loc:')===0){ var rest=v.slice(4), s=rest.indexOf('::'); return 'metro:'+(s===-1?rest:rest.slice(0,s)); } return ''; }
  function locMatch(job, val){ if(!val) return true; if(val.indexOf('metro:')===0) return job._metro === val.slice(6); if(val.indexOf('loc:')===0){ var rest=val.slice(4), s=rest.indexOf('::'); if(s===-1) return job._locCity === rest; return job._metro === rest.slice(0,s) && job._locCity === rest.slice(s+2); } return true; }
  function verticalMatch(job){ return !filters.vertical || job._vertical === filters.vertical; }
  function shiftMatch(job){ return !filters.shift || (job._shifts||[]).indexOf(filters.shift) !== -1; }
  function payMatch(job){ return !filters.pay || (job.pay_min != null) || !!(job.pay||'').trim(); }
  function postedMatch(job){ if(!filters.posted) return true; var d = postedDays(filters.posted); return !d || withinDays(job, d); }
  function roleMatch(job){ return !filters.role || job._roles.indexOf(filters.role) !== -1; }

  function jobsMatching(except){
    return ALL_JOBS.filter(function(job){
      if(except !== 'q' && !qMatch(job)) return false;
      if(except !== 'loc' && !locMatch(job, filters.loc)) return false;
      if(except !== 'vertical' && !verticalMatch(job)) return false;
      if(except !== 'shift' && !shiftMatch(job)) return false;
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
    renderFeed(true);
    updateResultsBar();
    var corrected = refreshFacets();
    if (corrected && !repass) applyFilters(true);
  }

  function updateResultsBar() {
    var el = document.getElementById('resultsCount');
    var n = FILTERED.length;
    var sortLabel = filters.sort === 'pay' ? 'highest pay' : (filters.sort === 'company' ? 'company A–Z' : 'newest first');
    el.innerHTML = '<b>' + n + '</b> ' + (n === 1 ? 'open position' : 'open positions') + ' · ' + sortLabel;
    var anyFilter = filters.q || filters.pay || filters.posted ||
      (filters.loc !== PRESET.loc) || (filters.vertical !== PRESET.vertical) ||
      (filters.role !== PRESET.role) || (filters.shift !== PRESET.shift);
    document.getElementById('clearBtn').classList.toggle('show', !!anyFilter);
  }

  function esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  function cardHTML(job) {
    var tags = '';
    if (isNew(job)) tags += '<span class="jb-tag new">New</span>';
    if (job._roles[0]) tags += '<span class="jb-tag role">' + esc(roleLabel(job._roles[0])) + '</span>';
    if ((job.job_type||'').trim()) tags += '<span class="jb-tag">' + esc(job.job_type) + '</span>';
    if ((job.pay||'').trim()) tags += '<span class="jb-tag pay">$ ' + esc(job.pay) + '</span>';
    var via = (job.via||'').replace(/^via\s+/i,'').trim();
    if (via) tags += '<span class="jb-tag via">' + esc(via) + '</span>';
    var loc = esc(job.location || job.city || '');
    // Real crawlable <a href> to the employer (the crawl path to job pages). The gate
    // lives in the onclick: return true lets the href navigate on an allowed view.
    var href = esc((job.apply_link || '').trim()) || '#';
    return '<a class="jb-card" href="' + href + '" target="_blank" rel="nofollow sponsored noopener" data-i="' + job._i + '" aria-label="View and apply: ' + esc(job.title) + '" onclick="return bbjCardApply(this, event)">' +
      '<div class="jb-head">' +
        '<div class="jb-title">' + esc(job.title) + '</div>' +
        '<div class="jb-sub"><b>' + esc(job.company || 'Employer') + '</b>' + (loc ? ' · ' + loc : '') + '</div>' +
      '</div>' +
      '<div class="jb-tags">' + tags + '</div>' +
      '<span class="jb-apply">View &amp; Apply →</span>' +
    '</a>';
  }

  function renderFeed(reset) {
    var feed = document.getElementById('feed');
    if (reset) feed.innerHTML = '';
    if (!FILTERED.length) {
      feed.innerHTML = '<div class="feed-msg" style="grid-column:1/-1;">' +
        '<div class="fm-title">No matching jobs right now</div>' +
        '<div class="fm-sub">Try clearing a filter — or get alerted the moment a match posts.</div>' +
        '<a href="#" class="hero-btn gold" onclick="openAlerts();return false;" style="display:inline-flex;color:var(--navy-deep);">Get Job Alerts →</a>' +
      '</div>';
      document.getElementById('loadMoreWrap').style.display = 'none';
      return;
    }
    var next = FILTERED.slice(shown, shown + PAGE_SIZE);
    var html = next.map(cardHTML).join('');
    if (reset) feed.innerHTML = html; else feed.insertAdjacentHTML('beforeend', html);
    shown += next.length;
    document.getElementById('loadMoreWrap').style.display = (shown < FILTERED.length) ? 'block' : 'none';
    document.getElementById('loadMoreBtn').textContent = 'Load more jobs (' + (FILTERED.length - shown) + ' more)';
  }

  function loadMore() { renderFeed(false); }

  // Cards are real <a href> anchors now: click and keyboard-Enter both fire the
  // anchor's onclick (bbjCardApply), so no delegated feed listener is needed.

  /* ───────────────── DYNAMIC FACETS (auto-update from sheet) ───────────────── */
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
    html += '<option value="">All Locations ('+base.length+')</option>';
    names.forEach(function(name){
      var friendly = METRO_FRIENDLY[name] || (name + ' Area');
      html += '<optgroup label="'+esc(friendly)+'">';
      html += '<option value="metro:'+esc(name)+'">'+esc(name)+' Metro \u2014 all ('+m[name].count+')</option>';
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
  function buildLocationChips(){
    var m = metrosFrom(ALL_JOBS), names = metroOrder(m);
    var html = '<div class="chip active" data-loc="">All Locations</div>';
    names.forEach(function(name){
      var label = metroLabel(name);
      html += '<div class="chip" data-loc="metro:'+esc(name)+'">'+esc(label)+'</div>';
    });
    var el = document.getElementById('locationChips');
    if(el) el.innerHTML = html;
  }
  function pickDefaultLoc(base){
    if(DEFAULT_LOC === '') return '';
    var m = metrosFrom(base);
    if(DEFAULT_LOC.indexOf('metro:')===0 && m[DEFAULT_LOC.slice(6)]) return DEFAULT_LOC;
    var names = metroOrder(m);
    return names.length ? ('metro:'+names[0]) : '';
  }
  function rebuildSelect(id, opts, countFn, key){
    var sel = document.getElementById(id), corrected = false;
    sel.innerHTML = opts.map(function(o){
      var n = countFn(o.v);
      var dis = (o.v !== '' && n === 0) ? ' disabled' : '';
      var label = o.label + (o.v !== '' ? ' ('+n+')' : '');
      return '<option value="'+o.v+'"'+dis+'>'+esc(label)+'</option>';
    }).join('');
    if(filters[key] && countFn(filters[key]) === 0){ filters[key] = ''; corrected = true; }
    sel.value = filters[key];
    return corrected;
  }
  function refreshFacets(){
    var corrected = false;

    // LOCATION — metro chips, updated live (counts drive disable + active)
    var locBase = jobsMatching('loc');
    var wantLoc = locChipValue();
    [].forEach.call(document.querySelectorAll('#locationChips .chip'), function(chip){
      var v = chip.getAttribute('data-loc');
      var n = (v === '') ? locBase.length : locBase.filter(function(j){ return j._metro === v.slice(6); }).length;
      var dead = (n === 0 && v !== '');
      chip.classList.toggle('disabled', dead);
      chip.classList.toggle('active', v === wantLoc && !dead);
      if(dead && v === wantLoc){ filters.loc = ''; corrected = true; }
    });
    if(!document.querySelector('#locationChips .chip.active')){
      var allLoc = document.querySelector('#locationChips .chip[data-loc=""]');
      if(allLoc) allLoc.classList.add('active');
    }

    // VERTICAL chips (primary axis A)
    var vertBase = jobsMatching('vertical');
    [].forEach.call(document.querySelectorAll('#verticalChips .chip'), function(chip){
      var v = chip.getAttribute('data-vertical');
      var n = (v==='') ? vertBase.length : vertBase.filter(function(j){ return j._vertical===v; }).length;
      var dead = (n===0 && v!=='');
      chip.classList.toggle('disabled', dead);
      chip.classList.toggle('active', v===filters.vertical && !dead);
      if(dead && filters.vertical===v){ filters.vertical=''; corrected = true; }
    });
    if(!document.querySelector('#verticalChips .chip.active')){ var v0=document.querySelector('#verticalChips .chip[data-vertical=""]'); if(v0) v0.classList.add('active'); }

    // SHIFT & attribute chips (primary axis B, cross-vertical)
    var shiftBase = jobsMatching('shift');
    [].forEach.call(document.querySelectorAll('#shiftChips .chip'), function(chip){
      var s = chip.getAttribute('data-shift');
      var n = (s==='') ? shiftBase.length : shiftBase.filter(function(j){ return (j._shifts||[]).indexOf(s)!==-1; }).length;
      var dead = (n===0 && s!=='');
      chip.classList.toggle('disabled', dead);
      chip.classList.toggle('active', s===filters.shift && !dead);
      if(dead && filters.shift===s){ filters.shift=''; corrected = true; }
    });
    if(!document.querySelector('#shiftChips .chip.active')){ var sh0=document.querySelector('#shiftChips .chip[data-shift=""]'); if(sh0) sh0.classList.add('active'); }

    // DATE POSTED (sheet segments)
    var postedBase = jobsMatching('posted');
    [].forEach.call(document.querySelectorAll('#postedSeg .seg'), function(seg){
      var v = seg.getAttribute('data-posted');
      var n; if(v===''){ n = postedBase.length; } else { var d = postedDays(v); n = postedBase.filter(function(j){ return d && withinDays(j, d); }).length; }
      var dead = (n===0 && v!=='');
      seg.classList.toggle('disabled', dead);
      seg.classList.toggle('active', v===filters.posted && !dead);
      if(dead && filters.posted===v){ filters.posted=''; corrected = true; }
    });
    if(!document.querySelector('#postedSeg .seg.active')){ var p0=document.querySelector('#postedSeg .seg[data-posted=""]'); if(p0) p0.classList.add('active'); }

    // ROLE CHIPS
    var roleBase = jobsMatching('role');
    var allChip = document.querySelector('#roleChips .chip[data-role=""]');
    [].forEach.call(document.querySelectorAll('#roleChips .chip'), function(chip){
      var r = chip.getAttribute('data-role');
      var n = (r==='') ? roleBase.length : roleBase.filter(function(j){ return j._roles.indexOf(r)!==-1; }).length;
      var dead = (n === 0 && r !== '');
      chip.classList.toggle('disabled', dead);
      if(dead && filters.role === r){ filters.role=''; chip.classList.remove('active'); if(allChip) allChip.classList.add('active'); corrected = true; }
    });

    // PAY
    var payBase = jobsMatching('pay');
    var paidN = payBase.filter(function(j){ return !!(j.pay||'').trim(); }).length;
    var payT = document.getElementById('payToggle');
    payT.classList.toggle('disabled', paidN === 0);
    if(paidN === 0 && filters.pay){ filters.pay = false; corrected = true; }
    payT.classList.toggle('on', filters.pay);

    // SORT (sheet segments — never disabled)
    [].forEach.call(document.querySelectorAll('#sortSeg .seg'), function(seg){
      seg.classList.toggle('active', seg.getAttribute('data-sort')===filters.sort);
    });

    // MORE-FILTERS badge — active secondary filters only
    var badgeN = (filters.posted?1:0) + (filters.pay?1:0) + (filters.sort!=='newest'?1:0);
    var mb = document.getElementById('mfBadge');
    if(mb){ mb.textContent = badgeN; mb.style.display = badgeN>0 ? 'inline-block' : 'none'; }

    return corrected;
  }

  /* ───────────────── FILTER HANDLERS ───────────────── */
  document.getElementById('searchInput').addEventListener('input', function(e){
    filters.q = e.target.value; applyFilters();
  });
  document.getElementById('locationChips').addEventListener('click', function(e){
    var chip = e.target.closest('.chip'); if (!chip || chip.classList.contains('disabled')) return;
    filters.loc = chip.getAttribute('data-loc');
    [].forEach.call(this.querySelectorAll('.chip'), function(c){ c.classList.remove('active'); });
    chip.classList.add('active');
    applyFilters();
  });
  function segHandler(containerId, attr, key){
    document.getElementById(containerId).addEventListener('click', function(e){
      var seg = e.target.closest('.seg'); if (!seg || seg.classList.contains('disabled')) return;
      filters[key] = seg.getAttribute(attr);
      [].forEach.call(this.querySelectorAll('.seg'), function(s){ s.classList.remove('active'); });
      seg.classList.add('active');
      applyFilters();
    });
  }
  segHandler('postedSeg', 'data-posted', 'posted');
  segHandler('sortSeg', 'data-sort', 'sort');
  function openFilterSheet(){ document.getElementById('filterSheet').classList.add('open'); document.body.style.overflow='hidden'; }
  function closeFilterSheet(){ document.getElementById('filterSheet').classList.remove('open'); document.body.style.overflow=''; }
  function togglePay() {
    filters.pay = !filters.pay;
    document.getElementById('payToggle').classList.toggle('on', filters.pay);
    applyFilters();
  }
  // Role chips are rebuilt from TAXONOMY whenever the vertical changes, so the role
  // set always matches the chosen vertical (armed for security, forklift for warehouse).
  function buildRoleChips(vertical){
    var roles = rolesForVertical(vertical);
    var html = '<div class="chip'+(filters.role===''?' active':'')+'" data-role="">All Roles</div>';
    roles.forEach(function(r){
      html += '<div class="chip'+(filters.role===r.key?' active':'')+'" data-role="'+r.key+'">'+esc(r.label)+'</div>';
    });
    var el = document.getElementById('roleChips');
    if(el) el.innerHTML = html;
  }
  document.getElementById('verticalChips').addEventListener('click', function(e){
    var chip = e.target.closest('.chip'); if (!chip || chip.classList.contains('disabled')) return;
    filters.vertical = chip.getAttribute('data-vertical');
    [].forEach.call(this.querySelectorAll('.chip'), function(c){ c.classList.remove('active'); });
    chip.classList.add('active');
    // a role that isn't part of the new vertical no longer applies — drop it
    if(!rolesForVertical(filters.vertical).some(function(r){ return r.key===filters.role; })) filters.role = '';
    buildRoleChips(filters.vertical);
    applyFilters();
  });
  document.getElementById('roleChips').addEventListener('click', function(e){
    var chip = e.target.closest('.chip'); if (!chip || chip.classList.contains('disabled')) return;
    filters.role = chip.getAttribute('data-role');
    [].forEach.call(this.querySelectorAll('.chip'), function(c){ c.classList.remove('active'); });
    chip.classList.add('active');
    applyFilters();
  });
  document.getElementById('shiftChips').addEventListener('click', function(e){
    var chip = e.target.closest('.chip'); if (!chip || chip.classList.contains('disabled')) return;
    filters.shift = chip.getAttribute('data-shift');
    [].forEach.call(this.querySelectorAll('.chip'), function(c){ c.classList.remove('active'); });
    chip.classList.add('active');
    applyFilters();
  });
  function clearFilters() {
    // Reset to the hub PRESET (or the neutral all-verticals state if no preset), NOT to
    // an empty state — so clearing on a warehouse hub never reveals security jobs.
    filters = { q:'', loc:(PRESET.loc||DEFAULT_LOC), vertical:(PRESET.vertical||''),
                role:(PRESET.role||''), shift:(PRESET.shift||''), pay:false, posted:'', sort:'newest' };
    document.getElementById('searchInput').value = '';
    document.getElementById('payToggle').classList.remove('on');
    buildRoleChips(filters.vertical);
    [].forEach.call(document.querySelectorAll('#verticalChips .chip'), function(c){ c.classList.toggle('active', c.getAttribute('data-vertical')===filters.vertical); });
    [].forEach.call(document.querySelectorAll('#shiftChips .chip'), function(c){ c.classList.toggle('active', c.getAttribute('data-shift')===filters.shift); });
    [].forEach.call(document.querySelectorAll('#locationChips .chip'), function(c){ c.classList.toggle('active', c.getAttribute('data-loc')===(filters.loc||'')); });
    applyFilters();
    window.scrollTo({ top: document.getElementById('board').offsetTop - 60, behavior: 'smooth' });
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
  // Card anchor onclick. Return true to let the href open the employer (crawlable) on an
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
  function closeGate() { document.getElementById('gateModal').classList.remove('open'); document.body.style.overflow=''; }
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
    document.getElementById('alertsModal').classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  function closeAlerts() { document.getElementById('alertsModal').classList.remove('open'); document.body.style.overflow=''; }
  function submitAlerts() {}

  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') { closeGate(); closeAlerts(); } });

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
  function renderContextBar(){
    var el = document.getElementById('contextBar'); if(!el) return;
    var parts = [];
    if(PRESET.vertical) parts.push(TAXONOMY[PRESET.vertical] ? TAXONOMY[PRESET.vertical].label : PRESET.vertical);
    if(PRESET.loc){ var lv=PRESET.loc; var name = lv.indexOf('metro:')===0 ? lv.slice(6) : (lv.indexOf('loc:')===0 ? lv.slice(4).split('::').pop() : lv); parts.push(metroLabel(name)); }
    if(PRESET.role) parts.push(roleLabel(PRESET.role));
    if(PRESET.shift) parts.push(roleLabel(PRESET.shift));
    if(!parts.length){ el.style.display='none'; return; }
    el.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:10px 16px;background:#fff7e0;border-bottom:1px solid #f0d98a;font-size:0.85rem;';
    el.innerHTML = '<span style="font-weight:700;color:#7a5b00;">Showing</span>' +
      parts.map(function(x){ return '<span style="background:#001D3D;color:#FFC300;font-weight:700;border-radius:999px;padding:3px 10px;">'+esc(x)+'</span>'; }).join('') +
      '<a href="/job-board" style="margin-left:auto;color:#001D3D;font-weight:700;text-decoration:underline;">View all jobs →</a>';
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
      var pt=document.getElementById('payToggle'); if(pt) pt.classList.toggle('on', filters.pay);
      [].forEach.call(document.querySelectorAll('#verticalChips .chip'), function(c){ c.classList.toggle('active', c.getAttribute('data-vertical')===filters.vertical); });
      buildRoleChips(filters.vertical);
      [].forEach.call(document.querySelectorAll('#shiftChips .chip'), function(c){ c.classList.toggle('active', c.getAttribute('data-shift')===filters.shift); });
      renderContextBar();
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
      base._vertical = (base.vertical || 'security').toLowerCase();   // board.json vertical; legacy rows default to security
      // roles (vertical-scoped): title-derived + the stored role slug of every dup this job merged
      base._roles = deriveRoles(base);
      g.forEach(function(x){ var r = roleFromString(x.role || x.role_category, base._vertical); if(r && base._roles.indexOf(r) === -1) base._roles.unshift(r); });
      base._shifts = deriveShifts(base);                              // cross-vertical shift+attribute axis
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
    buildLocationChips();             // metro chips from live feed data
    buildRoleChips(filters.vertical); // role chips from TAXONOMY (all roles until a vertical is picked)
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
      schedule: j.schedule || ''
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
        document.getElementById('feed').innerHTML = '<div class="feed-msg" style="grid-column:1/-1;"><div class="fm-title">Couldn\'t load openings</div><div class="fm-sub">Please refresh in a moment, or get job alerts and we\'ll come to you.</div><a href="#" class="hero-btn gold" onclick="openAlerts();return false;" style="display:inline-flex;color:var(--navy-deep);">Get Job Alerts →</a></div>';
        document.getElementById('resultsCount').textContent = 'Listings temporarily unavailable';
      });
  }
  loadFeed();
