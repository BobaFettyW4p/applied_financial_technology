// The Worker reads calculated prices from R2 and builds the table on each visit.
const DATA_KEY = 'treasury_prices.json';
const amount = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 6, maximumFractionDigits: 6,
});
const percent = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 });
const displayDate = new Intl.DateTimeFormat('en-US', {
  month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
});

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

function dateLabel(value) {
  // Use UTC so timezone differences do not change the displayed calendar date.
  return displayDate.format(new Date(`${value}T00:00:00Z`));
}

export function validatePrices(rows) {
  if (!Array.isArray(rows) || !rows.length) throw new Error('No price records found');
  const seen = new Set();
  for (const row of rows) {
    if (!row || !/^[A-Z0-9]{9}$/.test(row.cusip) || seen.has(row.cusip)) {
      throw new Error('A price record has a missing or duplicate CUSIP');
    }
    seen.add(row.cusip);
    for (const field of ['maturity', 'price_date', 'settlement_date']) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(row[field]) ||
          !Number.isFinite(Date.parse(`${row[field]}T00:00:00Z`))) {
        throw new Error(`Invalid ${field} for ${row.cusip}`);
      }
    }
    for (const field of ['coupon', 'clean_price', 'accrued_interest', 'dirty_price']) {
      if (typeof row[field] !== 'number' || !Number.isFinite(row[field]) || row[field] < 0) {
        throw new Error(`Invalid ${field} for ${row.cusip}`);
      }
    }
    if (row.price_date !== rows[0].price_date || row.settlement_date !== rows[0].settlement_date) {
      throw new Error('The file contains more than one pricing or settlement date');
    }
  }
  return [...rows].sort((a, b) =>
    a.maturity.localeCompare(b.maturity) || a.cusip.localeCompare(b.cusip));
}

export function renderPage(rows, nonce = '') {
  const { price_date: priceDate, settlement_date: settlement } = rows[0];
  const tableRows = rows.map(row => `
            <tr data-type="${escapeHtml(row.security_type)}" data-coupon="${row.coupon}" data-maturity="${row.maturity}"
                data-clean="${row.clean_price}" data-accrued="${row.accrued_interest}" data-dirty="${row.dirty_price}">
              <th scope="row">${escapeHtml(row.cusip)}</th>
              <td class="number">${percent.format(row.coupon)}%</td>
              <td class="maturity"><time datetime="${row.maturity}">${dateLabel(row.maturity)}</time></td>
              <td class="number">${amount.format(row.clean_price)}</td>
              <td class="number">${amount.format(row.accrued_interest)}</td>
              <td class="number dirty">${amount.format(row.dirty_price)}</td>
            </tr>`).join('');

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Treasury note and bond prices, including accrued interest for settlement on ${settlement}.">
  <title>Treasury prices</title>
  <style>
    :root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #202c38; background: #f5f4ef; font-synthesis: none; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    main { max-width: 1180px; padding: 56px 28px 32px; margin: auto; }
    .eyebrow { font-size: 12px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; color: #577263; }
    h1 { font-family: Georgia, "Times New Roman", serif; font-size: clamp(36px, 5vw, 52px);
      font-weight: 400; letter-spacing: -.035em; margin: 12px 0 16px; }
    .intro { max-width: 660px; font-size: 16px; line-height: 1.7; color: #53616b; margin: 0; }
    .dates { display: flex; gap: 32px; flex-wrap: wrap; margin: 30px 0; }
    .dates div { border-left: 2px solid #becbc0; padding-left: 14px; }
    dt { color: #66736c; font-size: 12px; margin-bottom: 6px; }
    dd { margin: 0; font-size: 15px; font-weight: 600; }
    .table-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin: 36px 0 12px; }
    h2 { font-size: 16px; margin: 0; }
    .units { font-size: 12px; color: #63716c; margin: 0; }
    .filters { display: flex; flex-wrap: wrap; gap: 14px 18px; align-items: end; margin: 0 0 14px; }
    .filters label { display: grid; gap: 4px; font-size: 12px; color: #66736c; }
    .filters input, .filters select { font: inherit; font-size: 13px; padding: 7px 9px; color: inherit;
      border: 1px solid #c9d1c6; border-radius: 6px; background: #fff; width: 128px; }
    .filters input[type=search] { width: 160px; }
    .filters button { font: inherit; font-size: 13px; padding: 7px 12px; border: 1px solid #c9d1c6;
      border-radius: 6px; background: #fff; cursor: pointer; }
    .count { font-size: 12px; color: #63716c; margin: 0 0 10px; }
    th .sort { all: unset; cursor: pointer; display: inline-flex; gap: 6px; align-items: center; }
    th .sort:focus-visible { outline: 3px solid #547c60; outline-offset: 2px; }
    th .sort::after { content: "\\2195"; color: #9aa89f; font-size: 11px; }
    th[aria-sort=ascending] .sort::after { content: "\\2191"; color: #205840; }
    th[aria-sort=descending] .sort::after { content: "\\2193"; color: #205840; }
    .table-scroll { max-height: 65vh; overflow: auto; background: #fff;
      border: 1px solid #dce0d8; border-radius: 8px; }
    table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; }
    caption { text-align: left; padding: 12px 18px; font-size: 12px; color: #66736c; }
    thead th { position: sticky; top: 0; background: #e9eee7; font-size: 12px; white-space: nowrap;
      z-index: 1; border-top: 1px solid #dce0d8; border-bottom: 1px solid #d3dcd2; }
    th, td { text-align: left; padding: 14px 18px; }
    tbody th { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 500; letter-spacing: .015em; }
    tbody th, tbody td { border-bottom: 1px solid #edf0ea; white-space: nowrap; }
    tbody tr:last-child > * { border-bottom: 0; }
    tbody tr:hover { background: #f7f9f4; }
    .number { text-align: right; font-variant-numeric: tabular-nums; }
    .dirty { color: #205840; font-weight: 600; }
    .notes { font-size: 12px; line-height: 1.8; color: #657169; margin: 18px 0 0; }
    footer { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px 24px;
      padding-top: 24px; margin-top: 30px; border-top: 1px solid #dce0d8; font-size: 12px; color: #657169; }
    a { color: #205840; text-underline-offset: 3px; }
    a:focus-visible, .table-scroll:focus-visible { outline: 3px solid #547c60; outline-offset: 4px; }
    @media (max-width: 600px) {
      main { padding: 32px 16px; }
      .dates { gap: 20px; }
      .table-heading { display: block; }
      .units { margin-top: 8px; }
      th, td { padding: 12px; }
      .table-scroll { max-height: 70vh; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">U.S. Treasury · Notes &amp; bonds</div>
      <h1>Treasury prices</h1>
      <p class="intro">Quoted prices with the interest owed to the seller at settlement.
        Dirty price is the clean price plus accrued interest.</p>
      <dl class="dates">
        <div><dt>Price date</dt><dd><time datetime="${priceDate}">${dateLabel(priceDate)}</time></dd></div>
        <div><dt>Settlement date</dt><dd><time datetime="${settlement}">${dateLabel(settlement)}</time></dd></div>
        <div><dt>Securities</dt><dd>${rows.length} notes and bonds</dd></div>
      </dl>
    </header>
    <section aria-labelledby="table-title">
      <div class="table-heading">
        <h2 id="table-title">Prices by maturity</h2>
        <p class="units">USD per $100 face value · Annual coupon rates</p>
      </div>
      <form class="filters" id="filters" aria-label="Filter securities" hidden>
        <label>CUSIP<input type="search" name="cusip" placeholder="e.g. 91282C" autocomplete="off"></label>
        <label>Type<select name="type"><option value="">All</option><option>Note</option><option>Bond</option></select></label>
        <label>Coupon min (%)<input type="number" name="cmin" step="0.125" min="0"></label>
        <label>Coupon max (%)<input type="number" name="cmax" step="0.125" min="0"></label>
        <label>Maturity from<input type="date" name="mfrom"></label>
        <label>Maturity to<input type="date" name="mto"></label>
        <button type="reset">Clear</button>
      </form>
      <p class="count" id="count" aria-live="polite"></p>
      <div class="table-scroll" tabindex="0" role="region" aria-label="Treasury prices, scroll for more securities">
        <table>
          <caption>${rows.length} securities, sorted by maturity from earliest to latest.</caption>
          <thead><tr>
            <th scope="col">CUSIP</th>
            <th scope="col" class="number">Coupon</th>
            <th scope="col">Maturity</th>
            <th scope="col" class="number">Clean price</th>
            <th scope="col" class="number">Accrued interest</th>
            <th scope="col" class="number">Dirty price</th>
          </tr></thead>
          <tbody>${tableRows}
          </tbody>
        </table>
      </div>
      <p class="notes">Clean prices use the FedInvest end-of-day quotes. Accrued interest uses actual days
        between Treasury coupon dates. Bills, TIPS, and floating-rate notes are excluded.<br>
        Amounts are displayed to six decimal places. The JSON download retains eight decimal places.</p>
    </section>
    <footer>
      <span>Sources: FedInvest prices and Treasury security terms.</span>
      <a href="/api/prices" download="treasury_prices.json">Download price data (JSON)</a>
    </footer>
  </main>
  <script nonce="${nonce}">
  (() => {
    const body = document.querySelector('tbody');
    const rows = [...body.rows];
    const form = document.getElementById('filters');
    const count = document.getElementById('count');
    const heads = [...document.querySelectorAll('thead th')];
    const keys = [['text'], ['num', 'coupon'], ['text', 'maturity'], ['num', 'clean'], ['num', 'accrued'], ['num', 'dirty']];
    form.hidden = false;
    function apply() {
      const f = Object.fromEntries(new FormData(form));
      const q = (f.cusip || '').trim().toUpperCase();
      let shown = 0;
      for (const r of rows) {
        const d = r.dataset, coupon = Number(d.coupon);
        const ok = (!q || r.cells[0].textContent.includes(q)) &&
          (!f.type || d.type === f.type) &&
          (f.cmin === '' || f.cmin === undefined || coupon >= Number(f.cmin)) &&
          (f.cmax === '' || f.cmax === undefined || coupon <= Number(f.cmax)) &&
          (!f.mfrom || d.maturity >= f.mfrom) && (!f.mto || d.maturity <= f.mto);
        r.hidden = !ok; if (ok) shown++;
      }
      count.textContent = 'Showing ' + shown + ' of ' + rows.length + ' securities';
    }
    heads.forEach((th, i) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'sort'; b.textContent = th.textContent;
      th.textContent = ''; th.append(b);
      b.addEventListener('click', () => {
        const dir = th.getAttribute('aria-sort') === 'ascending' ? -1 : 1;
        heads.forEach(h => h.removeAttribute('aria-sort'));
        th.setAttribute('aria-sort', dir === 1 ? 'ascending' : 'descending');
        const [kind, key] = keys[i];
        const val = r => i === 0 ? r.cells[0].textContent : r.dataset[key];
        rows.sort((a, c) => dir * (kind === 'num' ? val(a) - val(c) : val(a).localeCompare(val(c)))
          || a.cells[0].textContent.localeCompare(c.cells[0].textContent));
        body.append(...rows);
      });
    });
    form.addEventListener('input', apply);
    form.addEventListener('reset', () => setTimeout(apply));
    apply();
  })();
  </script>
</body>
</html>`;
}

function response(body, status, contentType, head = false, nonce = '') {
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

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    const head = request.method === 'HEAD';
    if (!['GET', 'HEAD'].includes(request.method)) {
      return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
    }
    if (path === '/favicon.ico') return new Response(null, { status: 204 });
    if (!['/', '/api/prices'].includes(path)) return response('Not found', 404, 'text/plain', head);
    try {
      const object = await env.TREASURY_BUCKET.get(DATA_KEY);
      if (!object) {
        return response('Pricing data is unavailable. Load treasury_prices.json into the R2 bucket and refresh.',
          503, 'text/plain; charset=utf-8', head);
      }
      const rows = validatePrices(await object.json());
      return path === '/api/prices'
        ? response(JSON.stringify(rows), 200, 'application/json; charset=utf-8', head)
        : (() => {
            const nonce = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(16))));
            return response(renderPage(rows, nonce), 200, 'text/html; charset=utf-8', head, nonce);
          })();
    } catch (error) {
      console.error('Could not read Treasury prices:', error.message);
      return response('Pricing data could not be loaded. Check the Worker log for details.',
        503, 'text/plain; charset=utf-8', head);
    }
  },
};
