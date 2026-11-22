// Helpers shared by the prices page and the curve page.
const displayDate = new Intl.DateTimeFormat('en-US', {
  month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
});

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

export function dateLabel(value) {
  // Use UTC so timezone differences do not change the displayed calendar date.
  return displayDate.format(new Date(`${value}T00:00:00Z`));
}

export const isoDate = value => /^\d{4}-\d{2}-\d{2}$/.test(value) &&
  Number.isFinite(Date.parse(`${value}T00:00:00Z`));

export function siteNav(current) {
  const link = (href, label) => href === current
    ? `<a href="${href}" aria-current="page">${label}</a>`
    : `<a href="${href}">${label}</a>`;
  return `<nav class="site-nav" aria-label="Pages">${link('/', 'Prices')}${link('/curve', 'Curve &amp; rich/cheap')}</nav>`;
}

export const navCss = `
    .site-nav { display: flex; gap: 20px; font-size: 13px; margin: 0 0 28px; }
    .site-nav a { color: #53616b; text-decoration: none; padding-bottom: 4px; border-bottom: 2px solid transparent; }
    .site-nav a:hover { color: #205840; }
    .site-nav a[aria-current=page] { color: #202c38; font-weight: 600; border-bottom-color: #205840; }`;

export function response(body, status, contentType, head = false, nonce = '') {
  return new Response(head ? null : body, {
    status,
    headers: {
      'Content-Type': contentType,
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      'Content-Security-Policy': `default-src 'none'; style-src 'unsafe-inline'; ${nonce ? `script-src 'nonce-${nonce}'; ` : ''}base-uri 'none'; frame-ancestors 'none'`,
    },
  });
}
