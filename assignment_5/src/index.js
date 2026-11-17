// The Worker reads calculated prices from R2 and builds the table on each visit.
import { browserScript } from './interactions.js';
import { withYield } from './yields.js';

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
            <tr data-cusip="${escapeHtml(row.cusip)}" data-type="${escapeHtml(row.security_type)}" data-coupon="${row.coupon}" data-maturity="${row.maturity}"
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
    [hidden] { display: none !important; }
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
    .visuals { margin: 22px 0 30px; }
    .card { background: #fff; border: 1px solid #dce0d8; border-radius: 10px; padding: 24px; }
    .card h3 { font-size: 17px; margin: 0 0 9px; font-weight: 600; }
    .card p { color: #63716c; font-size: 13px; line-height: 1.65; margin: 0; }
    .timeline-top { display: flex; justify-content: space-between; align-items: start; gap: 20px; }
    .timeline-kicker { color: #527360; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 8px; }
    #selected-cusip { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .fixed-date { background: #edf2eb; color: #42634f; font-size: 12px; padding: 7px 10px; border-radius: 5px; }
    .timeline-track { height: 12px; border-radius: 8px; background: #e8ece6; position: relative; margin: 66px 0 16px; }
    #timeline-fill { height: 100%; background: #3f7957; border-radius: inherit; }
    #settlement-marker { position: absolute; top: -5px; height: 22px; width: 3px; background: #233f31; transform: translateX(-50%); }
    .marker-label { position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%); white-space: nowrap; font-size: 11px; line-height: 1.6; color: #315b40; }
    .timeline-dates { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .timeline-dates > div:last-child { text-align: right; }
    .timeline-dates span { display: block; font-size: 11px; color: #66736c; margin-bottom: 5px; }
    .timeline-dates strong { font-size: 13px; font-weight: 600; }
    .day-counts { display: flex; justify-content: space-between; font-size: 12px; color: #54705d; margin: 18px 0; }
    .calculation { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 32px; border-top: 1px solid #e5e9e1; padding-top: 18px; }
    .calculation dt { margin: 0 0 6px; }
    .calculation dd { font-size: 13px; line-height: 1.7; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
    .chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 18px; }
    .wide { grid-column: 1 / -1; }
    .bar-label { font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; fill: #415148; }
    .chart-point rect { fill: #669479; }
    .chart-point.selected rect, .chart-point:hover rect, .chart-point:focus rect { fill: #246947; stroke: #193a28; stroke-width: 1.5; }
    .yield-bucket { cursor: pointer; outline: none; }
    .yield-bucket:hover circle, .yield-bucket:focus circle { stroke: #142f21; stroke-width: 3; }
    .year-bar { cursor: pointer; outline: none; }
    .year-bar:hover rect, .year-bar:focus rect { stroke: #193a28; stroke-width: 2; }
    .chart-card { min-width: 0; padding: 20px 16px 14px; }
    .chart-card h3, .chart-card > p { margin-left: 6px; margin-right: 6px; }
    .chart { display: block; width: 100%; height: auto; margin-top: 14px; overflow: visible; }
    .chart .axis-tick { font: 11px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #657169; }
    .chart .axis-label { font: 12px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #415148; }
    .grid-line { stroke: #e8ece7; stroke-width: 1; }
    .par-line { stroke: #879889; stroke-width: 1; stroke-dasharray: 4 4; }
    .chart-empty { font-size: 14px; fill: #657169; }
    .chart-point { cursor: pointer; outline: none; }
    .chart-point .dot { opacity: .65; stroke: white; stroke-width: .7; }
    .chart-point:hover .dot, .chart-point:focus .dot, .chart-point.selected .dot { opacity: 1; stroke: #172f23; stroke-width: 2; r: 5.5; }
    .chart-point.selected .price-gap { stroke: #172f23; stroke-width: 3; }
    .legend { display: flex; justify-content: center; flex-wrap: wrap; gap: 10px 16px; font-size: 11px; color: #5f7064; padding: 8px 0; }
    .progress-swatch { width: 85px; height: 9px; border-radius: 4px; background: linear-gradient(to right, hsl(145,32%,82%), hsl(145,32%,30%)); }
    .legend span { display: inline-flex; align-items: center; gap: 5px; }
    .swatch { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
    .clean-swatch, .short-swatch { background: #527ba1; }
    .dirty-swatch { background: #246947; }
    .medium-swatch { background: #287b72; }
    .long-swatch { background: #996149; }
    .chart-tooltip { position: fixed; z-index: 5; pointer-events: none; background: #243b30; color: #fff;
      padding: 12px 15px; border-radius: 7px; font-size: 12px; line-height: 1.8; max-width: min(400px, calc(100vw - 16px));
      box-shadow: 0 4px 16px #172f2326; }
    .chart-tooltip strong { display: block; }
    .security-select { all: unset; cursor: pointer; text-decoration: underline; text-decoration-color: #a9b9ac; text-underline-offset: 3px; }
    .security-select:focus-visible { outline: 3px solid #547c60; outline-offset: 3px; }
    tbody tr { cursor: pointer; }
    tbody tr.selected { background: #eef4e9; }
    tbody tr.selected th { box-shadow: inset 3px 0 #3f7957; }
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
      .card { padding: 18px 14px; }
      .chart-card { padding: 18px 10px 10px; }
      .timeline-top { flex-direction: column; gap: 10px; }
      .timeline-dates { gap: 8px; }
      .timeline-dates strong { font-size: 11px; }
      .calculation { grid-template-columns: 1fr; }
    }
    @media (max-width: 600px) { .wide .chart { min-width: 660px; } .wide { overflow-x: auto; } }
    @media (max-width: 900px) { .chart-grid { grid-template-columns: 1fr; } }
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
      <div class="visuals" id="visuals" hidden>
        <p class="notes">The table filters apply to every chart. Click a security to see its coupon calculation; click a maturity year to filter the table.</p>
        <section class="card" id="timeline-card" aria-labelledby="timeline-title">
          <div class="timeline-top">
            <div>
              <div class="timeline-kicker">Coupon timeline</div>
              <h3 id="timeline-title"><span id="selected-cusip"></span></h3>
              <p id="selected-details"></p>
            </div>
            <span class="fixed-date">Settlement fixed at ${dateLabel(settlement)}</span>
          </div>
          <div id="coupon-timeline" role="img" aria-label="Coupon period">
            <div class="timeline-track"><div id="timeline-fill"></div><div id="settlement-marker"><span class="marker-label">Settlement<br><strong id="settlement-date"></strong></span></div></div>
            <div class="timeline-dates">
              <div><span>Previous coupon / interest start</span><strong id="previous-date"></strong></div>
              <div><span>Next coupon</span><strong id="next-date"></strong></div>
            </div>
          </div>
          <div class="day-counts"><span id="elapsed-days"></span><span id="remaining-days"></span></div>
          <dl class="calculation" aria-live="polite">
            <div><dt>Half-year coupon per $100 face value</dt><dd id="half-coupon"></dd></div>
            <div><dt>Portion of the coupon period elapsed</dt><dd id="period-fraction"></dd></div>
            <div><dt>Accrued interest owed to the seller</dt><dd id="accrued-formula"></dd></div>
            <div><dt>Dirty price = clean price + accrued interest</dt><dd id="dirty-formula"></dd></div>
          </dl>
        </section>
        <div class="chart-grid">
          <section class="card chart-card wide" aria-labelledby="yield-chart-heading">
            <h3 id="yield-chart-heading">Yield to maturity by time remaining</h3>
            <p>YTM is the annualized yield implied by the price and remaining payments through maturity. Each dot is the median for all securities in that maturity bucket; lines span the middle 50%. Click a bucket to filter all views.</p>
            <svg class="chart" id="yield-chart" viewBox="0 0 1060 360" role="group"></svg>
            <p class="notes">Each security counts equally. Counts and medians follow the table filters. Calculated from the November 9 prices for November 10 settlement; this is not the official Treasury yield curve.</p>
          </section>
          <section class="card chart-card" aria-labelledby="coupons-chart-heading">
            <h3 id="coupons-chart-heading">Coupon rate vs. clean price</h3>
            <p>Each dot is one security. Above $100 means it costs more than face value; below means less. Coupon rate is not total return.</p>
            <svg class="chart" id="coupon-chart" viewBox="0 0 560 340" role="group"></svg>
            <div class="legend" aria-label="Years from settlement to maturity"><span><i class="swatch short-swatch"></i>&lt;2 years</span><span><i class="swatch medium-swatch"></i>2–10 years</span><span><i class="swatch long-swatch"></i>&gt;10 years</span></div>
          </section>
          <section class="card chart-card" aria-labelledby="accrual-chart-heading">
            <h3 id="accrual-chart-heading">Coupon rate vs. accrued interest</h3>
            <p>A larger coupon can mean more interest owed, but timing also matters. Darker dots are further through their current coupon period.</p>
            <svg class="chart" id="accrual-chart" viewBox="0 0 560 340" role="group"></svg>
            <div class="legend"><span><i class="progress-swatch"></i>0% → 100% of coupon period elapsed</span></div>
          </section>
          <section class="card chart-card wide" aria-labelledby="maturity-chart-heading">
            <h3 id="maturity-chart-heading">When securities mature</h3>
            <p>Number of notes and bonds maturing each year, not dollars invested. Click a year to filter all views; use Clear above the table to restore the full range.</p>
            <svg class="chart" id="maturity-chart" viewBox="0 0 1060 310" role="group"></svg>
            <div class="legend"><span><i class="swatch short-swatch"></i>Notes</span><span><i class="swatch dirty-swatch"></i>Bonds</span></div>
          </section>
        </div>
      </div>
    </section>
    <footer>
      <span>Sources: FedInvest prices and Treasury security terms.</span>
      <a href="/api/prices" download="treasury_prices.json">Download price data (JSON)</a>
    </footer>
  </main>
  <div id="chart-tooltip" class="chart-tooltip" role="tooltip" hidden></div>
  <script type="application/json" id="price-data" nonce="${nonce}">${JSON.stringify(rows).replace(/</g, '\\u003c')}</script>
  <script nonce="${nonce}">${browserScript}</script>
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
      const rows = validatePrices(await object.json()).map(withYield);
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
