(function () {
  const sbClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

  if (!document.getElementById('bbj-nav-styles')) {
    const s = document.createElement('style');
    s.id = 'bbj-nav-styles';
    s.textContent = `
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
      }
      .bbj-nav-link:hover { color: #FFC300; }
      .bbj-nav-link.gold {
        background: none;
        border: none;
        color: rgba(255,255,255,0.85);
      }
      .bbj-nav-signout {
        font-family: 'Barlow', sans-serif;
        font-size: 0.82rem;
        font-weight: 600;
        color: rgba(255,255,255,0.45);
        background: none;
        border: none;
        cursor: pointer;
        margin-left: 14px;
        padding: 6px 0;
        white-space: nowrap;
        transition: color 0.15s;
      }
      .bbj-nav-signout:hover { color: rgba(255,255,255,0.85); }
    `;
    document.head.appendChild(s);
  }

  async function renderNav() {
    const nav = document.querySelector('nav');
    if (!nav) return;
    nav.style.justifyContent = 'space-between';

    // Remove any previously injected nav elements
    document.querySelectorAll('.bbj-nav-injected').forEach(el => el.remove());

    const { data: { session } } = await sbClient.auth.getSession();

    const wrap = document.createElement('div');
    wrap.className = 'bbj-nav-injected';
    wrap.style.cssText = 'display:flex;align-items:center;gap:4px;';

    if (session) {
      // Logged in: plain text Dashboard link + Sign Out
      const dashLink = document.createElement('a');
      dashLink.href = '/dashboard.html';
      dashLink.className = 'bbj-nav-link';
      dashLink.textContent = 'Dashboard';

      const signOutBtn = document.createElement('button');
      signOutBtn.className = 'bbj-nav-signout';
      signOutBtn.textContent = 'Sign Out';
      signOutBtn.addEventListener('click', async () => {
        await sbClient.auth.signOut();
        window.location.reload();
      });

      wrap.appendChild(dashLink);
      wrap.appendChild(signOutBtn);

      // Hide hero CTA ("Get Free Job Alerts" button) for logged-in users
      const heroCta = document.querySelector('.hero-btn.gold, .board-hero-actions a, .board-hero-actions');
      if (heroCta) heroCta.style.display = 'none';

      // Also hide the nav Get Alerts button if present
      const alertsBtn = document.querySelector('.nav-cta');
      if (alertsBtn) alertsBtn.style.display = 'none';

    } else {
      // Logged out: Sign In link
      const signInLink = document.createElement('a');
      signInLink.href = '/login.html';
      signInLink.className = 'bbj-nav-link gold';
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