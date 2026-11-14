import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import worker from '../src/index.js';

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
  assert.deepEqual(await response.json(), prices);
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
