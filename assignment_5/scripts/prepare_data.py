"""Join FedInvest prices to Treasury terms and calculate accrued/dirty prices.

Runs offline after fetch_reference_data.py. All prices are per $100 face value.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
import calendar
from collections import Counter, defaultdict
import csv
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "securityprice.csv"
DEFAULT_PRICE_DATE = date(2026, 11, 9)
DEFAULT_SETTLEMENT = date(2026, 11, 10)
ELIGIBLE_TYPES = {"MARKET BASED NOTE": "Note", "MARKET BASED BOND": "Bond"}
PRICE_COLUMNS = {"buy": 5, "sell": 6, "end_of_day": 7}
MONEY_PRECISION = Decimal("0.00000001")


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def load_prices(path: Path):
    """Read the headerless 8-column FedInvest format, keeping the original file intact."""
    prices, excluded, seen = [], Counter(), set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for number, row in enumerate(csv.reader(handle), 1):
            if not row:
                continue
            if len(row) != 8:
                raise ValueError(f"Line {number}: expected 8 columns, found {len(row)}")
            cusip, security_type, coupon, maturity, call_date, *_ = row
            if security_type not in ELIGIBLE_TYPES:
                excluded[security_type] += 1
                continue
            if cusip in seen:
                raise ValueError(f"Duplicate CUSIP in prices: {cusip}")
            if call_date.strip():
                raise ValueError(f"{cusip}: callable security requires additional review")
            seen.add(cusip)
            month, day, year = map(int, maturity.split("/"))
            rate = Decimal(coupon)
            if not rate.is_finite() or not 0 < rate < 1:
                raise ValueError(f"{cusip}: invalid decimal coupon rate {coupon}")
            prices.append({
                "cusip": cusip, "security_type": ELIGIBLE_TYPES[security_type],
                "coupon_rate": rate, "maturity": date(year, month, day),
                "prices": {name: Decimal(row[index])
                           for name, index in PRICE_COLUMNS.items()},
            })
    if not prices:
        raise ValueError("No eligible notes or bonds in the price file")
    return prices, dict(excluded)


def optional_date(value):
    return parse_date(value) if value and value != "null" else None


def normalize_direct(row):
    """Rename TreasuryDirect fields to match the Fiscal Data field names."""
    mapping = {
        "cusip": "cusip", "security_type": "securityType",
        "issue_date": "issueDate", "maturity_date": "maturityDate",
        "dated_date": "datedDate", "original_dated_date": "originalDatedDate",
        "original_issue_date": "originalIssueDate", "reopening": "reopening",
        "int_rate": "interestRate", "int_payment_frequency": "frequencyOfInterestPayments",
        "floating_rate": "floatingRate", "inflation_index_security": "inflationProtected",
    }
    return {target: row.get(source, "") for target, source in mapping.items()}


def select_terms(price, candidates, price_date):
    cusip = price["cusip"]
    candidates = [r for r in candidates
                  if optional_date(r.get("issue_date"))
                  and parse_date(r["issue_date"]) <= price_date]
    if not candidates:
        raise ValueError(f"{cusip}: missing Treasury terms issued by {price_date}")
    for row in candidates:
        if row["security_type"] != price["security_type"]:
            raise ValueError(f"{cusip}: security type does not match Treasury")
        if parse_date(row["maturity_date"]) != price["maturity"]:
            raise ValueError(f"{cusip}: maturity does not match Treasury")
        if Decimal(row["int_rate"]) != price["coupon_rate"] * 100:
            raise ValueError(f"{cusip}: coupon rate does not match Treasury")
        if row["int_payment_frequency"] != "Semi-Annual":
            raise ValueError(f"{cusip}: expected semiannual interest")
        if row.get("floating_rate") != "No" or row.get("inflation_index_security") != "No":
            raise ValueError(f"{cusip}: expected a fixed-rate, nominal Treasury")
    # Reopenings retain the original security's interest schedule. Prefer the
    # original auction rather than treating a reopening as a new bond.
    return min(candidates, key=lambda r: (
        r.get("reopening") != "No", parse_date(r["issue_date"])))


def coupon_dates(cusip, rows, terms, maturity):
    if not rows:
        raise ValueError(f"{cusip}: missing official coupon schedule")
    if any(r["cusip"] != cusip for r in rows):
        raise ValueError(f"{cusip}: coupon schedule contains another CUSIP")
    dates = sorted({parse_date(r["interestPaymentDate"]) for r in rows
                    if r.get("stripsType") == "TINT"})
    if not dates or dates[-1] != maturity:
        raise ValueError(f"{cusip}: coupon schedule does not end at maturity")
    first_payment = optional_date(terms.get("first_int_payment_date"))
    if first_payment and dates[0] != first_payment:
        raise ValueError(f"{cusip}: first coupon conflicts with Treasury terms")
    # Each scheduled coupon is either a fixed day of the month or month-end.
    month_end = all(d.day == calendar.monthrange(d.year, d.month)[1] for d in dates)
    fixed_day = len({d.day for d in dates}) == 1
    if not month_end and not fixed_day:
        raise ValueError(f"{cusip}: irregular coupon dates require review")
    for earlier, later in zip(dates, dates[1:]):
        if (later.year - earlier.year) * 12 + later.month - earlier.month != 6:
            raise ValueError(f"{cusip}: coupon schedule has a gap")
    return dates


def coupon_period(dates, settlement, accrual_start):
    """Find the coupon dates on either side of settlement.

    Before the first payment, use Treasury's dated date (the interest start),
    which can differ from the actual issue date when issuance is on a weekend.
    """
    index = bisect_right(dates, settlement)
    if index == len(dates):
        raise ValueError("Settlement must be before maturity")
    previous = dates[index - 1] if index else accrual_start
    following = dates[index]
    if previous is None or not previous <= settlement < following:
        raise ValueError("Settlement is outside the security's accrual period")
    # This formula assumes a full six-month coupon period. Short or long
    # first periods need a different calculation.
    if not 181 <= (following - previous).days <= 184:
        raise ValueError("Irregular coupon period requires separate treatment")
    return previous, following


def accrued_interest(coupon_rate, previous, following, settlement):
    period_days = (following - previous).days
    remaining_days = (following - settlement).days
    if period_days <= 0 or not 0 < remaining_days <= period_days:
        raise ValueError("Invalid coupon-period dates")
    coupon_per_half_year = coupon_rate * Decimal(100) / 2
    return coupon_per_half_year * Decimal(period_days - remaining_days) / Decimal(period_days)


def numeric(value: Decimal):
    # Keep eight decimals in exports; calculate dirty price before rounding.
    return float(value.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP))


def prepare(input_path, reference_dir, output_dir, price_date, settlement, clean_column):
    if settlement <= price_date:
        raise ValueError("Settlement must be after the price date")
    prices, excluded = load_prices(input_path)
    grouped = defaultdict(list)
    for row in json.loads((reference_dir / "auctions.json").read_text()):
        grouped[row["cusip"]].append(row)
    additional_terms = json.loads((reference_dir / "additional_terms.json").read_text())
    for cusip, rows in additional_terms.items():
        grouped[cusip].extend(normalize_direct(r) for r in rows)
    schedules = json.loads((reference_dir / "coupon_schedules.json").read_text())
    results, references, errors = [], [], []
    for price in prices:
        cusip = price["cusip"]
        try:
            terms = select_terms(price, grouped[cusip], price_date)
            dates = coupon_dates(cusip, schedules.get(cusip), terms, price["maturity"])
            start = (optional_date(terms.get("original_dated_date"))
                     or optional_date(terms.get("dated_date")))
            previous, following = coupon_period(dates, settlement, start)
            clean = price["prices"][clean_column]
            if not clean.is_finite() or clean <= 0:
                raise ValueError(f"Missing/invalid {clean_column} price; choose another column explicitly")
            accrued = accrued_interest(price["coupon_rate"], previous, following, settlement)
            results.append({
                "cusip": cusip, "security_type": price["security_type"],
                "coupon": float(price["coupon_rate"] * 100),
                "maturity": price["maturity"].isoformat(),
                "clean_price": numeric(clean), "accrued_interest": numeric(accrued),
                "dirty_price": numeric(clean + accrued),
                "price_date": price_date.isoformat(), "settlement_date": settlement.isoformat(),
                "clean_price_column": clean_column,
                "previous_coupon_date": previous.isoformat(),
                "next_coupon_date": following.isoformat(),
                "coupon_period_days": (following - previous).days,
                "days_accrued": (settlement - previous).days,
                "days_to_next_coupon": (following - settlement).days,
                "coupon_per_half_year": numeric(price["coupon_rate"] * 50),
            })
            references.append({
                "cusip": cusip, "security_type": price["security_type"],
                "coupon": float(price["coupon_rate"] * 100),
                "maturity": price["maturity"].isoformat(),
                "dated_date": start.isoformat(),
                "interest_payment_frequency": terms["int_payment_frequency"],
                "first_coupon_date": dates[0].isoformat(),
                "coupon_dates": [d.isoformat() for d in dates],
                "terms_source": (
                    "TreasuryDirect" if cusip in additional_terms else "Fiscal Data"
                ),
                "terms_lookup_url": (
                    "https://www.treasurydirect.gov/auctions/auction-query/?cusip=" + cusip),
                "schedule_source_url": (
                    "https://www.treasurydirect.gov/TA_WS/secinterestpayments/"
                    + cusip + "?format=json"),
            })
        except (ValueError, KeyError, ArithmeticError) as exc:
            errors.append({"cusip": cusip, "error": str(exc)})
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "price_date": price_date.isoformat(), "settlement_date": settlement.isoformat(),
        "price_date_verification": "User-supplied date; FedInvest CSV has no date field",
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "eligible_count": len(prices), "priced_count": len(results),
        "excluded_by_type": excluded, "clean_price_column": clean_column,
        "errors": errors,
    }
    (output_dir / "validation_report.json").write_text(json.dumps(report, indent=2) + "\n")
    if errors:
        details = "\n".join(f"{r['cusip']}: {r['error']}" for r in errors)
        raise ValueError(f"Refusing to export incomplete results:\n{details}")
    results.sort(key=lambda r: (r["maturity"], r["cusip"]))
    references.sort(key=lambda r: (r["maturity"], r["cusip"]))
    for name, values in [("treasury_prices", results), ("treasury_reference", references)]:
        (output_dir / f"{name}.json").write_text(json.dumps(values, indent=2) + "\n")
    with (output_dir / "treasury_prices.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"Priced {len(results)} securities; excluded {sum(excluded.values())} bills/TIPS/FRNs.")
    print(f"Settlement: {settlement}; clean price column: {clean_column}.")
    print(f"Outputs: {output_dir}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--reference-dir", type=Path, default=ROOT / "data" / "reference")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "processed")
    parser.add_argument("--price-date", type=date.fromisoformat, default=DEFAULT_PRICE_DATE)
    parser.add_argument("--settlement", type=date.fromisoformat, default=DEFAULT_SETTLEMENT)
    parser.add_argument("--clean-column", choices=PRICE_COLUMNS, default="end_of_day")
    args = parser.parse_args()
    prepare(args.input, args.reference_dir, args.output_dir, args.price_date,
            args.settlement, args.clean_column)


if __name__ == "__main__":
    main()
