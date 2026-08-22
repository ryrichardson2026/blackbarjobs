(function () {
  const sbClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

  // ---------------------------------------------------------------
  // Standard menu — single source of truth for the whole site.
  // To add a market/link later, edit MENU_HTML here only.
  // ---------------------------------------------------------------
  const MENU_HTML = `
    <button class="tx-nav-toggle" aria-label="Menu">&#9776;</button>
    <div class="tx-nav-links">
      <div class="tx-nav-drop">
        <button class="tx-nav-drop-btn" type="button">Locations <span style="font-size:0.7rem;">&#9660;</span></button>
        <div class="tx-nav-drop-menu">
          <a href="/dallas">Dallas&#8211;Fort Worth</a>
          <a href="/houston">Houston</a>
          <a href="/san-antonio">San Antonio</a>
          <a href="/chicago">Chicago</a>
        </div>
      </div>
      <a href="/job-board">Find Jobs</a>
      <div class="tx-nav-drop">
        <button class="tx-nav-drop-btn" type="button">Employers <span style="font-size:0.7rem;">&#9660;</span></button>
        <div class="tx-nav-drop-menu">
          <a href="/employers-tx">Hire Officers</a>
          <a href="/#employers">Hiring Guides</a>
        </div>
      </div>
      <a href="/#resources">Resources</a>
      <a href="/about">About Us</a>
    </div>`;

  // ---------------------------------------------------------------
  // Styles (menu + auth). nav positioning is left untouched so we
  // don't override the page's fixed nav.
  // ---------------------------------------------------------------
  if (!document.getElementById('bbj-nav-styles')) {
    const s = document.createElement('style');
    s.id = 'bbj-nav-styles';
    s.textContent = `
      nav {
        display: flex !important;
        align-items: center !important;
        flex-wrap: nowrap !important;
      }
      /* Standard menu */
      .tx-nav-links { display: flex; align-items: center; gap: 22px; margin-left: auto; }
      .tx-nav-links a, .tx-nav-drop-btn {
        font-family: 'Barlow Condensed', sans-serif; font-size: 0.9rem; font-weight: 700;
        letter-spacing: 0.05em; text-transform: uppercase; color: #001D3D; text-decoration: none;
        background: none; border: none; cursor: pointer; padding: 6px 0; white-space: nowrap;
        display: inline-flex; align-items: center; gap: 4px; transition: color 0.15s;
      }
      .tx-nav-links a:hover, .tx-nav-drop-btn:hover { color: #E6A800; }
      .tx-nav-drop { position: relative; }
      .tx-nav-drop-menu {
        display: none; position: absolute; top: 100%; left: 0; margin-top: 8px; background: #fff;
        border: 1px solid #e2e5ea; border-radius: 10px; padding: 6px; min-width: 190px;
        box-shadow: 0 8px 24px rgba(0,8,20,0.10); z-index: 300;
      }
      .tx-nav-drop.open .tx-nav-drop-menu { display: block; }
      .tx-nav-drop-menu a { display: block; padding: 9px 12px; border-radius: 7px; font-size: 0.82rem; }
      .tx-nav-drop-menu a:hover { background: #f7f8fa; color: #001D3D; }
      .tx-nav-toggle {
        display: none; background: none; border: none; cursor: pointer; padding: 6px;
        font-size: 1.4rem; color: #001D3D; line-height: 1; margin-left: auto;
      }
      @media (max-width: 860px) {
        .tx-nav-toggle { display: block; }
        .tx-nav-links {
          display: none; position: absolute; top: 100%; left: 0; right: 0; flex-direction: column;
          align-items: flex-start; gap: 0; margin-left: 0; background: #fff;
          border-bottom: 1px solid #e2e5ea; padding: 8px 20px 16px; box-shadow: 0 8px 24px rgba(0,8,20,0.08);
        }
        .tx-nav-links.open { display: flex; }
        .tx-nav-links > a, .tx-nav-drop { width: 100%; padding: 4px 0; }
        .tx-nav-drop-menu { position: static; box-shadow: none; border: none; padding: 0 0 0 12px; margin-top: 2px; display: block; min-width: 0; }
        .tx-nav-drop-menu a { padding: 7px 0; }
        .tx-nav-drop-btn { padding: 8px 0; }
      }
      /* Auth button */
      .bbj-nav-injected { display: flex; align-items: center; flex-shrink: 0; margin-left: 16px; }
      .bbj-nav-signout, .bbj-nav-signin {
        font-family: 'Barlow Condensed', sans-serif; font-size: 0.85rem; font-weight: 700;
        letter-spacing: 0.05em; text-transform: uppercase; color: rgba(255,255,255,0.85);
        background: none; border: none; cursor: pointer; padding: 6px 0; white-space: nowrap;
        text-decoration: none; transition: color 0.15s; -webkit-tap-highlight-color: transparent;
      }
      .bbj-nav-signout:hover, .bbj-nav-signin:hover { color: #FFC300; }
      /* Light nav pages (login, register): darken auth + menu text */
      .bbj-nav-light .bbj-nav-signout, .bbj-nav-light .bbj-nav-signin { color: #001D3D; }
      .bbj-nav-light .bbj-nav-signout:hover, .bbj-nav-light .bbj-nav-signin:hover { color: #FFC300; }
      @media (max-width: 480px) {
        .bbj-nav-signout, .bbj-nav-signin { font-size: 0.8rem; }
      }
    `;
    document.head.appendChild(s);
  }

  function navIsLight() {
    const nav = document.querySelector('nav');
    if (!nav) return false;
    const bg = window.getComputedStyle(nav).backgroundColor;
    const m = bg.match(/\d+/g);
    if (!m) return false;
    const [r, g, b] = m.map(Number);
    return (r + g + b) / 3 > 180;
  }

  // Inject the standard menu into <nav>, replacing any legacy nav content.
  function renderMenu() {
    const nav = document.querySelector('nav');
    if (!nav) return;

    // Strip legacy/duplicate nav bits (inline homepage menu, "back to jobs",
    // old Get Alerts CTA) — never the logo.
    nav.querySelectorAll('.tx-nav-links, .tx-nav-toggle, .nav-back, .nav-cta').forEach(el => el.remove());

    const authWrap = nav.querySelector('.bbj-nav-injected');
    const frag = document.createElement('div');
    frag.innerHTML = MENU_HTML.trim();
    Array.from(frag.children).forEach(node => {
      if (authWrap) nav.insertBefore(node, authWrap);
      else nav.appendChild(node);
    });

    wireMenu(nav);
  }

  function wireMenu(nav) {
    const toggle = nav.querySelector('.tx-nav-toggle');
    const links = nav.querySelector('.tx-nav-links');

    if (toggle && links) {
      toggle.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        links.classList.toggle('open');
      });
    }

    nav.querySelectorAll('.tx-nav-drop-btn').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const drop = btn.closest('.tx-nav-drop');
        const wasOpen = drop.classList.contains('open');
        nav.querySelectorAll('.tx-nav-drop.open').forEach(d => d.classList.remove('open'));
        if (!wasOpen) drop.classList.add('open');
      });
    });

    // Click outside closes any open dropdown + the mobile panel.
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target)) {
        nav.querySelectorAll('.tx-nav-drop.open').forEach(d => d.classList.remove('open'));
        if (links) links.classList.remove('open');
      }
    });
  }

  async function renderNav() {
    const nav = document.querySelector('nav');
    if (!nav) return;

    document.querySelectorAll('.bbj-nav-injected').forEach(el => el.remove());

    if (navIsLight()) nav.classList.add('bbj-nav-light');
    else nav.classList.remove('bbj-nav-light');

    const { data: { session } } = await sbClient.auth.getSession();
    const wrap = document.createElement('div');
    wrap.className = 'bbj-nav-injected';

    if (session) {
      // Logged in: Sign Out only
      const signOutBtn = document.createElement('button');
      signOutBtn.className   = 'bbj-nav-signout';
      signOutBtn.textContent = 'Sign Out';
      signOutBtn.addEventListener('click', async () => {
        await sbClient.auth.signOut();
        window.location.href = '/job-board';
      });
      wrap.appendChild(signOutBtn);

      // Hide hero CTAs when logged in
      document.querySelectorAll('.hero-btn.gold, .board-hero-actions').forEach(el => {
        el.style.display = 'none';
      });

    } else {
      // Logged out: Sign In link
      const signInLink = document.createElement('a');
      signInLink.href        = '/login.html';
      signInLink.className    = 'bbj-nav-signin';
      signInLink.textContent  = 'Sign In';
      wrap.appendChild(signInLink);
    }

    nav.appendChild(wrap);
  }

  function init() {
    renderMenu();
    renderNav();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
