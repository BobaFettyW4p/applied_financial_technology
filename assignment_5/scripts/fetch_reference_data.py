"""Download and cache official Treasury terms and coupon schedules (no API key).

Saved reference files are included in the project. Run this script to download
missing files, or use --refresh to replace them. Requires Python 3.10+ and curl.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import json
from pathlib import Path
import subprocess
from urllib.parse import urlencode

from prepare_data import DEFAULT_INPUT, DEFAULT_PRICE_DATE, load_prices

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "data" / "reference"
FISCAL_API = (
    "https://api.fiscaldata.treasury.gov/services/api/"
    "fiscal_service/v1/accounting/od/auctions_query"
)
TREASURY_API = "https://www.treasurydirect.gov/TA_WS"
FIELDS = (
    "cusip,security_type,security_term,auction_date,issue_date,maturity_date,"
    "dated_date,original_dated_date,original_issue_date,reopening,int_rate,"
    "int_payment_frequency,first_int_payment_date,first_int_period,"
    "floating_rate,inflation_index_security,pdf_filenm_announcemt"
)


def get_json(url: str):
    # Use curl so HTTPS requests use the system certificate store on macOS.
    result = subprocess.run(
        ["curl", "--silent", "--show-error", "--fail", "--location",
         "--globoff", "--retry", "2", "--max-time", "60", url],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def save_json(path: Path, value) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def download(prices_path: Path, price_date, reference_dir: Path, refresh=False):
    prices, _ = load_prices(prices_path)
    reference_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = reference_dir / "sources.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if refresh:
        manifest = {}

    def record_source(name, url):
        manifest[name] = {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat()}
        save_json(manifest_path, manifest)

    terms_path = reference_dir / "auctions.json"
    if refresh or not terms_path.exists():
        all_rows = []
        page = 1
        while True:
            params = {
                "fields": FIELDS,
                "filter": (
                    "security_type:in:(Note,Bond),"
                    f"maturity_date:gt:{price_date.isoformat()},"
                    f"issue_date:lte:{price_date.isoformat()}"
                ),
                "sort": "cusip,issue_date", "page[size]": 10000,
                "page[number]": page,
            }
            url = FISCAL_API + "?" + urlencode(params)
            response = get_json(url)
            all_rows.extend(response["data"])
            record_source(f"auctions_page_{page}", url)
            if page >= response["meta"]["total-pages"]:
                break
            page += 1
        save_json(terms_path, all_rows)
    terms = json.loads(terms_path.read_text())

    # TreasuryDirect can have newly issued securities before Fiscal Data catches up.
    fallback_path = reference_dir / "additional_terms.json"
    fallback = (json.loads(fallback_path.read_text())
                if fallback_path.exists() and not refresh else {})
    covered = {r["cusip"] for r in terms}
    for price in prices:
        cusip = price["cusip"]
        if cusip not in covered and cusip not in fallback:
            url = f"{TREASURY_API}/securities/search?" + urlencode(
                {"format": "json", "cusip": cusip})
            rows = get_json(url)
            if not rows:
                raise ValueError(f"TreasuryDirect has no terms for {cusip}")
            fallback[cusip] = rows
            save_json(fallback_path, fallback)
            record_source(f"additional_terms_{cusip}", url)
    save_json(fallback_path, fallback)

    schedules_path = reference_dir / "coupon_schedules.json"
    schedules = (json.loads(schedules_path.read_text())
                 if schedules_path.exists() and not refresh else {})

    def fetch_schedule(cusip):
        url = f"{TREASURY_API}/secinterestpayments/{cusip}?format=json"
        rows = get_json(url)
        if not rows:
            raise ValueError(f"TreasuryDirect returned an empty schedule for {cusip}")
        return cusip, url, rows

    missing = [p["cusip"] for p in prices if p["cusip"] not in schedules]
    print(f"Downloading {len(missing)} coupon schedules; {len(schedules)} cached.", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch_schedule, cusip) for cusip in missing]
        try:
            for count, future in enumerate(as_completed(futures), 1):
                cusip, url, rows = future.result()
                schedules[cusip] = rows
                record_source(f"schedule_{cusip}", url)
                if count % 25 == 0:
                    save_json(schedules_path, schedules)
                    print(f"Downloaded {count}/{len(missing)} schedules.", flush=True)
        finally:
            save_json(schedules_path, schedules)
    print(f"Saved reference data for {len(prices)} securities to {reference_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--price-date", type=date.fromisoformat,
                        default=DEFAULT_PRICE_DATE)
    parser.add_argument("--reference-dir", type=Path, default=REFERENCE_DIR)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    download(args.input, args.price_date, args.reference_dir, args.refresh)


if __name__ == "__main__":
    main()
