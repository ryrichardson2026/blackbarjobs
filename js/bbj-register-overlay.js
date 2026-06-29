(function() {
  // BBJ Register Overlay — mirrors register.html as floating overlay
  // Supabase: Step 1 signUp with temp pass, Step 2 updateUser with real pass

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
  var html = '<style>' + css + '</style>' +
    '<div id="bbjRegOvr" onclick="if(event.target===this)bbjRegClose()">' +
    '<div id="bbjRegCard">' +
    '<button id="bbjRegX" onclick="bbjRegClose()">✕</button>' +
    '<div class="step-bar">' +
      '<div class="step-dot active" id="bbjDot1"></div>' +
      '<div class="step-dot" id="bbjDot2"></div>' +
    '</div>' +
    // STEP 1
    '<div id="bbjStep1">' +
      '<h2 class="auth-title">Get Job Alerts</h2>' +
      '<p class="auth-sub">Free. No resume required. Get notified the moment new openings post.</p>' +
      '<div id="bbjErr1" class="err-msg"></div>' +
      '<label class="field-label">First Name</label>' +
      '<input id="bbjFirstName" type="text" placeholder="First name" autocomplete="given-name">' +
      '<label class="field-label">Email</label>' +
      '<input id="bbjEmail" type="email" placeholder="you@email.com" inputmode="email" autocomplete="email">' +
      '<label class="field-label" style="font-size:0.88rem;font-weight:700;color:#1a1a1a;text-transform:none;letter-spacing:0;">What type of security jobs?</label>' +
      '<p style="font-size:0.78rem;color:#5a6474;margin-bottom:10px;">Select all that apply.</p>' +
      '<div class="chip-grid">' +
        '<div class="chip" data-role="all" id="bbjChipAll">All Types</div>' +
        '<div class="chip" data-role="unarmed">Unarmed</div>' +
        '<div class="chip" data-role="armed">Armed</div>' +
        '<div class="chip" data-role="overnight">Overnight</div>' +
        '<div class="chip" data-role="event">Event</div>' +
      '</div>' +
      '<label class="field-label" style="font-size:0.88rem;font-weight:700;color:#1a1a1a;text-transform:none;letter-spacing:0;">Receive SMS alerts for new jobs?</label>' +
      '<div class="toggle-row" style="margin-top:6px;">' +
        '<div class="toggle-btn" id="bbjSmsYes" onclick="bbjSetSms(\'yes\')">Yes</div>' +
        '<div class="toggle-btn" id="bbjSmsNo" onclick="bbjSetSms(\'no\')">No thanks</div>' +
      '</div>' +
      '<div class="reveal-block" id="bbjPhoneBlock">' +
        '<label class="field-label">Mobile Number</label>' +
        '<input id="bbjPhone" type="tel" placeholder="(214) 000-0000" inputmode="tel" autocomplete="tel">' +
      '</div>' +
      '<button class="submit-btn" id="bbjStep1Btn">Get Job Alerts</button>' +
      '<p class="tcpa">By submitting you agree to receive job alerts by email and SMS if opted in. <a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank">Privacy Policy</a>.</p>' +
      '<p class="signin-link">Already have an account? <a href="/login.html">Sign in</a></p>' +
    '</div>' +
    // LOADER
    '<div id="bbjLoader"><div id="bbjLoaderSpinner"></div><div id="bbjLoaderTxt">One moment...</div></div>' +
    // SUCCESS
    '<div id="bbjSuccess" style="display:none;">' +
      '<div class="success-wrap">' +
        '<div class="success-title">You\'re on the list!</div>' +
        '<p class="success-sub">We\'ll notify you the moment new security jobs post in your area.</p>' +
        '<button class="submit-btn" onclick="bbjShowStep2()" style="margin-bottom:14px;">Browse All Jobs \u2192</button>' +
        '<a class="signin-link" href="/job-board" style="display:block;margin-top:8px;">Skip \u2014 Browse jobs now</a>' +
      '</div>' +
    '</div>' +
    // STEP 2
    '<div id="bbjStep2" style="display:none;">' +
      '<h2 class="auth-title" style="font-size:1.6rem;">Complete Your Profile</h2>' +
      '<p class="auth-sub">Register for BlackBarJobs \u2014 get access to more jobs. Free to sign up. No resume required.</p>' +
      '<div id="bbjErr2" class="err-msg"></div>' +
      '<div class="field-row">' +
        '<div><label class="field-label">City</label><input id="bbjCity" type="text" placeholder="Dallas" autocomplete="address-level2"></div>' +
        '<div><label class="field-label">State</label><input id="bbjState" type="text" placeholder="TX" autocomplete="address-level1" maxlength="2"></div>' +
      '</div>' +
      '<span class="section-label">Texas Security License</span>' +
      '<p style="font-size:0.82rem;color:#5a6474;margin-bottom:10px;">Do you hold a Texas DPS security license?</p>' +
      '<div class="toggle-row">' +
        '<div class="toggle-btn" id="bbjLicYes" onclick="bbjSetLic(\'yes\')">Yes, I\'m licensed</div>' +
        '<div class="toggle-btn" id="bbjLicNo" onclick="bbjSetLic(\'no\')">Not yet</div>' +
      '</div>' +
      '<div class="reveal-block" id="bbjLicLevelBlock">' +
        '<label class="field-label">License Level</label>' +
        '<select id="bbjLicLevel"><option value="">Select level</option><option value="level2">Level 2 \u2014 Non-Commissioned (Unarmed)</option><option value="level3">Level 3 \u2014 Commissioned (Armed)</option><option value="both">Both Level 2 and Level 3</option></select>' +
      '</div>' +
      '<div class="reveal-block-pad" id="bbjLicHelpBlock">' +
        '<p>No problem \u2014 you can still apply to many positions while pursuing your license.</p>' +
        '<div class="help-opts">' +
          '<label class="help-opt"><input type="checkbox" id="bbjHelpTrain"> Connect me with a training program</label>' +
          '<label class="help-opt"><input type="checkbox" id="bbjHelpJobs"> Show me jobs that include training or license sponsorship</label>' +
        '</div>' +
      '</div>' +
      '<hr>' +
      '<label class="field-label">Create a Password</label>' +
      '<input id="bbjPassword" type="password" placeholder="Min. 8 characters" autocomplete="new-password">' +
      '<button class="submit-btn" id="bbjStep2Btn">Create Account &amp; View Jobs</button>' +
      '<p class="tcpa">Free forever. <a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank">Privacy Policy</a>.</p>' +
    '</div>' +
    '</div></div>';

  // ── INJECT ───────────────────────────────────────────────────
  var div = document.createElement('div');
  div.innerHTML = html;
  document.body.appendChild(div);

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

  window.bbjShowStep2 = function() {
    document.getElementById('bbjSuccess').style.display = 'none';
    document.getElementById('bbjStep2').style.display   = 'block';
    _setDots(2);
  };

  // ── INIT LISTENERS ───────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function() {

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
      var phone = document.getElementById('bbjPhone').value.trim();
      var errEl = document.getElementById('bbjErr1');
      errEl.style.display = 'none';

      if (!name || !email) { errEl.textContent = 'Please enter your name and email.'; errEl.style.display = 'block'; return; }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { errEl.textContent = 'Please enter a valid email address.'; errEl.style.display = 'block'; return; }
      if (_sms === 'yes' && phone.replace(/\D/g,'').length < 10) { errEl.textContent = 'Please enter a valid mobile number.'; errEl.style.display = 'block'; return; }

      this.disabled = true; this.textContent = 'Setting up alerts...';

      var roles = {};
      document.querySelectorAll('#bbjRegCard .chip.selected').forEach(function(c){ roles[c.dataset.role] = true; });

      _step1Data = { first_name: name, email: email, phone: phone, roles: roles, sms_opt: _sms === 'yes' };

      // Supabase signUp with temp password
      var tempPass = 'BBJt_' + Math.random().toString(36).slice(2,10) + Math.random().toString(36).slice(2,4) + '!';
      var sbClient = _sb();
      if (sbClient) {
        try {
          var result = await sbClient.auth.signUp({
            email: email, password: tempPass,
            options: { data: { first_name: name, phone: phone.replace(/\D/g,''), roles: roles, sms_notifications: _sms === 'yes', step: 1 } }
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
          body: JSON.stringify({ type: 'candidate', first_name: name, email: email,
            phone: phone.replace(/\D/g,''), sms_consent: _sms === 'yes', roles: roles,
            source: 'overlay_step1', ts: new Date().toISOString() })
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
      var helpTrain = document.getElementById('bbjHelpTrain').checked;
      var helpJobs  = document.getElementById('bbjHelpJobs').checked;

      // Supabase updateUser with real password + profile
      var sbClient = _sb();
      if (sbClient) {
        try {
          var upd = await sbClient.auth.updateUser({
            password: password,
            data: { first_name: _step1Data.first_name, phone: _step1Data.phone,
              city: city, state: state, roles: _step1Data.roles,
              sms_notifications: _step1Data.sms_opt, license_status: _lic,
              license_level: licLevel, help_training: helpTrain, help_jobs: helpJobs, step: 2 }
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
          body: JSON.stringify({ type: 'candidate_profile', first_name: _step1Data.first_name,
            email: _step1Data.email, phone: _step1Data.phone, city: city, state: state,
            license_status: _lic, license_level: licLevel, help_training: helpTrain,
            help_jobs: helpJobs, source: 'overlay_step2', ts: new Date().toISOString() })
        });
      } catch(e) {}

      window.dataLayer = window.dataLayer || []; window.dataLayer.push({ event: 'account_created' });

      _showLoader('Creating your account...');
      setTimeout(function() { bbjRegClose(); window.location.href = '/job-board'; }, 2000);
    });

  });

})();
