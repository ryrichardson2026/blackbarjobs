(function() {
  // BBJ Register Overlay — mirrors register.html as floating overlay
  // Supabase: Step 1 signUp with temp pass, Step 2 updateUser with real pass

  // ── Attribution: capture once at landing, attach to every webhook ──
  window.bbjAttr = window.bbjAttr || (function () {
    function qp(n){var m=new RegExp('[?&]'+n+'=([^&#]*)').exec(location.href);return m?decodeURIComponent(m[1].replace(/\+/g,' ')):'';}
    var KEY='bbj_attr', s=null;
    try { s = JSON.parse(sessionStorage.getItem(KEY)||'null'); } catch(e){ s=null; }
    if (!s) {
      var gclid=qp('gclid'), gbraid=qp('gbraid'), wbraid=qp('wbraid');
      s = { landing_url: location.href, landing_path: location.pathname, referrer: document.referrer || '',
            gclid: gclid, gbraid: gbraid, wbraid: wbraid,
            utm_source: qp('utm_source'), utm_medium: qp('utm_medium'), utm_campaign: qp('utm_campaign'),
            utm_term: qp('utm_term'), utm_content: qp('utm_content') };
      var ch='direct';
      if (gclid||gbraid||wbraid) ch='google_ads';
      else if (s.utm_medium) ch=s.utm_medium;
      else if (document.referrer) { var h=''; try{h=new URL(document.referrer).hostname;}catch(e){}
        if(/google\.|bing\.|yahoo\.|duckduckgo\./.test(h)) ch='organic_search';
        else if(h && h.indexOf(location.hostname)===-1) ch='referral'; }
      s.channel=ch;
      try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch(e){}
    }
    return function (cta) {
      return Object.assign({}, s, { page_url: location.href, page_path: location.pathname, page_title: document.title, cta: cta||'' });
    };
  })();

  // ── Geo-aware license copy: switches the license question set by detected state ──
  // Page market from the URL path (authority for region prefill).
  // First path segment -> served metro + its state, or null (root/national -> ask).
  // NOT sourced from BBJ_FEED_KEY: the root homepage is Dallas-keyed but must stay neutral.
  window.bbjPageMarket = window.bbjPageMarket || function(){
    var seg = (location.pathname || '').toLowerCase().replace(/^\/+|\/+$/g, '').split('/')[0];
    var METRO = { 'dallas':{metro:'Dallas',state:'TX'}, 'fort-worth':{metro:'Fort Worth',state:'TX'},
      'houston':{metro:'Houston',state:'TX'}, 'san-antonio':{metro:'San Antonio',state:'TX'},
      'austin':{metro:'Austin',state:'TX'}, 'chicago':{metro:'Chicago',state:'IL'} };
    var STATE = { 'texas':{metro:'Dallas',state:'TX'}, 'illinois':{metro:'Chicago',state:'IL'} };
    return METRO[seg] || STATE[seg] || null;
  };
  // Split a region dropdown value "Metro|ST" into its parts.
  window.bbjParseRegion = window.bbjParseRegion || function(v){
    v = v || ''; var i = v.lastIndexOf('|');
    return i === -1 ? { metro: v, state: '' } : { metro: v.slice(0, i), state: v.slice(i + 1) };
  };
  // Dead fallback: the old free-text regex. License copy no longer comes from typed
  // text, so this is retained for reference only and is never the driver.
  window.bbjLicState = window.bbjLicState || function(v){
    v = (v || '').toLowerCase();
    if (/chicago|illinois|\bil\b|naperville|aurora|joliet|schaumburg|evanston|cicero|rockford|peoria|springfield/.test(v)) return 'IL';
    if (/dallas|fort worth|ft worth|dfw|houston|san antonio|austin|texas|\btx\b|el paso|arlington|plano|irving|garland/.test(v)) return 'TX';
    return '';
  };
  window.BBJ_LIC = window.BBJ_LIC || {
    TX: { label: 'Texas Security License', q: 'Do you hold a Texas DPS security license?',
      opts: [['','Select level'],['level2','Level 2 \u2014 Non-Commissioned (Unarmed)'],['level3','Level 3 \u2014 Commissioned (Armed)'],['both','Both Level 2 and Level 3']] },
    IL: { label: 'Illinois Security License', q: 'Do you have an Illinois PERC card (security license)?',
      opts: [['','Select type'],['perc','PERC card (unarmed)'],['perc_fcc','PERC plus Firearm Control Card (armed)']] },
    '': { label: 'Security Officer License', q: 'Do you hold a security officer license in your state?',
      opts: [['','Select one'],['unarmed','Unarmed license'],['armed','Armed license'],['both','Both']] }
  };
  // Wire the region dropdown to the license question: parse the state from the
  // selected value, set copy from BBJ_LIC[state], and show/hide the license
  // section based on whether a region has been chosen.
  window.bbjWireLicense = window.bbjWireLicense || function(regionEl, labelEl, qEl, selEl, sectionEl){
    if (!regionEl || !selEl) return;
    var cur = '__init__';
    function apply(){
      if (sectionEl) sectionEl.style.display = regionEl.value ? '' : 'none';
      var st = window.bbjParseRegion(regionEl.value).state;
      if (st === cur) return; cur = st;
      var c = window.BBJ_LIC[st] || window.BBJ_LIC[''];
      if (labelEl) labelEl.textContent = c.label;
      if (qEl) qEl.textContent = c.q;
      var prev = selEl.value;
      selEl.innerHTML = c.opts.map(function(o){ return '<option value="' + o[0] + '">' + o[1] + '</option>'; }).join('');
      for (var i = 0; i < selEl.options.length; i++){ if (selEl.options[i].value === prev){ selEl.value = prev; break; } }
    }
    regionEl.addEventListener('change', apply);
    apply();
  };
  // Prefill a region dropdown from the page's market. Returns true if a market
  // was matched (dropdown set), false if the page must ask (root/national).
  window.bbjPrefillRegion = window.bbjPrefillRegion || function(regionEl){
    if (!regionEl) return false;
    var m = window.bbjPageMarket();
    if (!m) return false;
    var want = m.metro + '|' + m.state;
    for (var i = 0; i < regionEl.options.length; i++){
      if (regionEl.options[i].value === want){ regionEl.value = want; return true; }
    }
    return false;
  };

  // ── CSS ──────────────────────────────────────────────────────
  var css = [
    '#bbjRegOvr{display:none;position:fixed;inset:0;z-index:5000;background:rgba(0,8,20,0.75);align-items:flex-end;justify-content:center;}',
    '#bbjRegOvr.open{display:flex;}',
    '@media(min-width:640px){#bbjRegOvr{align-items:center;}}',
    '#bbjRegCard{background:#fff;width:100%;max-width:480px;border-radius:22px 22px 0 0;padding:32px 28px 40px;position:relative;max-height:92dvh;overflow-y:auto;transform:translateY(100%);transition:transform 0.28s ease,opacity 0.28s ease;opacity:0;}',
    '@media(min-width:640px){#bbjRegCard{border-radius:16px;transform:translateY(20px) scale(0.97);}}',
    '#bbjRegOvr.open #bbjRegCard{transform:translateY(0);opacity:1;}',
    '#bbjRegX{position:absolute;top:14px;right:14px;width:32px;height:32px;border-radius:50%;background:#f4f5f7;border:none;cursor:pointer;font-size:1.1rem;color:#5a6474;line-height:1;display:flex;align-items:center;justify-content:center;}',
    '#bbjRegX:hover{background:#e2e5ea;}',
    '#bbjRegCard .step-bar{display:flex;gap:6px;margin-bottom:24px;}',
    '#bbjRegCard .step-dot{flex:1;height:3px;border-radius:2px;background:#e2e5ea;transition:background 0.2s;}',
    '#bbjRegCard .step-dot.active{background:#FFC300;}',
    '#bbjRegCard .step-dot.done{background:#000814;}',
    '#bbjRegCard .auth-title{font-family:"Barlow Condensed",sans-serif;font-weight:800;font-size:1.9rem;color:#000814;line-height:1.1;margin-bottom:4px;}',
    '#bbjRegCard .auth-sub{font-size:0.88rem;color:#5a6474;margin-bottom:20px;}',
    '#bbjRegCard .field-label{font-size:0.75rem;font-weight:600;color:#5a6474;letter-spacing:0.04em;text-transform:uppercase;margin-bottom:4px;display:block;}',
    '#bbjRegCard input[type=text],#bbjRegCard input[type=email],#bbjRegCard input[type=tel],#bbjRegCard input[type=password],#bbjRegCard select{width:100%;padding:10px 13px;border:1.5px solid #e2e5ea;border-radius:8px;font-family:"Barlow",sans-serif;font-size:0.92rem;color:#1a1a1a;background:#fff;outline:none;transition:border-color 0.15s;margin-bottom:10px;display:block;-webkit-appearance:none;}',
    '#bbjRegCard input:focus,#bbjRegCard select:focus{border-color:#001D3D;}',
    '#bbjRegCard input::placeholder{color:#a0aab4;}',
    '#bbjRegCard .chip-grid{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;}',
    '#bbjRegCard .chip{font-family:"Barlow Condensed",sans-serif;font-size:0.85rem;font-weight:700;padding:7px 14px;border-radius:20px;border:1.5px solid #e2e5ea;background:#fff;color:#5a6474;cursor:pointer;transition:all 0.12s;user-select:none;}',
    '#bbjRegCard .chip.selected{background:#000814;border-color:#000814;color:#FFC300;}',
    '#bbjRegCard .toggle-row{display:flex;gap:8px;margin-bottom:10px;}',
    '#bbjRegCard .toggle-btn{flex:1;padding:10px;font-family:"Barlow Condensed",sans-serif;font-size:0.9rem;font-weight:700;border:1.5px solid #e2e5ea;border-radius:8px;background:#fff;color:#5a6474;cursor:pointer;transition:all 0.12s;text-align:center;}',
    '#bbjRegCard .toggle-btn.selected{background:#000814;border-color:#000814;color:#FFC300;}',
    '#bbjRegCard .reveal-block{display:none;margin-bottom:10px;}',
    '#bbjRegCard .reveal-block.visible{display:block;}',
    '#bbjRegCard .reveal-block-pad{display:none;background:#f4f5f7;border-radius:10px;padding:14px 16px;margin-bottom:10px;border:1px solid #e2e5ea;}',
    '#bbjRegCard .reveal-block-pad.visible{display:block;}',
    '#bbjRegCard .reveal-block-pad p{font-size:0.85rem;color:#5a6474;margin-bottom:10px;line-height:1.5;}',
    '#bbjRegCard .help-opts{display:flex;flex-direction:column;gap:10px;margin-top:6px;}',
    '#bbjRegCard .help-opt{display:flex;align-items:flex-start;gap:10px;font-size:0.88rem;color:#1a1a1a;cursor:pointer;line-height:1.4;}',
    '#bbjRegCard .help-opt input[type=checkbox]{width:16px;height:16px;margin:0;padding:0;accent-color:#000814;cursor:pointer;flex-shrink:0;margin-top:2px;}',
    '#bbjRegCard .submit-btn{width:100%;padding:14px;background:#FFC300;color:#000814;font-family:"Barlow Condensed",sans-serif;font-size:1.1rem;font-weight:800;letter-spacing:0.06em;text-transform:uppercase;border:none;border-radius:10px;cursor:pointer;transition:background 0.15s;margin-top:8px;}',
    '#bbjRegCard .submit-btn:hover{background:#FFD60A;}',
    '#bbjRegCard .submit-btn:disabled{opacity:0.4;cursor:not-allowed;}',
    '#bbjRegCard .err-msg{display:none;color:#e53935;font-size:0.82rem;margin-bottom:12px;padding:10px 12px;background:#fff5f5;border-radius:6px;border:1px solid #fcc;}',
    '#bbjRegCard .success-wrap{text-align:center;padding:10px 0;}',
    '#bbjRegCard .success-title{font-family:"Barlow Condensed",sans-serif;font-weight:800;font-size:1.8rem;color:#000814;margin-bottom:6px;}',
    '#bbjRegCard .success-sub{font-size:0.88rem;color:#5a6474;margin-bottom:24px;line-height:1.5;}',
    '#bbjRegCard .tcpa{font-size:0.7rem;color:#a0aab4;margin-top:10px;line-height:1.5;}',
    '#bbjRegCard .tcpa a{color:#a0aab4;}',
    '#bbjRegCard .signin-link{text-align:center;font-size:0.86rem;color:#5a6474;margin-top:16px;}',
    '#bbjRegCard .signin-link a{color:#001D3D;font-weight:600;text-decoration:none;}',
    '#bbjRegCard hr{border:none;border-top:1px solid #e2e5ea;margin:16px 0;}',
    '#bbjRegCard .section-label{font-family:"Barlow Condensed",sans-serif;font-size:0.78rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#000814;margin:16px 0 10px;padding-bottom:6px;border-bottom:2px solid #FFC300;display:block;}',
    '#bbjRegCard select{background-image:url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'12\' height=\'8\' viewBox=\'0 0 12 8\'%3E%3Cpath d=\'M1 1l5 5 5-5\' stroke=\'%235a6474\' stroke-width=\'1.5\' fill=\'none\' stroke-linecap=\'round\'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 13px center;padding-right:32px;}',
    '#bbjRegCard .field-row{display:flex;gap:10px;margin-bottom:10px;}',
    '#bbjRegCard .field-row>div{flex:1;}',
    '#bbjLoader{display:none;text-align:center;padding:60px 20px;}',
    '#bbjLoaderSpinner{width:44px;height:44px;border:3px solid #e2e5ea;border-top-color:#FFC300;border-radius:50%;animation:bbjSpin 0.8s linear infinite;margin:0 auto 16px;}',
    '#bbjLoaderTxt{font-family:"Barlow Condensed",sans-serif;font-size:1.2rem;font-weight:800;color:#000814;}',
    '@keyframes bbjSpin{to{transform:rotate(360deg);}}'
  ].join('');

  // ── HTML ─────────────────────────────────────────────────────
  var div = document.createElement('div');
  div.innerHTML = '<style>' + css + '</style>';
  document.head.appendChild(div.firstChild);

  var card = document.createElement('div');
  card.id = 'bbjRegOvr';
  card.onclick = function(e){ if(e.target===this) bbjRegClose(); };
  card.innerHTML = [
    '<div id="bbjRegCard">',
    '<button id="bbjRegX" onclick="bbjRegClose()">&#x2715;</button>',
    '<div class="step-bar">',
      '<div class="step-dot active" id="bbjDot1"></div>',
      '<div class="step-dot" id="bbjDot2"></div>',
    '</div>',
    '<div id="bbjStep1">',
      '<h2 class="auth-title">Get Job Alerts</h2>',
      '<p class="auth-sub">Free. No resume required. Get notified the moment new openings post.</p>',
      '<div id="bbjErr1" class="err-msg"></div>',
      '<label class="field-label">First Name</label>',
      '<input id="bbjFirstName" type="text" placeholder="First name" autocomplete="given-name">',
      '<label class="field-label">Email</label>',
      '<input id="bbjEmail" type="email" placeholder="you@email.com" inputmode="email" autocomplete="email">',
      '<label class="field-label">Region</label>',
      '<select id="bbjCityRegion">',
        '<option value="">What\'s your region?</option>',
        '<option value="Dallas|TX">Dallas, TX</option>',
        '<option value="Fort Worth|TX">Fort Worth, TX</option>',
        '<option value="Houston|TX">Houston, TX</option>',
        '<option value="San Antonio|TX">San Antonio, TX</option>',
        '<option value="Austin|TX">Austin, TX</option>',
        '<option value="Chicago|IL">Chicago, IL</option>',
        '<option value="other|">Other / not listed</option>',
      '</select>',
      '<label style="font-size:0.88rem;font-weight:700;color:#1a1a1a;margin-bottom:4px;display:block;">What type of security jobs?</label>',
      '<p style="font-size:0.78rem;color:#5a6474;margin-bottom:10px;">Select all that apply.</p>',
      '<div class="chip-grid">',
        '<div class="chip" data-role="all" id="bbjChipAll">All Types</div>',
        '<div class="chip" data-role="unarmed">Unarmed</div>',
        '<div class="chip" data-role="armed">Armed</div>',
        '<div class="chip" data-role="overnight">Overnight</div>',
        '<div class="chip" data-role="event">Event</div>',
      '</div>',
      '<label style="font-size:0.88rem;font-weight:700;color:#1a1a1a;margin-bottom:6px;display:block;">Receive SMS alerts for new jobs?</label>',
      '<div class="toggle-row" style="margin-top:6px;">',
        '<div class="toggle-btn" id="bbjSmsYes">Yes</div>',
        '<div class="toggle-btn" id="bbjSmsNo">No thanks</div>',
      '</div>',
      '<div class="reveal-block" id="bbjPhoneBlock">',
        '<label class="field-label">Mobile Number</label>',
        '<input id="bbjPhone" type="tel" placeholder="(214) 000-0000" inputmode="tel" autocomplete="tel">',
      '</div>',
      '<button class="submit-btn" id="bbjStep1Btn">Get Job Alerts</button>',
      '<p class="tcpa">By submitting you agree to receive job alerts by email and SMS if opted in. <a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank">Privacy Policy</a>.</p>',
      '<p class="signin-link">Already have an account? <a href="/login.html">Sign in</a></p>',
    '</div>',
    '<div id="bbjLoader"><div id="bbjLoaderSpinner"></div><div id="bbjLoaderTxt">One moment...</div></div>',
    '<div id="bbjSuccess" style="display:none;">',
      '<div class="success-wrap">',
        '<div class="success-title">You\'re on the list!</div>',
        '<p class="success-sub">We\'ll notify you the moment new security jobs post in your area.</p>',
        '<button class="submit-btn" id="bbjShowStep2Btn" style="margin-bottom:14px;">Browse All Jobs &#x2192;</button>',
        '<a class="signin-link" href="/job-board" style="display:block;margin-top:8px;">Skip &#x2014; Browse jobs now</a>',
      '</div>',
    '</div>',
    '<div id="bbjStep2" style="display:none;">',
      '<h2 class="auth-title" style="font-size:1.6rem;">Complete Your Profile</h2>',
      '<p class="auth-sub">Register for BlackBarJobs &#x2014; get access to more jobs. Free to sign up. No resume required.</p>',
      '<div id="bbjErr2" class="err-msg"></div>',
      '<div class="field-row">',
        '<div><label class="field-label">City</label><input id="bbjCity" type="text" placeholder="Dallas" autocomplete="address-level2"></div>',
        '<div><label class="field-label">State</label><input id="bbjState" type="text" placeholder="TX" autocomplete="address-level1" maxlength="2"></div>',
      '</div>',
      '<div id="bbjLicSection">',
      '<span class="section-label" id="bbjLicLabel">Texas Security License</span>',
      '<p style="font-size:0.82rem;color:#5a6474;margin-bottom:10px;" id="bbjLicQ">Do you hold a Texas DPS security license?</p>',
      '<div class="toggle-row">',
        '<div class="toggle-btn" id="bbjLicYes">Yes, I\'m licensed</div>',
        '<div class="toggle-btn" id="bbjLicNo">Not yet</div>',
      '</div>',
      '<div class="reveal-block" id="bbjLicLevelBlock">',
        '<label class="field-label">License Level</label>',
        '<select id="bbjLicLevel"><option value="">Select level</option><option value="level2">Level 2 &#x2014; Non-Commissioned (Unarmed)</option><option value="level3">Level 3 &#x2014; Commissioned (Armed)</option><option value="both">Both Level 2 and Level 3</option></select>',
      '</div>',
      '<div class="reveal-block" id="bbjLicHelpBlock">',
        '<label style="font-size:0.88rem;font-weight:700;color:#1a1a1a;margin-bottom:6px;display:block;">Do you want help getting licensed in your state?</label>',
        '<div class="toggle-row">',
          '<div class="toggle-btn" id="bbjHelpY">Yes</div>',
          '<div class="toggle-btn" id="bbjHelpN">No</div>',
        '</div>',
      '</div>',
      '</div>',
      '<hr>',
      '<label class="field-label">Create a Password</label>',
      '<input id="bbjPassword" type="password" placeholder="Min. 8 characters" autocomplete="new-password">',
      '<button class="submit-btn" id="bbjStep2Btn">Create Account &amp; View Jobs</button>',
      '<p class="tcpa">Free forever. <a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank">Privacy Policy</a>.</p>',
    '</div>',
    '</div>'
  ].join('');
  document.body.appendChild(card);


  // ── STATE ────────────────────────────────────────────────────
  var _sms = '', _lic = '', _step1Data = {};

  // ── HELPERS ──────────────────────────────────────────────────
  function _sb() {
    try {
      if (window.supabase && typeof SUPABASE_URL !== 'undefined') {
        return window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
      }
    } catch(e) {}
    return null;
  }

  function _showLoader(txt) {
    document.getElementById('bbjStep1').style.display    = 'none';
    document.getElementById('bbjSuccess').style.display  = 'none';
    document.getElementById('bbjStep2').style.display    = 'none';
    document.getElementById('bbjLoaderTxt').textContent  = txt || 'One moment...';
    document.getElementById('bbjLoader').style.display   = 'block';
  }

  function _hideLoader() {
    document.getElementById('bbjLoader').style.display = 'none';
  }

  function _setDots(n) {
    document.getElementById('bbjDot1').className = 'step-dot ' + (n > 1 ? 'done' : 'active');
    document.getElementById('bbjDot2').className = 'step-dot ' + (n >= 2 ? 'active' : '');
  }

  // ── PUBLIC API ───────────────────────────────────────────────
  // Post-registration: feed pages already show aligned jobs, so stay in place
  // (bbj_registered cookie unlocks applies). Feedless hub pages still get the board.
  // After account creation, render a success splash (kept open) with a single
  // Browse Jobs button that goes to the board filtered to this page.
  function bbjShowBrowseSplash(spinnerId, txtId){
    var sp = document.getElementById(spinnerId); if (sp) sp.style.display = 'none';
    if (typeof bbjMorphCtas === 'function') bbjMorphCtas();  // flip lander CTAs too, in case they dismiss this
    var url = bbjBrowseUrl();
    var el = document.getElementById(txtId);
    if (el) el.innerHTML =
      "You're in."
      + "<span style='display:block;margin-top:8px;font-weight:400;font-size:0.9rem;color:#5a6474;'>Your account is ready. Browse jobs matched to this search.</span>"
      + "<a href='" + url + "' style='display:block;box-sizing:border-box;width:100%;margin-top:20px;padding:15px;background:#FFC300;color:#000814;font-family:\"Barlow Condensed\",sans-serif;font-size:1.1rem;font-weight:800;letter-spacing:0.06em;text-transform:uppercase;text-align:center;text-decoration:none;border-radius:10px;'>Browse Jobs \u2192</a>";
  }

  // Once registered, alerts are already active from signup, so register CTAs
  // become browse actions: scroll to the on-page feed, or go to the board if none.
  // Build a board URL filtered to this page's context, derived from the feed key
  // e.g. "austin/jobs/armed-security-austin" -> /job-board?role=armed-security-austin&city=austin
  function bbjBrowseUrl(){
    var key = window.BBJ_FEED_KEY || '';
    if (!key) return '/job-board';
    var parts = key.split('/');
    var metro = (parts[0] || '').replace(/-/g, ' ');
    var slug  = parts[parts.length - 1] || '';
    var qs = [];
    if (slug && slug !== 'index') qs.push('role=' + encodeURIComponent(slug));
    if (metro) qs.push('city=' + encodeURIComponent(metro));
    return '/job-board' + (qs.length ? '?' + qs.join('&') : '');
  }
  // Once registered, alerts are already active from signup, so register CTAs
  // become a Browse Jobs action that opens the board filtered to this page.
  function bbjMorphCtas(){
    if (document.cookie.indexOf('bbj_registered=1') === -1) return;
    var ctas = document.querySelectorAll('[onclick*="bbjAlertOpen"],[onclick*="bbjAccOpen"]');
    [].forEach.call(ctas, function(el){
      if (/alert/i.test(el.textContent)) el.textContent = 'Browse Jobs \u2192';
      el.setAttribute('href', bbjBrowseUrl());
      el.onclick = function(e){
        if (e && e.preventDefault) e.preventDefault();
        window.location.href = bbjBrowseUrl();
        return false;
      };
    });
  }
  window.bbjBrowseUrl = bbjBrowseUrl;
  window.bbjShowBrowseSplash = bbjShowBrowseSplash;
  document.addEventListener('DOMContentLoaded', bbjMorphCtas);

  window.bbjRegOpen = function() {
    document.getElementById('bbjStep1').style.display   = 'block';
    document.getElementById('bbjLoader').style.display  = 'none';
    document.getElementById('bbjSuccess').style.display = 'none';
    document.getElementById('bbjStep2').style.display   = 'none';
    document.getElementById('bbjErr1').style.display    = 'none';
    _setDots(1);
    document.getElementById('bbjRegOvr').classList.add('open');
    document.body.style.overflow = 'hidden';
    setTimeout(function(){ document.getElementById('bbjFirstName').focus(); }, 350);
  };
  window.bbjAlertOpen = window.bbjRegOpen;
  window.bbjAccOpen   = window.bbjRegOpen;

  window.bbjRegClose = function() {
    document.getElementById('bbjRegOvr').classList.remove('open');
    document.body.style.overflow = '';
  };

  window.bbjSetSms = function(val) {
    _sms = val;
    document.getElementById('bbjSmsYes').classList.toggle('selected', val === 'yes');
    document.getElementById('bbjSmsNo').classList.toggle('selected', val === 'no');
    document.getElementById('bbjPhoneBlock').classList.toggle('visible', val === 'yes');
    if (val !== 'yes') document.getElementById('bbjPhone').value = '';
  };

  window.bbjSetLic = function(val) {
    _lic = val;
    document.getElementById('bbjLicYes').classList.toggle('selected', val === 'yes');
    document.getElementById('bbjLicNo').classList.toggle('selected', val === 'no');
    document.getElementById('bbjLicLevelBlock').classList.toggle('visible', val === 'yes');
    document.getElementById('bbjLicHelpBlock').classList.toggle('visible', val === 'no');
  };

  window.bbjSetHelp = function(val) {
    document.getElementById('bbjHelpY').classList.toggle('selected', val==='yes');
    document.getElementById('bbjHelpN').classList.toggle('selected', val==='no');
  };

  window.bbjShowStep2 = function() {
    document.getElementById('bbjSuccess').style.display = 'none';
    document.getElementById('bbjStep2').style.display   = 'block';
    _setDots(2);
  };

  // ── INIT LISTENERS ───────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function() {

    // Wire SMS toggles
    document.getElementById('bbjSmsYes').addEventListener('click', function(){ bbjSetSms('yes'); });
    document.getElementById('bbjSmsNo').addEventListener('click', function(){ bbjSetSms('no'); });
    // Wire License toggles
    document.getElementById('bbjLicYes').addEventListener('click', function(){ bbjSetLic('yes'); });
    document.getElementById('bbjLicNo').addEventListener('click', function(){ bbjSetLic('no'); });
    // Wire Help toggles
    document.getElementById('bbjHelpY').addEventListener('click', function(){ bbjSetHelp('yes'); });
    document.getElementById('bbjHelpN').addEventListener('click', function(){ bbjSetHelp('no'); });
    // Wire success Browse button
    document.getElementById('bbjShowStep2Btn').addEventListener('click', function(){ bbjShowStep2(); });
    // Wire X button
    document.getElementById('bbjRegX').addEventListener('click', function(){ bbjRegClose(); });

    // Geo-aware license copy (driven by the Step 1 region dropdown)
    var bbjRegionSel = document.getElementById('bbjCityRegion');
    window.bbjPrefillRegion(bbjRegionSel);
    window.bbjWireLicense(
      bbjRegionSel,
      document.getElementById('bbjLicLabel'),
      document.getElementById('bbjLicQ'),
      document.getElementById('bbjLicLevel'),
      document.getElementById('bbjLicSection')
    );

    // Chips
    var chipAll = document.getElementById('bbjChipAll');
    if (chipAll) {
      chipAll.addEventListener('click', function() {
        var chips = document.querySelectorAll('#bbjRegCard .chip');
        var allOn = this.classList.contains('selected');
        chips.forEach(function(c){ c.classList.remove('selected'); });
        if (!allOn) this.classList.add('selected');
      });
    }
    document.querySelectorAll('#bbjRegCard .chip:not(#bbjChipAll)').forEach(function(c) {
      c.addEventListener('click', function() {
        this.classList.toggle('selected');
        var anyOn = Array.from(document.querySelectorAll('#bbjRegCard .chip:not(#bbjChipAll)')).some(function(x){ return x.classList.contains('selected'); });
        document.getElementById('bbjChipAll').classList.toggle('selected', !anyOn);
      });
    });

    // ── STEP 1 SUBMIT ─────────────────────────────────────────
    var btn1 = document.getElementById('bbjStep1Btn');
    if (btn1) btn1.addEventListener('click', async function() {
      var name  = document.getElementById('bbjFirstName').value.trim();
      var email = document.getElementById('bbjEmail').value.trim();
      var phoneEl = document.getElementById('bbjPhone'); var phone = phoneEl ? phoneEl.value.trim() : '';
      var reg = window.bbjParseRegion(document.getElementById('bbjCityRegion').value);
      var region_metro = reg.metro, license_state = reg.state, cityRegion = region_metro;
      var errEl = document.getElementById('bbjErr1');
      errEl.style.display = 'none';

      if (!name || !email) { errEl.textContent = 'Please enter your name and email.'; errEl.style.display = 'block'; return; }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { errEl.textContent = 'Please enter a valid email address.'; errEl.style.display = 'block'; return; }
      if (!cityRegion) { errEl.textContent = 'Please select your region.'; errEl.style.display = 'block'; return; }
      if (_sms === 'yes' && phone.replace(/\D/g,'').length < 10) { errEl.textContent = 'Please enter a valid mobile number.'; errEl.style.display = 'block'; return; }

      this.disabled = true; this.textContent = 'Setting up alerts...';

      var roles = {};
      document.querySelectorAll('#bbjRegCard .chip.selected').forEach(function(c){ roles[c.dataset.role] = true; });

      _step1Data = { first_name: name, email: email, phone: phone, city_region: cityRegion, region_metro: region_metro, license_state: license_state, roles: roles, sms_opt: _sms === 'yes' };

      // Supabase signUp with temp password
      var tempPass = 'BBJt_' + Math.random().toString(36).slice(2,10) + Math.random().toString(36).slice(2,4) + '!';
      var sbClient = _sb();
      if (sbClient) {
        try {
          var result = await sbClient.auth.signUp({
            email: email, password: tempPass,
            options: { data: { first_name: name, phone: phone.replace(/\D/g,''), city_region: cityRegion, region_metro: region_metro, license_state: license_state, roles: roles, sms_notifications: _sms === 'yes', step: 1 } }
          });
          if (result.error && result.error.message !== 'User already registered') {
            errEl.textContent = result.error.message;
            errEl.style.display = 'block';
            this.disabled = false; this.textContent = 'Get Job Alerts'; return;
          }
        } catch(e) {}
      }

      // Webhook
      try {
        fetch('https://hook.us2.make.com/qv0ynbmsfwf33wknewif43ijdlwif58x', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(Object.assign(bbjAttr('overlay_step1'), { type: 'candidate', first_name: name, email: email,
            phone: phone.replace(/\D/g,''), city_region: cityRegion, region_metro: region_metro, license_state: license_state, sms_consent: _sms === 'yes', roles: roles,
            source: 'overlay_step1', ts: new Date().toISOString(),
            consent: true, consent_timestamp: new Date().toISOString(),
            consent_text: 'By submitting you agree to receive job alerts by email and SMS if opted in.', page_url: window.location.href }))
        });
      } catch(e) {}

      document.cookie = 'bbj_registered=1; max-age=2592000; path=/; SameSite=Lax';
      window.dataLayer = window.dataLayer || []; window.dataLayer.push({ event: 'alert_signup' });

      _showLoader('One moment...');
      setTimeout(function() {
        _hideLoader();
        document.getElementById('bbjSuccess').style.display = 'block';
      }, 1500);
    });

    // ── STEP 2 SUBMIT ─────────────────────────────────────────
    var btn2 = document.getElementById('bbjStep2Btn');
    if (btn2) btn2.addEventListener('click', async function() {
      var city     = document.getElementById('bbjCity').value.trim();
      var state    = document.getElementById('bbjState').value.trim().toUpperCase();
      var password = document.getElementById('bbjPassword').value;
      var errEl    = document.getElementById('bbjErr2');
      errEl.style.display = 'none';

      if (!city || !state || !password) { errEl.textContent = 'Please fill in all fields.'; errEl.style.display = 'block'; return; }
      if (password.length < 8) { errEl.textContent = 'Password must be at least 8 characters.'; errEl.style.display = 'block'; return; }

      this.disabled = true; this.textContent = 'Creating account...';

      var licLevel  = document.getElementById('bbjLicLevel').value;
      var region_metro = _step1Data.region_metro || '';
      var license_state = _step1Data.license_state || '';
      var licJur    = license_state;
      var helpTrain = document.getElementById('bbjHelpY') && document.getElementById('bbjHelpY').classList.contains('selected');
      var helpJobs  = false;

      // Supabase updateUser with real password + profile
      var sbClient = _sb();
      if (sbClient) {
        try {
          var upd = await sbClient.auth.updateUser({
            password: password,
            data: { first_name: _step1Data.first_name, phone: _step1Data.phone,
              city: city, state: state, roles: _step1Data.roles, region_metro: region_metro, license_state: license_state,
              sms_notifications: _step1Data.sms_opt, license_status: _lic,
              license_level: licLevel, license_jurisdiction: licJur, help_training: (document.getElementById("bbjHelpY")||{}).classList&&document.getElementById("bbjHelpY").classList.contains("selected")||false, step: 2 }
          });
          if (upd.error) {
            errEl.textContent = upd.error.message;
            errEl.style.display = 'block';
            this.disabled = false; this.textContent = 'Create Account & View Jobs'; return;
          }
        } catch(e) {}
      }

      // Webhook with full profile
      try {
        fetch('https://hook.us2.make.com/qv0ynbmsfwf33wknewif43ijdlwif58x', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(Object.assign(bbjAttr('overlay_step2'), { type: 'candidate_profile', first_name: _step1Data.first_name,
            email: _step1Data.email, phone: _step1Data.phone, city: city, state: state,
            region_metro: region_metro, license_state: license_state,
            license_status: _lic, license_level: licLevel, license_jurisdiction: licJur, help_training: helpTrain,
            help_jobs: helpJobs, source: 'overlay_step2', ts: new Date().toISOString(),
            consent: true, consent_timestamp: new Date().toISOString(),
            consent_text: 'By submitting you agree to receive job alerts by email and SMS if opted in.', page_url: window.location.href }))
        });
      } catch(e) {}

      window.dataLayer = window.dataLayer || []; window.dataLayer.push({ event: 'account_created' });

      _showLoader('Creating your account...');
      setTimeout(function() { bbjShowBrowseSplash('bbjLoaderSpinner', 'bbjLoaderTxt'); }, 700);
    });

  });

})();

// ─────────────────────────────────────────────────────────────────
// BBJ ACCESS OVERLAY — "Get Access to Jobs" card
// Triggered by Browse All Jobs CTAs
// Single form, no steps, 2s loader, fires webhook + Supabase signUp
// ─────────────────────────────────────────────────────────────────
(function() {

  var accCss = [
    '#bbjAccOvr{display:none;position:fixed;inset:0;z-index:5000;background:rgba(0,8,20,0.75);align-items:flex-end;justify-content:center;}',
    '#bbjAccOvr.open{display:flex;}',
    '@media(min-width:640px){#bbjAccOvr{align-items:center;}}',
    '#bbjAccCard{background:#fff;width:100%;max-width:480px;border-radius:22px 22px 0 0;padding:32px 28px 40px;position:relative;max-height:92dvh;overflow-y:auto;transform:translateY(100%);transition:transform 0.28s ease,opacity 0.28s ease;opacity:0;}',
    '@media(min-width:640px){#bbjAccCard{border-radius:16px;transform:translateY(20px) scale(0.97);}}',
    '#bbjAccOvr.open #bbjAccCard{transform:translateY(0);opacity:1;}',
    '#bbjAccX{position:absolute;top:14px;right:14px;width:32px;height:32px;border-radius:50%;background:#f4f5f7;border:none;cursor:pointer;font-size:1.1rem;color:#5a6474;line-height:1;display:flex;align-items:center;justify-content:center;}',
    '#bbjAccX:hover{background:#e2e5ea;}',
    '#bbjAccCard .acc-title{font-family:"Barlow Condensed",sans-serif;font-weight:800;font-size:1.9rem;color:#000814;line-height:1.1;margin-bottom:4px;}',
    '#bbjAccCard .acc-sub{font-size:0.88rem;color:#5a6474;margin-bottom:20px;}',
    '#bbjAccCard .acc-label{font-size:0.75rem;font-weight:600;color:#5a6474;letter-spacing:0.04em;text-transform:uppercase;margin-bottom:4px;display:block;}',
    '#bbjAccCard input[type=text],#bbjAccCard input[type=email],#bbjAccCard input[type=tel],#bbjAccCard select{width:100%;padding:10px 13px;border:1.5px solid #e2e5ea;border-radius:8px;font-family:"Barlow",sans-serif;font-size:0.92rem;color:#1a1a1a;background:#fff;outline:none;transition:border-color 0.15s;margin-bottom:10px;display:block;-webkit-appearance:none;}',
    '#bbjAccCard input:focus,#bbjAccCard select:focus{border-color:#001D3D;}',
    '#bbjAccCard input::placeholder{color:#a0aab4;}',
    '#bbjAccCard .acc-chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;}',
    '#bbjAccCard .acc-chip{font-family:"Barlow Condensed",sans-serif;font-size:0.85rem;font-weight:700;padding:7px 14px;border-radius:20px;border:1.5px solid #e2e5ea;background:#fff;color:#5a6474;cursor:pointer;transition:all 0.12s;user-select:none;}',
    '#bbjAccCard .acc-chip.selected{background:#000814;border-color:#000814;color:#FFC300;}',
    '#bbjAccCard .acc-toggles{display:flex;gap:8px;margin-bottom:10px;}',
    '#bbjAccCard .acc-toggle{flex:1;padding:10px;font-family:"Barlow Condensed",sans-serif;font-size:0.9rem;font-weight:700;border:1.5px solid #e2e5ea;border-radius:8px;background:#fff;color:#5a6474;cursor:pointer;transition:all 0.12s;text-align:center;}',
    '#bbjAccCard .acc-toggle.selected{background:#000814;border-color:#000814;color:#FFC300;}',
    '#bbjAccCard .acc-reveal{display:none;margin-bottom:10px;}',
    '#bbjAccCard .acc-reveal.visible{display:block;}',
    '#bbjAccCard .acc-reveal-pad{display:none;background:#f4f5f7;border-radius:10px;padding:14px 16px;margin-bottom:10px;border:1px solid #e2e5ea;}',
    '#bbjAccCard .acc-reveal-pad.visible{display:block;}',
    '#bbjAccCard .acc-reveal-pad p{font-size:0.85rem;color:#5a6474;margin-bottom:10px;line-height:1.5;}',
    '#bbjAccCard .acc-help-opts{display:flex;flex-direction:column;gap:10px;margin-top:6px;}',
    '#bbjAccCard .acc-help-opt{display:flex;align-items:flex-start;gap:10px;font-size:0.88rem;color:#1a1a1a;cursor:pointer;line-height:1.4;}',
    '#bbjAccCard .acc-help-opt input[type=checkbox]{width:16px;height:16px;margin:0;padding:0;accent-color:#000814;cursor:pointer;flex-shrink:0;margin-top:2px;}',
    '#bbjAccCard .acc-btn{width:100%;padding:14px;background:#FFC300;color:#000814;font-family:"Barlow Condensed",sans-serif;font-size:1.1rem;font-weight:800;letter-spacing:0.06em;text-transform:uppercase;border:none;border-radius:10px;cursor:pointer;transition:background 0.15s;margin-top:8px;}',
    '#bbjAccCard .acc-btn:hover{background:#FFD60A;}',
    '#bbjAccCard .acc-btn:disabled{opacity:0.4;cursor:not-allowed;}',
    '#bbjAccCard .acc-err{display:none;color:#e53935;font-size:0.82rem;margin-bottom:12px;padding:10px 12px;background:#fff5f5;border-radius:6px;border:1px solid #fcc;}',
    '#bbjAccCard .acc-section-label{font-family:"Barlow Condensed",sans-serif;font-size:0.78rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#000814;margin:16px 0 10px;padding-bottom:6px;border-bottom:2px solid #FFC300;display:block;}',
    '#bbjAccCard hr{border:none;border-top:1px solid #e2e5ea;margin:16px 0;}',
    '#bbjAccCard select{background-image:url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'12\' height=\'8\' viewBox=\'0 0 12 8\'%3E%3Cpath d=\'M1 1l5 5 5-5\' stroke=\'%235a6474\' stroke-width=\'1.5\' fill=\'none\' stroke-linecap=\'round\'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 13px center;padding-right:32px;}',
    '#bbjAccCard .acc-tcpa{font-size:0.7rem;color:#a0aab4;margin-top:10px;line-height:1.5;}',
    '#bbjAccCard .acc-tcpa a{color:#a0aab4;}',
    '#bbjAccCard .acc-signin{text-align:center;font-size:0.86rem;color:#5a6474;margin-top:16px;}',
    '#bbjAccCard .acc-signin a{color:#001D3D;font-weight:600;text-decoration:none;}',
    '#bbjAccLoader{display:none;text-align:center;padding:60px 20px;}',
    '#bbjAccSpinner{width:44px;height:44px;border:3px solid #e2e5ea;border-top-color:#FFC300;border-radius:50%;animation:bbjAccSpin 0.8s linear infinite;margin:0 auto 16px;}',
    '#bbjAccLoaderTxt{font-family:"Barlow Condensed",sans-serif;font-size:1.2rem;font-weight:800;color:#000814;}',
    '@keyframes bbjAccSpin{to{transform:rotate(360deg);}}'
  ].join('');

  // Inject access CSS
  var accStyle = document.createElement('style');
  accStyle.textContent = accCss;
  document.head.appendChild(accStyle);

  var accCard = document.createElement('div');
  accCard.id = 'bbjAccOvr';
  accCard.onclick = function(e){ if(e.target===this) bbjAccClose(); };
  accCard.innerHTML = [
    '<div id="bbjAccCard">',
    '<button id="bbjAccX">&#x2715;</button>',
    '<div id="bbjAccForm">',
      '<h2 class="acc-title">Get Access to Jobs</h2>',
      '<p class="acc-sub" id="bbjAccSub">Free. No resume required.</p>',
      '<div class="acc-err" id="bbjAccErr"></div>',
      '<label class="acc-label">First Name</label>',
      '<input id="bbjAccName" type="text" placeholder="First name" autocomplete="given-name">',
      '<label class="acc-label">Email</label>',
      '<input id="bbjAccEmail" type="email" placeholder="you@email.com" inputmode="email" autocomplete="email">',
      '<label class="acc-label">Region</label>',
      '<select id="bbjAccCityRegion">',
        '<option value="">What\'s your region?</option>',
        '<option value="Dallas|TX">Dallas, TX</option>',
        '<option value="Fort Worth|TX">Fort Worth, TX</option>',
        '<option value="Houston|TX">Houston, TX</option>',
        '<option value="San Antonio|TX">San Antonio, TX</option>',
        '<option value="Austin|TX">Austin, TX</option>',
        '<option value="Chicago|IL">Chicago, IL</option>',
        '<option value="other|">Other / not listed</option>',
      '</select>',
      '<label style="font-size:0.88rem;font-weight:700;color:#1a1a1a;margin-bottom:4px;display:block;">What type of security jobs?</label>',
      '<p style="font-size:0.78rem;color:#5a6474;margin-bottom:10px;">Select all that apply.</p>',
      '<div class="acc-chips">',
        '<div class="acc-chip selected" data-role="all" id="bbjAccChipAll">All Types</div>',
        '<div class="acc-chip" data-role="unarmed">Unarmed</div>',
        '<div class="acc-chip" data-role="armed">Armed</div>',
        '<div class="acc-chip" data-role="overnight">Overnight</div>',
        '<div class="acc-chip" data-role="event">Event</div>',
      '</div>',
      '<label style="font-size:0.88rem;font-weight:700;color:#1a1a1a;margin-bottom:6px;display:block;">Receive SMS alerts for new jobs?</label>',
      '<div class="acc-toggles" style="margin-top:6px;">',
        '<div class="acc-toggle" id="bbjAccSmsY">Yes</div>',
        '<div class="acc-toggle" id="bbjAccSmsN">No thanks</div>',
      '</div>',
      '<div class="acc-reveal" id="bbjAccPhoneWrap">',
        '<label class="acc-label">Mobile Number</label>',
        '<input id="bbjAccPhone" type="tel" placeholder="(214) 000-0000" inputmode="tel" autocomplete="tel">',
      '</div>',
      '<hr>',
      '<div id="bbjAccLicSection">',
      '<span class="acc-section-label" id="bbjAccLicLabel">Texas Security License</span>',
      '<p style="font-size:0.82rem;color:#5a6474;margin-bottom:10px;" id="bbjAccLicQ">Do you hold a Texas DPS security license?</p>',
      '<div class="acc-toggles">',
        '<div class="acc-toggle" id="bbjAccLicY">Yes, I\'m licensed</div>',
        '<div class="acc-toggle" id="bbjAccLicN">Not yet</div>',
      '</div>',
      '<div class="acc-reveal" id="bbjAccLicLevel">',
        '<label class="acc-label">License Level</label>',
        '<select id="bbjAccLicSel"><option value="">Select level</option><option value="level2">Level 2 &#x2014; Non-Commissioned (Unarmed)</option><option value="level3">Level 3 &#x2014; Commissioned (Armed)</option><option value="both">Both Level 2 and Level 3</option></select>',
      '</div>',
      '<div class="acc-reveal" id="bbjAccLicHelp">',
        '<label style="font-size:0.88rem;font-weight:700;color:#1a1a1a;margin-bottom:6px;display:block;">Do you want help getting licensed in your state?</label>',
        '<div class="acc-toggles">',
          '<div class="acc-toggle" id="bbjAccHelpY">Yes</div>',
          '<div class="acc-toggle" id="bbjAccHelpN">No</div>',
        '</div>',
      '</div>',
      '</div>',
      '<button class="acc-btn" id="bbjAccSubmitBtn">Get Access &#x2192;</button>',
      '<p class="acc-tcpa">By submitting you agree to receive job alerts by email and SMS if opted in. <a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank">Privacy Policy</a>.</p>',
      '<p class="acc-signin">Already have an account? <a href="/login.html">Sign in</a></p>',
    '</div>',
    '<div id="bbjAccLoader"><div id="bbjAccSpinner"></div><div id="bbjAccLoaderTxt">Creating your account...</div></div>',
    '</div>'
  ].join('');
  document.body.appendChild(accCard);



  // State
  var _accSms = '', _accLic = '';

  // Fetch job count
  (function(){
    var M = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSGYh2fnA1lRdcI1nLmiohA8YuC6FTdeA5xmF6sga3a-9SPuTMN_o-p28OiAtxPFb5PhTEbNjzIe-UF/pub?gid=885752320&single=true&output=csv';
    fetch(M, {mode:'cors'}).then(function(r){return r.ok?r.text():'';}).then(function(t){
      if(!t)return;
      var n=t.trim().split('\n').slice(1).filter(function(l){return l.toLowerCase().indexOf(',yes')!==-1;}).length;
      var el=document.getElementById('bbjAccSub');
      if(el&&n>0)el.textContent='Currently '+n+' active jobs. Free, no resume required.';
    }).catch(function(){});
  })();

  // Public open — overrides the alias set in alerts overlay
  window.bbjAccOpen = function() {
    document.getElementById('bbjAccForm').style.display = 'block';
    document.getElementById('bbjAccLoader').style.display = 'none';
    document.getElementById('bbjAccErr').style.display = 'none';
    document.getElementById('bbjAccOvr').classList.add('open');
    document.body.style.overflow = 'hidden';
    setTimeout(function(){ document.getElementById('bbjAccName').focus(); }, 350);
  };

  window.bbjAccClose = function() {
    document.getElementById('bbjAccOvr').classList.remove('open');
    document.body.style.overflow = '';
  };

  window.bbjAccSetSms = function(val) {
    _accSms = val;
    document.getElementById('bbjAccSmsY').classList.toggle('selected', val==='yes');
    document.getElementById('bbjAccSmsN').classList.toggle('selected', val==='no');
    document.getElementById('bbjAccPhoneWrap').classList.toggle('visible', val==='yes');
    if(val!=='yes') document.getElementById('bbjAccPhone').value='';
  };

  window.bbjAccSetLic = function(val) {
    _accLic = val;
    document.getElementById('bbjAccLicY').classList.toggle('selected', val==='yes');
    document.getElementById('bbjAccLicN').classList.toggle('selected', val==='no');
    document.getElementById('bbjAccLicLevel').classList.toggle('visible', val==='yes');
    document.getElementById('bbjAccLicHelp').classList.toggle('visible', val==='no');
  };

  window.bbjAccSetHelp = function(val) {
    document.getElementById('bbjAccHelpY').classList.toggle('selected', val==='yes');
    document.getElementById('bbjAccHelpN').classList.toggle('selected', val==='no');
  };

  // Wire access toggles + chips
  document.addEventListener('DOMContentLoaded', function() {
    // Toggles
    document.getElementById('bbjAccSmsY').addEventListener('click', function(){ bbjAccSetSms('yes'); });
    document.getElementById('bbjAccSmsN').addEventListener('click', function(){ bbjAccSetSms('no'); });
    document.getElementById('bbjAccLicY').addEventListener('click', function(){ bbjAccSetLic('yes'); });
    document.getElementById('bbjAccLicN').addEventListener('click', function(){ bbjAccSetLic('no'); });
    document.getElementById('bbjAccHelpY').addEventListener('click', function(){ bbjAccSetHelp('yes'); });
    document.getElementById('bbjAccHelpN').addEventListener('click', function(){ bbjAccSetHelp('no'); });
    document.getElementById('bbjAccX').addEventListener('click', function(){ bbjAccClose(); });
    document.getElementById('bbjAccSubmitBtn').addEventListener('click', function(){ bbjAccSubmit(); });

    // Geo-aware license copy (driven by the region dropdown on this card)
    var accRegionSel = document.getElementById('bbjAccCityRegion');
    window.bbjPrefillRegion(accRegionSel);
    window.bbjWireLicense(
      accRegionSel,
      document.getElementById('bbjAccLicLabel'),
      document.getElementById('bbjAccLicQ'),
      document.getElementById('bbjAccLicSel'),
      document.getElementById('bbjAccLicSection')
    );

    var ca = document.getElementById('bbjAccChipAll');
    if(ca) {
      ca.addEventListener('click', function(){
        var chips=document.querySelectorAll('#bbjAccCard .acc-chip');
        var allOn=this.classList.contains('selected');
        chips.forEach(function(c){c.classList.remove('selected');});
        if(!allOn)this.classList.add('selected');
      });
    }
    document.querySelectorAll('#bbjAccCard .acc-chip:not(#bbjAccChipAll)').forEach(function(c){
      c.addEventListener('click', function(){
        this.classList.toggle('selected');
        var anyOn=Array.from(document.querySelectorAll('#bbjAccCard .acc-chip:not(#bbjAccChipAll)')).some(function(x){return x.classList.contains('selected');});
        var ca=document.getElementById('bbjAccChipAll');
        if(ca)ca.classList.toggle('selected',!anyOn);
      });
    });
  });

  window.bbjAccSubmit = function() {
    var name  = document.getElementById('bbjAccName').value.trim();
    var email = document.getElementById('bbjAccEmail').value.trim();
    var phoneEl = document.getElementById('bbjAccPhone'); var phone = phoneEl ? phoneEl.value.trim() : '';
    var accReg = window.bbjParseRegion(document.getElementById('bbjAccCityRegion').value);
    var region_metro = accReg.metro, license_state = accReg.state, cityRegion = region_metro;
    var errEl = document.getElementById('bbjAccErr');
    errEl.style.display = 'none';

    if(!name){ errEl.textContent='Please enter your first name.'; errEl.style.display='block'; document.getElementById('bbjAccName').focus(); return; }
    if(!email||!email.includes('@')){ errEl.textContent='Please enter a valid email address.'; errEl.style.display='block'; document.getElementById('bbjAccEmail').focus(); return; }
    if(!cityRegion){ errEl.textContent='Please select your region.'; errEl.style.display='block'; document.getElementById('bbjAccCityRegion').focus(); return; }

    var btn = document.getElementById('bbjAccSubmitBtn');
    btn.disabled = true;

    var roles = Array.from(document.querySelectorAll('#bbjAccCard .acc-chip.selected')).map(function(c){return c.dataset.role;}).join(',');
    var licLevel   = (document.getElementById('bbjAccLicSel')||{}).value||'';
    var licJur     = license_state;
    var helpTrain  = document.getElementById('bbjAccHelpY') && document.getElementById('bbjAccHelpY').classList.contains('selected');
    var helpJobs   = false;

    // GTM
    window.dataLayer = window.dataLayer||[];
    window.dataLayer.push({event:'bbj_access_signup', email:email});
    if(typeof gtag!=='undefined') gtag('event','conversion',{'send_to':'AW-17039190320/rYvuCM6Mu7IcELDS9bw_'});

    // Supabase signUp with temp password
    var tempPass = 'BBJt_' + Math.random().toString(36).slice(2,10) + Math.random().toString(36).slice(2,4) + '!';
    try {
      var sb = window.supabase && typeof SUPABASE_URL!=='undefined'
        ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;
      if(sb) {
        sb.auth.signUp({
          email: email, password: tempPass,
          options: { data: { first_name: name, phone: phone.replace(/\D/g,''), city_region: cityRegion, region_metro: region_metro, license_state: license_state, roles: roles,
            sms_notifications: _accSms==='yes', license_status: _accLic,
            license_level: licLevel, license_jurisdiction: licJur, help_training: helpTrain, step: 1 } }
        });
      }
    } catch(e) {}

    // Webhook
    fetch('https://hook.us2.make.com/qv0ynbmsfwf33wknewif43ijdlwif58x', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(Object.assign(bbjAttr('browse_jobs_overlay'), { type:'candidate_access', first_name:name, email:email,
        phone:phone.replace(/\D/g,''), city_region:cityRegion, region_metro:region_metro, license_state:license_state, roles:roles, sms_opt:_accSms,
        license_status:_accLic, license_level:licLevel, license_jurisdiction:licJur,
        help_training:helpTrain, help_jobs:helpJobs,
        source:window.location.href, trigger:'browse_jobs_overlay',
        ts:new Date().toISOString(), consent:true,
        consent_timestamp:new Date().toISOString(),
        consent_text:'By submitting you agree to receive job alerts by email and SMS if opted in.' }))
    });

    document.cookie = 'bbj_registered=1; max-age=2592000; path=/; SameSite=Lax';

    // Loader then job board
    document.getElementById('bbjAccForm').style.display = 'none';
    document.getElementById('bbjAccLoader').style.display = 'block';
    setTimeout(function() { window.bbjShowBrowseSplash('bbjAccSpinner', 'bbjAccLoaderTxt'); }, 700);
  };

})();
