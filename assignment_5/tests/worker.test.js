import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { Script } from 'node:vm';
import worker from '../src/index.js';
import { browserScript } from '../src/interactions.js';
import { dirtyPriceAtYield, yieldToMaturity, maturityBucket, withYield } from '../src/yields.js';

const prices = JSON.parse(readFileSync(new URL('../data/processed/treasury_prices.json', import.meta.url)));
function bucketWith(rows) {
  return { TREASURY_BUCKET: { async get(key) {
    assert.equal(key, 'treasury_prices.json');
    return rows === null ? null : { async json() { return rows; } };
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
