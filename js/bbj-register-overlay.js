(function() {
  // BBJ Register Overlay — single source of truth
  // Mirrors register.html as a floating overlay
  // Update this file to update the overlay on every page

  // ── OVERLAY CSS ──────────────────────────────────────────────
  var css = `
#bbjRegOvr{display:none;position:fixed;inset:0;z-index:5000;background:rgba(0,8,20,0.75);align-items:flex-end;justify-content:center;}
#bbjRegOvr.open{display:flex;}
@media(min-width:640px){#bbjRegOvr{align-items:center;}}
#bbjRegCard{background:#fff;width:100%;max-width:480px;border-radius:22px 22px 0 0;padding:32px 28px 40px;position:relative;max-height:92dvh;overflow-y:auto;transform:translateY(100%);transition:transform 0.28s ease,opacity 0.28s ease;opacity:0;}
@media(min-width:640px){#bbjRegCard{border-radius:16px;transform:translateY(20px) scale(0.97);}}
#bbjRegOvr.open #bbjRegCard{transform:translateY(0);opacity:1;}
#bbjRegX{position:absolute;top:14px;right:14px;width:32px;height:32px;border-radius:50%;background:#f4f5f7;border:none;cursor:pointer;font-size:1.1rem;color:#5a6474;line-height:1;display:flex;align-items:center;justify-content:center;}
#bbjRegX:hover{background:#e2e5ea;}
#bbjRegCard .step-bar{display:flex;gap:6px;margin-bottom:24px;}
#bbjRegCard .step-dot{flex:1;height:3px;border-radius:2px;background:#e2e5ea;transition:background 0.2s;}
#bbjRegCard .step-dot.active{background:#FFC300;}
#bbjRegCard .step-dot.done{background:#000814;}
#bbjRegCard .auth-eyebrow{font-family:'Barlow Condensed',sans-serif;font-size:0.75rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#5a6474;margin-bottom:4px;}
#bbjRegCard .auth-title{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:1.9rem;color:#000814;line-height:1.1;margin-bottom:4px;}
#bbjRegCard .auth-sub{font-size:0.88rem;color:#5a6474;margin-bottom:20px;}
#bbjRegCard .field-label{font-size:0.75rem;font-weight:600;color:#5a6474;letter-spacing:0.04em;text-transform:uppercase;margin-bottom:4px;display:block;}
#bbjRegCard input[type=text],#bbjRegCard input[type=email],#bbjRegCard input[type=tel],#bbjRegCard input[type=password],#bbjRegCard select{width:100%;padding:10px 13px;border:1.5px solid #e2e5ea;border-radius:8px;font-family:'Barlow',sans-serif;font-size:0.92rem;color:#1a1a1a;background:#fff;outline:none;transition:border-color 0.15s;margin-bottom:10px;display:block;-webkit-appearance:none;}
#bbjRegCard input:focus,#bbjRegCard select:focus{border-color:#001D3D;}
#bbjRegCard input::placeholder{color:#a0aab4;}
#bbjRegCard .chip-grid{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;}
#bbjRegCard .chip{font-family:'Barlow Condensed',sans-serif;font-size:0.85rem;font-weight:700;padding:7px 14px;border-radius:20px;border:1.5px solid #e2e5ea;background:#fff;color:#5a6474;cursor:pointer;transition:all 0.12s;user-select:none;}
#bbjRegCard .chip.selected{background:#000814;border-color:#000814;color:#FFC300;}
#bbjRegCard .toggle-row{display:flex;gap:8px;margin-bottom:10px;}
#bbjRegCard .toggle-btn{flex:1;padding:10px;font-family:'Barlow Condensed',sans-serif;font-size:0.9rem;font-weight:700;border:1.5px solid #e2e5ea;border-radius:8px;background:#fff;color:#5a6474;cursor:pointer;transition:all 0.12s;text-align:center;}
#bbjRegCard .toggle-btn.selected{background:#000814;border-color:#000814;color:#FFC300;}
#bbjRegCard .reveal-block{display:none;margin-bottom:10px;}
#bbjRegCard .reveal-block.visible{display:block;}
#bbjRegCard .reveal-block-pad{display:none;background:#f4f5f7;border-radius:10px;padding:14px 16px;margin-bottom:10px;border:1px solid #e2e5ea;}
#bbjRegCard .reveal-block-pad.visible{display:block;}
#bbjRegCard .reveal-block-pad p{font-size:0.85rem;color:#5a6474;margin-bottom:10px;line-height:1.5;}
#bbjRegCard .help-opts{display:flex;flex-direction:column;gap:10px;margin-top:6px;}
#bbjRegCard .help-opt{display:flex;align-items:flex-start;gap:10px;font-size:0.88rem;color:#1a1a1a;cursor:pointer;line-height:1.4;}
#bbjRegCard .help-opt input[type=checkbox]{width:16px;height:16px;margin:0;padding:0;accent-color:#000814;cursor:pointer;flex-shrink:0;margin-top:2px;}
#bbjRegCard .submit-btn{width:100%;padding:14px;background:#FFC300;color:#000814;font-family:'Barlow Condensed',sans-serif;font-size:1.1rem;font-weight:800;letter-spacing:0.06em;text-transform:uppercase;border:none;border-radius:10px;cursor:pointer;transition:background 0.15s;margin-top:8px;}
#bbjRegCard .submit-btn:hover{background:#FFD60A;}
#bbjRegCard .submit-btn:disabled{opacity:0.4;cursor:not-allowed;}
#bbjRegCard .err-msg{display:none;color:#e53935;font-size:0.82rem;margin-bottom:12px;padding:10px 12px;background:#fff5f5;border-radius:6px;border:1px solid #fcc;}
#bbjRegCard .success-wrap{text-align:center;padding:10px 0;}
#bbjRegCard .success-title{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:1.8rem;color:#000814;margin-bottom:6px;}
#bbjRegCard .success-sub{font-size:0.88rem;color:#5a6474;margin-bottom:24px;line-height:1.5;}
#bbjRegCard .network-cta{display:block;width:100%;padding:14px;background:#000814;color:#FFC300;font-family:'Barlow Condensed',sans-serif;font-size:1.05rem;font-weight:800;letter-spacing:0.06em;text-transform:uppercase;border:none;border-radius:10px;cursor:pointer;text-align:center;margin-bottom:10px;text-decoration:none;transition:background 0.15s;}
#bbjRegCard .skip-link{display:block;text-align:center;font-size:0.82rem;color:#5a6474;cursor:pointer;margin-top:8px;text-decoration:none;}
#bbjRegCard .tcpa{font-size:0.7rem;color:#a0aab4;margin-top:10px;line-height:1.5;}
#bbjRegCard .tcpa a{color:#a0aab4;}
#bbjRegCard .signin-link{text-align:center;font-size:0.86rem;color:#5a6474;margin-top:16px;}
#bbjRegCard .signin-link a{color:#001D3D;font-weight:600;text-decoration:none;}
#bbjRegCard hr{border:none;border-top:1px solid #e2e5ea;margin:16px 0;}
#bbjRegCard .section-label{font-family:'Barlow Condensed',sans-serif;font-size:0.78rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#000814;margin:16px 0 10px;padding-bottom:6px;border-bottom:2px solid #FFC300;display:block;}
#bbjRegCard select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%235a6474' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 13px center;padding-right:32px;}
#bbjRegCard .field-row{display:flex;gap:10px;margin-bottom:10px;}
#bbjRegCard .field-row>div{flex:1;}
`;

  // ── OVERLAY HTML ─────────────────────────────────────────────
  var html = `
<style>${css}</style>
<div id="bbjRegOvr" onclick="if(event.target===this)bbjRegClose()">
  <div id="bbjRegCard">
    <button id="bbjRegX" onclick="bbjRegClose()">✕</button>
    <div class="step-bar">
      <div class="step-dot active" id="bbjDot1"></div>
      <div class="step-dot" id="bbjDot2"></div>
    </div>

    <!-- STEP 1 -->
    <div id="bbjStep1">
      <h2 class="auth-title">Get Job Alerts</h2>
      <p class="auth-sub">Free. No resume required. Get notified the moment new openings post.</p>
      <div id="bbjErrMsg" class="err-msg"></div>
      <label class="field-label">First Name</label>
      <input id="bbjFirstName" type="text" placeholder="First name" autocomplete="given-name">
      <label class="field-label">Email</label>
      <input id="bbjEmail" type="email" placeholder="you@email.com" inputmode="email" autocomplete="email">
      <label class="field-label" style="font-size:0.88rem;font-weight:700;color:#1a1a1a;text-transform:none;letter-spacing:0;">What type of security jobs?</label>
      <p style="font-size:0.78rem;color:#5a6474;margin-bottom:10px;">Select all that apply.</p>
      <div class="chip-grid">
        <div class="chip" data-role="all" id="bbjChipAll">All Types</div>
        <div class="chip" data-role="unarmed">Unarmed</div>
        <div class="chip" data-role="armed">Armed</div>
        <div class="chip" data-role="overnight">Overnight</div>
        <div class="chip" data-role="event">Event</div>
      </div>
      <label class="field-label" style="font-size:0.88rem;font-weight:700;color:#1a1a1a;text-transform:none;letter-spacing:0;">Receive SMS alerts for new jobs?</label>
      <div class="toggle-row" style="margin-top:6px;">
        <div class="toggle-btn" id="bbjSmsYes" onclick="bbjSetSms('yes')">Yes</div>
        <div class="toggle-btn" id="bbjSmsNo" onclick="bbjSetSms('no')">No thanks</div>
      </div>
      <div class="reveal-block" id="bbjPhoneBlock">
        <label class="field-label">Mobile Number</label>
        <input id="bbjPhone" type="tel" placeholder="(214) 000-0000" inputmode="tel" autocomplete="tel">
      </div>
      <button class="submit-btn" id="bbjStep1Btn">Get Job Alerts</button>
      <p class="tcpa">By submitting you agree to receive job alerts by email and SMS if opted in. <a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank">Privacy Policy</a>.</p>
      <p class="signin-link">Already have an account? <a href="/login.html">Sign in</a></p>
    </div>

    <!-- SUCCESS -->
    <div id="bbjSuccess" style="display:none;">
      <div class="success-wrap">
        <div class="success-title">You're on the list!</div>
        <p class="success-sub">We'll notify you the moment new security jobs post in your area.</p>
        <button class="submit-btn" onclick="bbjShowStep2()" style="margin-bottom:14px;">Browse All Jobs →</button>
        <p style="font-size:0.88rem;margin-bottom:4px;"><strong>Join the BBJ Network for Free</strong></p>
        <p style="font-size:0.82rem;color:#5a6474;margin-bottom:16px;">No resume required. Free to access.</p>
        <a class="skip-link" href="/job-board">Skip — Browse jobs now</a>
      </div>
    </div>


    <!-- LOADER -->
    <div id="bbjLoader" style="display:none;text-align:center;padding:60px 20px;">
      <div style="width:44px;height:44px;border:3px solid #e2e5ea;border-top-color:#FFC300;border-radius:50%;animation:bbjSpin 0.8s linear infinite;margin:0 auto 16px;"></div>
      <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.2rem;font-weight:800;color:#000814;" id="bbjLoaderTxt">One moment...</div>
    </div>
    <style>@keyframes bbjSpin{to{transform:rotate(360deg);}}</style>

    <!-- STEP 2 -->
    <div id="bbjStep2" style="display:none;">
      <h2 class="auth-title" style="font-size:1.6rem;">Complete Your Profile</h2>
      <p class="auth-sub">Register for BlackBarJobs — get access to more jobs. Free to sign up. No resume required.</p>
      <div id="bbjErrMsg2" class="err-msg"></div>
      <div class="field-row">
        <div><label class="field-label">City</label><input id="bbjCity" type="text" placeholder="Dallas" autocomplete="address-level2"></div>
        <div><label class="field-label">State</label><input id="bbjState" type="text" placeholder="TX" autocomplete="address-level1" maxlength="2"></div>
      </div>
      <span class="section-label">Texas Security License</span>
      <p style="font-size:0.82rem;color:#5a6474;margin-bottom:10px;">Do you hold a Texas DPS security license?</p>
      <div class="toggle-row">
        <div class="toggle-btn" id="bbjLicYes" onclick="bbjSetLic('yes')">Yes, I'm licensed</div>
        <div class="toggle-btn" id="bbjLicNo" onclick="bbjSetLic('no')">Not yet</div>
      </div>
      <div class="reveal-block" id="bbjLicLevelBlock">
        <label class="field-label">License Level</label>
        <select id="bbjLicLevel">
          <option value="">Select level</option>
          <option value="level2">Level 2 — Non-Commissioned (Unarmed)</option>
          <option value="level3">Level 3 — Commissioned (Armed)</option>
          <option value="both">Both Level 2 and Level 3</option>
        </select>
      </div>
      <div class="reveal-block-pad" id="bbjLicHelpBlock">
        <p>No problem — you can still apply to many positions while pursuing your license.</p>
        <div class="help-opts">
          <label class="help-opt"><input type="checkbox" id="bbjHelpTrain"> Connect me with a training program</label>
          <label class="help-opt"><input type="checkbox" id="bbjHelpJobs"> Show me jobs that include training or license sponsorship</label>
        </div>
      </div>
      <hr>
      <label class="field-label">Create a Password</label>
      <input id="bbjPassword" type="password" placeholder="Min. 8 characters" autocomplete="new-password">
      <button class="submit-btn" id="bbjStep2Btn">Create Account &amp; View Jobs</button>
      <p class="tcpa">Free forever. <a href="https://www.termsfeed.com/live/e651a49f-d387-4d53-baa2-d069b9f9677f" target="_blank">Privacy Policy</a>.</p>
    </div>
  </div>
</div>
`;

  // ── INJECT HTML ──────────────────────────────────────────────
  var div = document.createElement('div');
  div.innerHTML = html;
  document.body.appendChild(div);

  // ── SUPABASE CLIENT ──────────────────────────────────────────
  var _sbClient = null;
  if (typeof window.supabase !== 'undefined' && typeof SUPABASE_URL !== 'undefined') {
    try { _sbClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY); } catch(e) {}
  }

  // ── STATE ────────────────────────────────────────────────────
  var _sms = '', _lic = '';
  var _step1Data = {};

  // ── OPEN / CLOSE ─────────────────────────────────────────────
  window.bbjRegOpen = function() {
    document.getElementById('bbjStep1').style.display = 'block';
    document.getElementById('bbjSuccess').style.display = 'none';
    document.getElementById('bbjStep2').style.display = 'none';
    document.getElementById('bbjErrMsg').style.display = 'none';
    bbjSetDots(1);
    document.getElementById('bbjRegOvr').classList.add('open');
    document.body.style.overflow = 'hidden';
    setTimeout(function(){ document.getElementById('bbjFirstName').focus(); }, 350);
  };

  // Aliases for existing CTA wiring
  window.bbjAlertOpen = window.bbjRegOpen;
  window.bbjAccOpen   = window.bbjRegOpen;

  window.bbjRegClose = function() {
    document.getElementById('bbjRegOvr').classList.remove('open');
    document.body.style.overflow = '';
  };

  // ── DOTS ─────────────────────────────────────────────────────
  function bbjSetDots(active) {
    document.getElementById('bbjDot1').className = 'step-dot ' + (active > 1 ? 'done' : 'active');
    document.getElementById('bbjDot2').className = 'step-dot ' + (active >= 2 ? 'active' : '');
  }

  // ── SMS TOGGLE ───────────────────────────────────────────────
  window.bbjSetSms = function(val) {
    _sms = val;
    document.getElementById('bbjSmsYes').classList.toggle('selected', val === 'yes');
    document.getElementById('bbjSmsNo').classList.toggle('selected', val === 'no');
    document.getElementById('bbjPhoneBlock').classList.toggle('visible', val === 'yes');
    if (val !== 'yes') document.getElementById('bbjPhone').value = '';
  };

  // ── LICENSE TOGGLE ───────────────────────────────────────────
  window.bbjSetLic = function(val) {
    _lic = val;
    document.getElementById('bbjLicYes').classList.toggle('selected', val === 'yes');
    document.getElementById('bbjLicNo').classList.toggle('selected', val === 'no');
    document.getElementById('bbjLicLevelBlock').classList.toggle('visible', val === 'yes');
    document.getElementById('bbjLicHelpBlock').classList.toggle('visible', val === 'no');
  };

  // ── CHIPS ────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function() {
    var chipAll = document.getElementById('bbjChipAll');
    if (!chipAll) return;
    chipAll.addEventListener('click', function() {
      var chips = document.querySelectorAll('#bbjRegCard .chip');
      var allOn = this.classList.contains('selected');
      chips.forEach(function(c){ c.classList.remove('selected'); });
      if (!allOn) this.classList.add('selected');
    });
    document.querySelectorAll('#bbjRegCard .chip:not(#bbjChipAll)').forEach(function(c) {
      c.addEventListener('click', function() {
        this.classList.toggle('selected');
        var anyOn = Array.from(document.querySelectorAll('#bbjRegCard .chip:not(#bbjChipAll)')).some(function(x){ return x.classList.contains('selected'); });
        document.getElementById('bbjChipAll').classList.toggle('selected', !anyOn);
      });
    });

    // ── STEP 1 SUBMIT ─────────────────────────────────────────
    document.getElementById('bbjStep1Btn').addEventListener('click', async function() {
      var name  = document.getElementById('bbjFirstName').value.trim();
      var email = document.getElementById('bbjEmail').value.trim();
      var phone = document.getElementById('bbjPhone').value.trim();
      var errEl = document.getElementById('bbjErrMsg');
      errEl.style.display = 'none';

      if (!name || !email) {
        errEl.textContent = 'Please enter your name and email.';
        errEl.style.display = 'block'; return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        errEl.textContent = 'Please enter a valid email address.';
        errEl.style.display = 'block'; return;
      }

      this.disabled = true;
      this.textContent = 'Sending...';

      var roles = Array.from(document.querySelectorAll('#bbjRegCard .chip.selected')).map(function(c){ return c.dataset.role; }).join(',');
      _step1Data = { first_name: name, email: email, phone: phone.replace(/\D/g,''), roles: roles, sms_opt: _sms };

      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({ event: 'alert_form_submit', email: email });
      if (typeof gtag !== 'undefined') gtag('event', 'conversion', { 'send_to': 'AW-17039190320/rYvuCM6Mu7IcELDS9bw_' });

      fetch('https://hook.us2.make.com/qv0ynbmsfwf33wknewif43ijdlwif58x', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.assign({}, _step1Data, {
          timestamp: new Date().toISOString(), source: window.location.href,
          trigger: 'alerts_step1', consent: true,
          consent_timestamp: new Date().toISOString(),
          consent_text: 'By submitting you agree to receive job alerts by email and SMS if opted in.'
        }))
      });

      // Supabase OTP
      if (typeof _sbClient !== 'undefined' && _sbClient !== null) {
        try { await _sbClient.auth.signInWithOtp({ email: email, options: { data: { first_name: name, roles: roles } } }); } catch(e) {}
      }

      document.cookie = 'bbj_registered=1; max-age=2592000; path=/; SameSite=Lax';
      document.getElementById('bbjStep1').style.display = 'none';
      document.getElementById('bbjLoaderTxt').textContent = 'One moment...';
      document.getElementById('bbjLoader').style.display = 'block';
      setTimeout(function() {
        document.getElementById('bbjLoader').style.display = 'none';
        document.getElementById('bbjSuccess').style.display = 'block';
        bbjSetDots(2);
      }, 1500);
    });

    // ── STEP 2 SUBMIT ─────────────────────────────────────────
    document.getElementById('bbjStep2Btn').addEventListener('click', async function() {
      var city     = document.getElementById('bbjCity').value.trim();
      var state    = document.getElementById('bbjState').value.trim();
      var password = document.getElementById('bbjPassword').value.trim();
      var errEl    = document.getElementById('bbjErrMsg2');
      errEl.style.display = 'none';

      if (!password || password.length < 8) {
        errEl.textContent = 'Please enter a password of at least 8 characters.';
        errEl.style.display = 'block'; return;
      }

      this.disabled = true;
      this.textContent = 'Creating account...';

      var licLevel   = document.getElementById('bbjLicLevel').value;
      var helpTrain  = document.getElementById('bbjHelpTrain').checked;
      var helpJobs   = document.getElementById('bbjHelpJobs').checked;

      fetch('https://hook.us2.make.com/qv0ynbmsfwf33wknewif43ijdlwif58x', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.assign({}, _step1Data, {
          timestamp: new Date().toISOString(), city: city, state: state,
          license_status: _lic, license_level: licLevel,
          help_training: helpTrain, help_jobs: helpJobs,
          password_set: true, source: window.location.href,
          trigger: 'register_step2', consent: true,
          consent_timestamp: new Date().toISOString(),
          consent_text: 'Free forever. Privacy Policy applies.'
        }))
      });

      if (typeof _sbClient !== 'undefined' && _sbClient !== null) {
        try {
          await _sbClient.auth.signUp({
            email: _step1Data.email, password: password,
            options: { data: { first_name: _step1Data.first_name, city: city, state: state, roles: _step1Data.roles, license_status: _lic, license_level: licLevel } }
          });
        } catch(e) {}
      }

      document.getElementById('bbjStep2').style.display = 'none';
      document.getElementById('bbjLoaderTxt').textContent = 'Creating your account...';
      document.getElementById('bbjLoader').style.display = 'block';
      setTimeout(function() {
        bbjRegClose();
        window.location.href = '/job-board';
      }, 2000);
    });
  });

  // ── SHOW STEP 2 (from success screen) ────────────────────────
  window.bbjShowStep2 = function() {
    document.getElementById('bbjSuccess').style.display = 'none';
    document.getElementById('bbjStep2').style.display = 'block';
  };

})();
