"""Financial boundary checks and an offline end-to-end check of the saved data."""

import csv
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from prepare_data import (
    ROOT, DEFAULT_INPUT, DEFAULT_PRICE_DATE, DEFAULT_SETTLEMENT, accrued_interest,
    coupon_dates, coupon_period, load_prices, parse_date, prepare, select_terms,
)


class TreasuryPricingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = ROOT / "data" / "reference"
        cls.schedules = json.loads((cls.reference / "coupon_schedules.json").read_text())
        cls.auctions = json.loads((cls.reference / "auctions.json").read_text())

    def dates_for(self, cusip):
        return sorted({parse_date(r["interestPaymentDate"])
                       for r in self.schedules[cusip] if r["stripsType"] == "TINT"})

    def test_settlement_date_not_price_date(self):
        # $1 semiannual coupon, 179 of 184 days accrued, five days remaining.
        dates = self.dates_for("912828U24")
        previous, following = coupon_period(dates, DEFAULT_SETTLEMENT, None)
        self.assertEqual((previous, following), (date(2026, 5, 15), date(2026, 11, 15)))
        result = accrued_interest(Decimal(".02"), previous, following, DEFAULT_SETTLEMENT)
        self.assertEqual(result.quantize(Decimal(".00000001")), Decimal(".97282609"))
        prior_day = accrued_interest(Decimal(".02"), previous, following, DEFAULT_PRICE_DATE)
        self.assertAlmostEqual(float(result - prior_day), 1 / 184)

    def test_matches_treasury_published_reopening_accrued_interest(self):
        # Treasury's 2016-12-15 reopening reports $1.65746 accrued per $1,000.
        reopening = next(r for r in self.auctions
                         if r["cusip"] == "912828U24" and r["issue_date"] == "2016-12-15")
        self.assertEqual(reopening["reopening"], "Yes")
        value = accrued_interest(Decimal(".02"), date(2016, 11, 15),
                                 date(2017, 5, 15), date(2016, 12, 15))
        self.assertEqual((value * 10).quantize(Decimal(".00001")), Decimal("1.65746"))

    def test_february_month_end_and_leap_year(self):
        dates = self.dates_for("91282CKC4")
        previous, following = coupon_period(dates, date(2026, 11, 10), None)
        self.assertEqual((previous, following), (date(2026, 8, 31), date(2027, 2, 28)))
        self.assertEqual((following - previous).days, 181)
        previous, following = coupon_period(dates, date(2027, 11, 10), None)
        self.assertEqual(following, date(2028, 2, 29))
        self.assertEqual((following - previous).days, 182)

    def test_february_maturity_still_pays_august_31(self):
        dates = self.dates_for("91282CKC4")
        previous, following = coupon_period(dates, date(2028, 3, 1), None)
        self.assertEqual((previous, following), (date(2028, 2, 29), date(2028, 8, 31)))
        self.assertEqual((following - previous).days, 184)

    def test_coupon_date_resets_accrued_interest(self):
        settlement = date(2026, 8, 31)
        previous, following = coupon_period(self.dates_for("91282CKC4"), settlement, None)
        self.assertEqual(previous, settlement)
        self.assertEqual(accrued_interest(Decimal(".0425"), previous, following, settlement), 0)

    def test_weekend_coupon_dates_are_not_shifted(self):
        # Nov 15, 2026 is Sunday. The contractual coupon date remains Nov 15.
        previous, following = coupon_period(self.dates_for("912828U24"), DEFAULT_SETTLEMENT, None)
        self.assertEqual(following, date(2026, 11, 15))
        self.assertEqual(following.weekday(), 6)

    def test_new_note_uses_dated_date_before_first_coupon(self):
        # This note was issued Nov 2 but starts accruing Oct 31.
        previous, following = coupon_period(self.dates_for("91282CRU7"),
                                            DEFAULT_SETTLEMENT, date(2026, 10, 31))
        self.assertEqual(previous, date(2026, 10, 31))
        self.assertEqual(following, date(2027, 4, 30))
        self.assertEqual((DEFAULT_SETTLEMENT - previous).days, 10)

    def test_183_day_period_is_valid(self):
        previous, following = coupon_period(
            [date(2026, 5, 31), date(2026, 11, 30)], DEFAULT_SETTLEMENT, None)
        self.assertEqual((following - previous).days, 183)

    def test_maturity_and_missing_schedules_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "before maturity"):
            coupon_period(self.dates_for("912828U24"), date(2026, 11, 15), None)
        with self.assertRaisesRegex(ValueError, "missing official"):
            coupon_dates("912828U24", [], {}, date(2026, 11, 15))

    def test_mismatched_treasury_terms_are_rejected(self):
        prices, _ = load_prices(DEFAULT_INPUT)
        price = next(p for p in prices if p["cusip"] == "912828U24")
        candidates = [dict(r) for r in self.auctions if r["cusip"] == price["cusip"]]
        candidates[0]["int_rate"] = "3.000"
        with self.assertRaisesRegex(ValueError, "coupon rate does not match"):
            select_terms(price, candidates, DEFAULT_PRICE_DATE)

    def test_full_dataset(self):
        prices, excluded = load_prices(DEFAULT_INPUT)
        self.assertEqual(len(prices), 353)
        self.assertEqual(sum(excluded.values()), 111)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            results = prepare(DEFAULT_INPUT, self.reference, output,
                              DEFAULT_PRICE_DATE, DEFAULT_SETTLEMENT, "end_of_day")
            self.assertEqual(len(results), 353)
            self.assertEqual(len({r["cusip"] for r in results}), 353)
            self.assertEqual(results, sorted(results, key=lambda r: (r["maturity"], r["cusip"])))
            source_prices = {r["cusip"]: r for r in prices}
            for result in results:
                self.assertEqual(result["clean_price"],
                                 float(source_prices[result["cusip"]]["prices"]["end_of_day"]))
                self.assertGreaterEqual(result["accrued_interest"], 0)
                self.assertLess(result["accrued_interest"], result["coupon_per_half_year"])
                self.assertAlmostEqual(result["dirty_price"],
                                       result["clean_price"] + result["accrued_interest"], places=7)
                self.assertEqual(result["coupon_period_days"],
                                 result["days_accrued"] + result["days_to_next_coupon"])
            with (output / "treasury_prices.csv").open(newline="") as handle:
                exported = list(csv.DictReader(handle))
            self.assertEqual(len(exported), 353)
            self.assertEqual(json.loads((output / "validation_report.json").read_text())["errors"], [])


if __name__ == "__main__":
    unittest.main()
