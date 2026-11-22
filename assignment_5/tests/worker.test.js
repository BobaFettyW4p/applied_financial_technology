import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { Script } from 'node:vm';
import worker from '../src/index.js';
import { browserScript } from '../src/interactions.js';
import { dirtyPriceAtYield, yieldToMaturity, maturityBucket, withYield } from '../src/yields.js';

const prices = JSON.parse(readFileSync(new URL('../data/processed/treasury_prices.json', import.meta.url)));
const curve = JSON.parse(readFileSync(new URL('../data/processed/curve_page.json', import.meta.url)));
// A fake R2 bucket. `rows` is the price data; `curveDoc` the curve page data (null = missing).
function bucketWith(rows, curveDoc = curve) {
  const objects = { 'treasury_prices.json': rows, 'curve_page.json': curveDoc };
  return { TREASURY_BUCKET: { async get(key) {
    assert.ok(key in objects, `unexpected key ${key}`);
    const value = objects[key];
    return value === null ? null : { async json() { return value; } };
  } } };
}


test('page renders all securities in maturity order from the R2 response', async () => {
  const response = await worker.fetch(new Request('https://example.com/'), bucketWith([...prices].reverse()));
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.equal((html.match(/<th scope="row">/g) || []).length, 353);
  const cusips = [...html.matchAll(/<th scope="row">(.*?)<\/th>/g)].map(match => match[1]);
  assert.deepEqual(cusips, prices.map(row => row.cusip));
  for (const heading of ['CUSIP', 'Coupon', 'Maturity', 'Clean price', 'Accrued interest', 'Dirty price']) {
    assert.ok(html.includes(`>${heading}</th>`));
  }
  assert.ok(html.includes('Nov 10, 2026'));
  assert.ok(html.includes('100.941576'));
});

test('JSON route returns the prices read from R2', async () => {
  const response = await worker.fetch(new Request('https://example.com/api/prices'), bucketWith(prices));
  assert.equal(response.status, 200);
  assert.match(response.headers.get('content-type'), /application\/json/);
  assert.deepEqual(await response.json(), prices.map(withYield));
});

test('interactive views use the same R2 snapshot and an allowed browser script', async () => {
  const response = await worker.fetch(new Request('https://example.com/'), bucketWith(prices));
  const html = await response.text();
  const data = html.match(/<script type="application\/json" id="price-data" nonce="([^"]+)">([\s\S]*?)<\/script>/);
  assert.ok(data);
  assert.deepEqual(JSON.parse(data[2]), prices.map(withYield));
  assert.ok(response.headers.get('content-security-policy').includes("'nonce-" + data[1] + "'"));
  assert.ok(html.includes('<script nonce="' + data[1] + '">' + browserScript + '</script>'));
  assert.doesNotThrow(() => new Script(browserScript));
  assert.ok(html.indexOf('<table>') < html.indexOf('id="visuals"'));
  assert.ok(!html.includes('id="price-chart"'));
  for (const id of ['timeline-card', 'yield-chart', 'coupon-chart', 'accrual-chart', 'maturity-chart']) {
    assert.ok(html.includes('id="' + id + '"'));
  }
});

test('missing and invalid data return an error instead of an empty price table', async () => {
  const missing = await worker.fetch(new Request('https://example.com/'), bucketWith(null));
  assert.equal(missing.status, 503);
  const badData = await worker.fetch(new Request('https://example.com/'), bucketWith([]));
  assert.equal(badData.status, 503);
});

test('unknown routes and write requests are rejected', async () => {
  const env = bucketWith(prices);
  const missing = await worker.fetch(new Request('https://example.com/missing'), env);
  assert.equal(missing.status, 404);
  const post = await worker.fetch(new Request('https://example.com/', { method: 'POST' }), env);
  assert.equal(post.status, 405);
  assert.equal(post.headers.get('allow'), 'GET, HEAD');
});

test('HEAD requests return headers without a page body', async () => {
  const response = await worker.fetch(new Request('https://example.com/', { method: 'HEAD' }), bucketWith(prices));
  assert.equal(response.status, 200);
  assert.equal(await response.text(), '');
});

test('YTM matches the published Treasury reopening example', () => {
  // Appendix B II.D: 9.5% coupon, clean 99.730918, dirty 100.098321,
  // 167/181 of a period to next payment and 19 full periods after it.
  const row = { cusip: 'Treasury example', coupon: 9.5, dirty_price: 100.098321,
    next_coupon_date: '1986-05-15', maturity: '1995-11-15',
    days_to_next_coupon: 167, coupon_period_days: 181 };
  assert.ok(Math.abs(yieldToMaturity(row) - 9.54) < .000001);
  assert.ok(Math.abs(dirtyPriceAtYield(row, 9.54) - 100.098321) < .000001);
});

test('YTM handles par, zero yield, and the final coupon period', () => {
  const par = { cusip: 'Par example', coupon: 4, dirty_price: 100,
    next_coupon_date: '2027-05-15', maturity: '2036-05-15',
    days_to_next_coupon: 181, coupon_period_days: 181 };
  assert.ok(Math.abs(yieldToMaturity(par) - 4) < 1e-10);
  const zero = { ...par, dirty_price: 138 };
  assert.ok(Math.abs(yieldToMaturity(zero)) < 1e-10);
  const final = prices.find(row => row.cusip === '912828U24');
  const expected = ((100 + final.coupon / 2) / final.dirty_price - 1) *
    200 * final.coupon_period_days / final.days_to_next_coupon;
  assert.ok(Math.abs(yieldToMaturity(final) - expected) < 1e-9);
  const negative = { ...par, maturity: par.next_coupon_date, dirty_price: 106 };
  assert.ok(yieldToMaturity(negative) < 0);
});

test('every calculated yield reproduces its source dirty price', () => {
  for (const row of prices) {
    const calculated = yieldToMaturity(row);
    assert.ok(Number.isFinite(calculated));
    assert.ok(Math.abs(dirtyPriceAtYield(row, calculated) - row.dirty_price) < 1e-9, row.cusip);
  }
});

test('maturity buckets use calendar anniversaries with no overlapping boundaries', () => {
  const base = { settlement_date: '2026-11-10' };
  for (const [maturity, bucket] of [
    ['2027-11-09', 0], ['2027-11-10', 1], ['2029-11-09', 1],
    ['2029-11-10', 2], ['2031-11-10', 3], ['2036-11-10', 4], ['2046-11-10', 5],
  ]) assert.equal(maturityBucket({ ...base, maturity }), bucket);
});

test('prices page links to the curve page', async () => {
  const html = await (await worker.fetch(new Request('https://example.com/'), bucketWith(prices))).text();
  assert.ok(html.includes('href="/curve"'));
  assert.ok(html.includes('aria-current="page">Prices'));
});

test('curve page renders every security, the scorecard and the answers', async () => {
  const response = await worker.fetch(new Request('https://example.com/curve'), bucketWith(prices));
  assert.equal(response.status, 200);
  assert.match(response.headers.get('content-type'), /text\/html/);
  const html = await response.text();
  const tbody = html.slice(html.indexOf('id="bond-table"'));
  assert.equal((tbody.match(/<tr data-years=/g) || []).length, curve.bonds.length);
  for (const m of curve.models) assert.ok(html.includes(m.label.replace(/&/g, '&amp;')), m.label);
  for (const q of ['Which curve?', 'How is rich/cheap measured?', 'Is it really cheap?', "What's the edge?"]) {
    assert.ok(html.includes(q.replace("'", '&#39;')) || html.includes(q), q);
  }
  // The script carries the CSP nonce, and the JSON island cannot break out of its script tag.
  const nonce = response.headers.get('content-security-policy').match(/'nonce-([^']+)'/)[1];
  assert.ok(html.includes(`<script nonce="${nonce}">`));
  const island = html.match(/<script type="application\/json" id="curve-data">([\s\S]*?)<\/script>/)[1];
  assert.ok(!island.includes('<'));
  assert.equal(JSON.parse(island).bonds.length, curve.bonds.length);
});

test('cheapest security is listed first with its selected-model score', async () => {
  const html = await (await worker.fetch(new Request('https://example.com/curve'), bucketWith(prices))).text();
  const best = [...curve.bonds].sort((a, b) => b.rc[curve.selected] - a.rc[curve.selected])[0];
  const first = html.slice(html.indexOf('id="bond-table"')).match(/<th scope="row">(.*?)<\/th>/)[1];
  assert.equal(first, best.cusip);
});

test('curve JSON route returns the curve data read from R2', async () => {
  const response = await worker.fetch(new Request('https://example.com/api/curve'), bucketWith(prices));
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), JSON.parse(JSON.stringify(curve)));  // -0 becomes 0
});

test('missing or malformed curve data returns 503, prices page unaffected', async () => {
  const missing = await worker.fetch(new Request('https://example.com/curve'), bucketWith(prices, null));
  assert.equal(missing.status, 503);
  const broken = structuredClone(curve);
  broken.bonds[0].rc[curve.selected] = 'cheap';
  const bad = await worker.fetch(new Request('https://example.com/curve'), bucketWith(prices, broken));
  assert.equal(bad.status, 503);
  const dup = structuredClone(curve);
  dup.bonds[1].cusip = dup.bonds[0].cusip;
  assert.equal((await worker.fetch(new Request('https://example.com/api/curve'), bucketWith(prices, dup))).status, 503);
  const prices200 = await worker.fetch(new Request('https://example.com/'), bucketWith(prices, null));
  assert.equal(prices200.status, 200);
});

test('curve labels are escaped in the page', async () => {
  const hostile = structuredClone(curve);
  hostile.models[0].label = '<img src=x onerror=alert(1)>';
  const html = await (await worker.fetch(new Request('https://example.com/curve'), bucketWith(prices, hostile))).text();
  assert.ok(!html.includes('<img src=x'));
  assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;'));
});

test('robustness section renders when present and is omitted when absent', async () => {
  const html = await (await worker.fetch(new Request('https://example.com/curve'), bucketWith(prices))).text();
  assert.equal(html.includes('id="robust-title"'), Boolean(curve.robustness));
  const without = structuredClone(curve);
  delete without.robustness;
  const html2 = await (await worker.fetch(new Request('https://example.com/curve'), bucketWith(prices, without))).text();
  assert.ok(!html2.includes('id="robust-title"'));
  const bad = structuredClone(curve);
  bad.robustness = { watch: ['x'], penalty_sweep: [] };
  assert.equal((await worker.fetch(new Request('https://example.com/curve'), bucketWith(prices, bad))).status, 503);
});
