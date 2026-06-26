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
        color: #1a1a1a;
        margin-left: auto;
        padding: 6px 14px;
        border: 1.5px solid #e2e5ea;
        border-radius: 6px;
        transition: border-color 0.15s, color 0.15s;
        white-space: nowrap;
      }
      .bbj-nav-link:hover { border-color: #FFC300; color: #000814; }
      .bbj-nav-link.gold {
        background: #FFC300;
        border-color: #FFC300;
        color: #000814;
      }
      .bbj-nav-link.gold:hover { background: #FFD60A; border-color: #FFD60A; }
      .bbj-nav-signout {
        font-family: 'Barlow', sans-serif;
        font-size: 0.82rem;
        font-weight: 600;
        color: #5a6474;
        background: none;
        border: none;
        cursor: pointer;
        margin-left: 10px;
        padding: 6px 4px;
        white-space: nowrap;
      }
      .bbj-nav-signout:hover { color: #1a1a1a; }
    `;
    document.head.appendChild(s);
  }

  async function renderNav() {
    const nav = document.querySelector('nav');
    if (!nav) return;

    nav.style.justifyContent = 'space-between';

    document.querySelectorAll('.bbj-nav-injected').forEach(el => el.remove());

    const { data: { session } } = await sbClient.auth.getSession();

    const wrap = document.createElement('div');
    wrap.className = 'bbj-nav-injected';
    wrap.style.display = 'flex';
    wrap.style.alignItems = 'center';

    if (session) {
      const dashLink = document.createElement('a');
      dashLink.href = '/dashboard.html';
      dashLink.className = 'bbj-nav-link gold';
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
    } else {
      const signInLink = document.createElement('a');
      signInLink.href = '/login.html';
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