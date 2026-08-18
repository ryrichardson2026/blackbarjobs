/* bbj-taxonomy.js  ·  Single source of truth for the alert taxonomy (Task 3)
 *
 * Every slug here MUST match feed/board.json exactly (job.vertical / job.role /
 * job.market). Alerts are matched by comparing a saved alert_preferences row against
 * the board, so a slug that is not a real board value silently matches nothing.
 * Verified against feed/board.json on 2026-08-18 (2 verticals, 5 markets).
 *
 * This file is the ONLY place the taxonomy is defined. The dashboard loads it to render
 * the role picker and to validate what it writes. The register overlay does not need the
 * role list: it writes roles:[] on signup ("any role in the chosen vertical") and lets the
 * user narrow roles on the dashboard, so the taxonomy is not forked into the overlay.
 */
(function () {
  window.BBJ_TAX = window.BBJ_TAX || {
    // vertical slug -> { label, roles:[[roleSlug, label], ...] }. Role slugs are the
    // job-TYPE values from the board; time/shift modifiers (night-shift, weekend,
    // part-time, full-time) are shift_pref, not roles, and are intentionally excluded.
    verticals: {
      security: {
        label: 'Security',
        roles: [
          ['unarmed', 'Unarmed'],
          ['armed', 'Armed'],
          ['overnight', 'Overnight'],
          ['event', 'Event'],
          ['mobile-patrol', 'Mobile Patrol'],
          ['loss-prevention', 'Loss Prevention'],
          ['hospital-healthcare', 'Hospital / Healthcare'],
          ['airport-tsa', 'Airport / TSA'],
          ['corporate', 'Corporate'],
          ['residential', 'Residential'],
          ['retail', 'Retail'],
          ['hotel', 'Hotel'],
          ['university', 'University'],
          ['industrial', 'Industrial'],
          ['surveillance', 'Surveillance'],
          ['executive-protection', 'Executive Protection']
        ]
      },
      warehouse: {
        label: 'Warehouse',
        roles: [
          ['forklift', 'Forklift'],
          ['package-handler', 'Package Handler'],
          ['warehouse-associate', 'Warehouse Associate'],
          ['industrial', 'Industrial']
        ]
      }
    },

    // Region display name (register-overlay dropdown / bbjPageMarket) -> board market
    // slug (feed/board.json job.market). Fort Worth rolls up to the dallas (DFW) market,
    // which is how the board keys it.
    metroSlug: {
      'Dallas': 'dallas', 'Fort Worth': 'dallas', 'Houston': 'houston',
      'San Antonio': 'san-antonio', 'Austin': 'austin', 'Chicago': 'chicago'
    },

    // shift_pref chip values. "Any" is the absence of a selection (empty), per DG5.
    shifts: [
      ['day', 'Day / Flexible'],
      ['overnight', 'Overnight'],
      ['weekend', 'Weekend'],
      ['part-time', 'Part-time']
    ]
  };

  // Normalize a region display name (e.g. "Dallas" or "Dallas|TX") to a board market slug.
  window.bbjMetroToSlug = window.bbjMetroToSlug || function (name) {
    if (!name) return '';
    var metro = String(name).split('|')[0].trim();
    return (window.BBJ_TAX.metroSlug[metro]) || '';
  };
})();
