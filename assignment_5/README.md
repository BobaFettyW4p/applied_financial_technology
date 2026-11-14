# Treasury pricing

Displays clean price, accrued interest, and dirty price for 353 Treasury notes
and bonds. Prices are dated November 9, 2026, with settlement November 10.
Amounts are per $100 face value. The Worker reads the calculated prices from R2.

## Start here: run on your computer

Open this `assignment_5` folder in VS Code. Run these commands in its terminal.
You need Python 3.10+ and Node.js 22+.

```bash
npm ci
npm run data:local
npm run dev
```

Open the address printed in the terminal, normally <http://127.0.0.1:8787>.
Keep the terminal running; Ctrl+C stops the server. This uses a local R2
simulation and needs no Cloudflare account. The calculated data is included.
After the first setup, run `npm run dev` to return to this local version.

## Cloudflare R2 setup

**Use the website for account setup, then return to the VS Code terminal.**
Run `npm ci` first if you have just cloned the project.

1. Sign in or create an account at the [Cloudflare dashboard](https://dash.cloudflare.com/).
2. Open **Storage & databases → R2 → Overview** (sometimes labeled
   **R2 Object Storage**). Complete the R2 subscription checkout yourself,
   including any billing information Cloudflare requests. R2 includes free
   monthly usage and bills usage above its allowance.
3. Click **Create bucket**, name it **treasury-pricing-data**, and use
   **Standard** storage. The bucket can stay private.
4. In the VS Code terminal, run:

   ```bash
   npx wrangler login
   ```

   Complete the login and authorization in the browser that opens.
5. Upload the original CSV and calculated JSON to your bucket:

   ```bash
   npm run data:remote
   ```

   In the dashboard, confirm the bucket contains `securityprice.csv` and
   `treasury_prices.json`.
6. Open **Workers & Pages** and look under **Account details → Subdomain**.
   If a `workers.dev` address is already shown, this is set up. Otherwise,
   register an available subdomain there or follow Wrangler's onboarding
   prompt. You do not need to create a separate application in the dashboard
   or buy a domain. The connection to the real bucket requires this account
   setup even when the Worker runs locally. If Wrangler still reports a
   missing subdomain after one appears, retry the command below.
7. Stop any running local server with Ctrl+C, then run:

   ```bash
   npm run dev:cloud
   ```

   Open the printed address. The Worker runs locally but reads your real R2
   bucket. You should see 353 securities and the six required columns.

Once this setup is complete, returning to the cloud-backed page only requires
`npm run dev:cloud`. Login and uploads do not need repeating unless your login
expires or the data changes.

If the page says **"Pricing data could not be loaded"**, check the terminal.
An R2 `get: Unspecified error (0)` can come from the development connection.
Press Ctrl+C, rerun `npm run dev:cloud`, and refresh the page. A connection
restart does not require uploading the files again.

**Wrangler** is Cloudflare's terminal tool; `npm ci` installs it for this
project. `wrangler.jsonc` connects the Worker to the bucket. If you rename
the bucket, change `bucket_name` there too. Keep that file as valid JSON.

The commands select the storage: `dev` and `data:local` use your computer;
`dev:cloud` and `data:remote` use Cloudflare R2. Local uploads do not appear
in your cloud bucket. Registering a subdomain does not deploy this project.

Publishing a URL is optional. Once the real bucket works, run `npm run deploy`.
Wrangler prints the URL. You do not need a custom domain.

Official instructions: [R2 account setup](https://developers.cloudflare.com/r2/get-started/)
and [Workers with R2](https://developers.cloudflare.com/r2/get-started/workers-api/).

## Where the files belong

| Location | Purpose |
| --- | --- |
| `src/index.js` | Worker and webpage |
| `scripts/` | Download reference data, calculate prices, and upload to R2 |
| `data/raw/` | Original FedInvest CSV |
| `data/reference/` | Treasury terms, coupon schedules, and source URLs |
| `data/processed/` | Calculated CSV/JSON and validation report |
| `tests/` | Financial calculations and Worker checks |
| `package.json` / `package-lock.json` | Commands and reproducible dependencies |
| `wrangler.jsonc` | Worker and bucket settings |

## Recalculate and check

```bash
npm run prices
npm test
```

After recalculating, run `npm run data:local` or `npm run data:remote` to
update the bucket the page reads. `/api/prices` returns the JSON from R2.

The calculation uses the end-of-day clean quote and actual coupon dates:
`accrued = half-year coupon × days elapsed / days in coupon period`;
`dirty = clean + accrued`. Actual periods can include 183 days as well as
181, 182, or 184. The CSV has no date field, so its price date is supplied
with the assignment. Tests cover month-end, leap years, and settlement timing.

Terms come from [Fiscal Data](https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/)
and [TreasuryDirect](https://www.treasurydirect.gov/auctions/auction-query/).
Saved reference files let calculations run offline. To refresh them, run
`python3 scripts/fetch_reference_data.py --refresh` before recalculating.
