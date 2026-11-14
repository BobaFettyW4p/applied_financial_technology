// Copy the source CSV and calculated prices to the selected R2 bucket.
// --local writes only to this computer. --remote writes to Cloudflare.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const mode = process.argv[2];
if (process.argv.length !== 3 || !['--local', '--remote'].includes(mode)) {
  throw new Error('Choose --local or --remote. Example: npm run data:local');
}
const config = JSON.parse(readFileSync(resolve(root, 'wrangler.jsonc'), 'utf8'));
const bucket = config.r2_buckets[0].bucket_name;
const report = JSON.parse(readFileSync(resolve(root, 'data/processed/validation_report.json'), 'utf8'));
const source = readFileSync(resolve(root, 'data/raw/securityprice.csv'));
const prices = JSON.parse(readFileSync(resolve(root, 'data/processed/treasury_prices.json'), 'utf8'));
if (report.errors.length || report.priced_count !== report.eligible_count ||
    prices.length !== report.priced_count ||
    createHash('sha256').update(source).digest('hex') !== report.input_sha256) {
  throw new Error('The price files need to be rebuilt. Run npm run prices and npm test first.');
}

const files = [
  ['securityprice.csv', 'data/raw/securityprice.csv', 'text/csv'],
  ['treasury_prices.json', 'data/processed/treasury_prices.json', 'application/json'],
];
const wrangler = resolve(root, 'node_modules/wrangler/bin/wrangler.js');
for (const [key, file, contentType] of files) {
  const args = [wrangler, 'r2', 'object', 'put', `${bucket}/${key}`,
    '--file', resolve(root, file), '--content-type', contentType, mode];
  if (mode === '--local') args.push('--persist-to', resolve(root, '.wrangler/state'));
  console.log(`Uploading ${key} to ${mode === '--local' ? 'local R2' : 'Cloudflare R2'} (${bucket})`);
  const result = spawnSync(process.execPath, args, { cwd: root, stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
