(function () {
  const sbClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

  // Detect if nav has a light background so we can use dark text
  function navIsLight() {
    const nav = document.querySelector('nav');
    if (!nav) return false;
    const bg = window.getComputedStyle(nav).backgroundColor;
    // Parse rgb values
    const m = bg.match(/\d+/g);
    if (!m) return false;
    const [r, g, b] = m.map(Number);
    // Luminance check — light if avg channel > 180
    return (r + g + b) / 3 > 180;
  }

  if (!document.getElementById('bbj-nav-styles')) {
    const s = document.createElement('style');
    s.id = 'bbj-nav-styles';
    s.textContent = `
      /* Nav layout — prevent overflow on mobile */
      nav {
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        flex-wrap: nowrap !important;
        overflow: hidden;
      }
      .nav-logo, .nav-brand {
        flex-shrink: 0;
        min-width: 0;
        white-space: nowrap;
      }
      .bbj-nav-injected {
        display: flex;
        align-items: center;
        gap: 4px;
        flex-shrink: 0;
        margin-left: auto;
      }

      /* Default: light text (dark nav) */
      .bbj-nav-link {
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 0.9rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        text-decoration: none;
        color: rgba(255,255,255,0.85);
        padding: 6px 4px;
        white-space: nowrap;
        transition: color 0.15s;
        -webkit-tap-highlight-color: transparent;
      }
      .bbj-nav-link:hover { color: #FFC300; }

      .bbj-nav-signout {
        font-family: 'Barlow', sans-serif;
        font-size: 0.82rem;
        font-weight: 600;
        color: rgba(255,255,255,0.45);
        background: none;
        border: none;
        cursor: pointer;
        margin-left: 10px;
        padding: 6px 0;
        white-space: nowrap;
        transition: color 0.15s;
        -webkit-tap-highlight-color: transparent;
      }
      .bbj-nav-signout:hover { color: rgba(255,255,255,0.85); }

      /* Light nav overrides (register, login, dashboard) */
      .bbj-nav-light .bbj-nav-link {
        color: #001D3D;
      }
      .bbj-nav-light .bbj-nav-link:hover { color: #000814; }
      .bbj-nav-light .bbj-nav-signout {
        color: #a0aab4;
      }
      .bbj-nav-light .bbj-nav-signout:hover { color: #1a1a1a; }

      /* Mobile tap target */
      @media (max-width: 600px) {
        .bbj-nav-link { font-size: 0.82rem; padding: 8px 6px; }
        .bbj-nav-signout { font-size: 0.78rem; margin-left: 6px; }
      }
    `;
    document.head.appendChild(s);
  }

  async function renderNav() {
    const nav = document.querySelector('nav');
    if (!nav) return;

    // Remove any previously injected elements
    document.querySelectorAll('.bbj-nav-injected').forEach(el => el.remove());

    // Apply light class if nav background is light
    if (navIsLight()) {
      nav.classList.add('bbj-nav-light');
    } else {
      nav.classList.remove('bbj-nav-light');
    }

    const { data: { session } } = await sbClient.auth.getSession();

    const wrap = document.createElement('div');
    wrap.className = 'bbj-nav-injected';

    if (session) {
      // Logged in: Dashboard text link + Sign Out
      const dashLink = document.createElement('a');
      dashLink.href      = '/dashboard.html';
      dashLink.className = 'bbj-nav-link';
      dashLink.textContent = 'Dashboard';

      const signOutBtn = document.createElement('button');
      signOutBtn.className   = 'bbj-nav-signout';
      signOutBtn.textContent = 'Sign Out';
      signOutBtn.addEventListener('click', async () => {
        await sbClient.auth.signOut();
        window.location.href = '/job-board';
      });

      wrap.appendChild(dashLink);
      wrap.appendChild(signOutBtn);

      // Hide hero CTA and Get Alerts button for logged-in users
      document.querySelectorAll('.hero-btn.gold, .board-hero-actions, .nav-cta').forEach(el => {
        el.style.display = 'none';
      });

    } else {
      // Logged out: Sign In link
      const signInLink = document.createElement('a');
      signInLink.href      = '/login.html';
      signInLink.className = 'bbj-nav-link';
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