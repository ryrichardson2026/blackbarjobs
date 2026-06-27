(function () {
  const sbClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

  if (!document.getElementById('bbj-nav-styles')) {
    const s = document.createElement('style');
    s.id = 'bbj-nav-styles';
    s.textContent = `
      /* Ensure nav always lays out correctly */
      nav {
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        flex-wrap: nowrap !important;
      }
      /* Push Get Alerts to center, Sign In to far right */
      .nav-cta {
        margin-left: auto !important;
        margin-right: auto !important;
        text-align: center;
      }
      .bbj-nav-injected {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        margin-left: 16px;
      }
      .bbj-nav-signout {
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: rgba(255,255,255,0.85);
        background: none;
        border: none;
        cursor: pointer;
        padding: 6px 0;
        white-space: nowrap;
        transition: color 0.15s;
        -webkit-tap-highlight-color: transparent;
      }
      .bbj-nav-signout:hover { color: #FFC300; }
      .bbj-nav-signin {
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        text-decoration: none;
        color: rgba(255,255,255,0.85);
        padding: 6px 0;
        white-space: nowrap;
        transition: color 0.15s;
        -webkit-tap-highlight-color: transparent;
      }
      .bbj-nav-signin:hover { color: #FFC300; }
      /* Light nav pages (login, register) */
      .bbj-nav-light .bbj-nav-signout,
      .bbj-nav-light .bbj-nav-signin { color: #001D3D; }
      .bbj-nav-light .bbj-nav-signout:hover,
      .bbj-nav-light .bbj-nav-signin:hover { color: #FFC300; }
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

      // Hide Get Alerts button — not needed when logged in
      const alertsBtn = document.querySelector('.nav-cta');
      if (alertsBtn) alertsBtn.style.display = 'none';

      // Hide hero CTAs
      document.querySelectorAll('.hero-btn.gold, .board-hero-actions').forEach(el => {
        el.style.display = 'none';
      });

    } else {
      // Logged out: Sign In link
      const signInLink = document.createElement('a');
      signInLink.href        = '/login.html';
      signInLink.className   = 'bbj-nav-signin';
      signInLink.textContent = 'Sign In';
      wrap.appendChild(signInLink);
    }

    nav.appendChild(wrap);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderNav);
  } else {
    renderNav();
  }
})();