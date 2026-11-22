"""Fetch Treasury terms and coupon schedules for CUSIPs in the price history.

The Nov 9 reference set in data/reference/ only covers securities outstanding
on that date. Notes and bonds that matured (or were issued) during the history
window are fetched from TreasuryDirect into data/reference/history/, in the same
formats, so the original reference files stay unchanged. Cached entries are
kept; only missing CUSIPs are downloaded. Requires curl.

    python scripts/fetch_history_reference.py
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode

from fetch_reference_data import TREASURY_API, get_json, save_json
from prepare_data import load_prices

ROOT = Path(__file__).resolve().parents[1]
HISTORY_DIR = ROOT / "data" / "raw" / "history"
BASE_REFERENCE = ROOT / "data" / "reference"
HISTORY_REFERENCE = BASE_REFERENCE / "history"


def load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def history_cusips(history_dir: Path):
    cusips = set()
    for path in sorted(history_dir.glob("securityprice_*.csv")):
        prices, _ = load_prices(path)
        cusips.update(p["cusip"] for p in prices)
    return cusips


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--history-dir", type=Path, default=HISTORY_DIR)
    parser.add_argument("--base-reference", type=Path, default=BASE_REFERENCE)
    parser.add_argument("--output", type=Path, default=HISTORY_REFERENCE)
    args = parser.parse_args()

    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    base_terms = ({r["cusip"] for r in load(args.base_reference / "auctions.json", [])}
                  | set(load(args.base_reference / "additional_terms.json", {})))
    base_schedules = set(load(args.base_reference / "coupon_schedules.json", {}))

    terms = load(out / "additional_terms.json", {})
    schedules = load(out / "coupon_schedules.json", {})
    sources = load(out / "sources.json", {})
    if not (out / "auctions.json").exists():
        save_json(out / "auctions.json", [])  # all extra terms come from TreasuryDirect

    def record(name, url):
        sources[name] = {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat()}

    cusips = history_cusips(args.history_dir)
    need_terms = sorted(c for c in cusips if c not in base_terms and c not in terms)
    need_sched = sorted(c for c in cusips if c not in base_schedules and c not in schedules)
    print(f"{len(cusips)} CUSIPs in history; fetching terms for {len(need_terms)}, "
          f"schedules for {len(need_sched)}")
    for cusip in need_terms:
        url = f"{TREASURY_API}/securities/search?" + urlencode({"format": "json", "cusip": cusip})
        rows = get_json(url)
        if not rows:
            raise ValueError(f"TreasuryDirect has no terms for {cusip}")
        terms[cusip] = rows
        record(f"additional_terms_{cusip}", url)
    for cusip in need_sched:
        url = f"{TREASURY_API}/secinterestpayments/{cusip}?format=json"
        rows = get_json(url)
        if not rows:
            raise ValueError(f"TreasuryDirect returned an empty schedule for {cusip}")
        schedules[cusip] = rows
        record(f"schedule_{cusip}", url)
    save_json(out / "additional_terms.json", terms)
    save_json(out / "coupon_schedules.json", schedules)
    save_json(out / "sources.json", sources)
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
