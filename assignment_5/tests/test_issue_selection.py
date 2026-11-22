"""Checks for the issue-selection analysis on small synthetic panels."""

from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import issue_selection as isel


def bond(rc_bp, years=7.5, dur=650.0, dirty=100.0, cost_buy=0.0, issued=date(2020, 1, 1)):
    return {"rc": rc_bp / 1e4, "dur": dur, "dirty": dirty, "years": years, "in_fit": True,
            "issue_date": issued, "cost_buy": cost_buy, "cost_sell": 0.0}


def day(costs=(0.0, 0.0, 0.0)):
    return {"A": bond(-2.0, cost_buy=costs[0], issued=date(2026, 8, 15)),
            "B": bond(0.5, cost_buy=costs[1]),
            "C": bond(3.0, cost_buy=costs[2])}


class SelectionTests(unittest.TestCase):
    def test_picks_cheapest_and_measures_pickups(self):
        r = isel.selection_day([day()], 0, 7, 8)
        self.assertEqual(r["pick"], "C")
        self.assertAlmostEqual(r["pickup_vs_average_bp"], 3.0 - 0.5)
        self.assertAlmostEqual(r["pickup_vs_richest_bp"], 5.0)
        self.assertAlmostEqual(r["pickup_vs_newest_bp"], 5.0)  # A is the newest issue
        self.assertAlmostEqual(r["pick_discount_usd_per_100mm"], 3e-4 * 650 * 1e6)

    def test_purchase_cost_reduces_net_pickup(self):
        # The pick costs 1/32 more to buy: 1/32 / 650 * 1e4 = 0.48 bp of yield.
        r = isel.selection_day([day(costs=(0.0, 0.0, 1 / 32))], 0, 7, 8)
        self.assertAlmostEqual(r["net_pickup_vs_richest_bp"], 5.0 - (1 / 32) / 650 * 1e4)

    def test_too_few_issues_is_skipped(self):
        panel = [{"A": bond(1.0), "B": bond(2.0)}]
        self.assertIsNone(isel.selection_day(panel, 0, 7, 8))

    def test_persistent_cheapness_has_no_convergence_return(self):
        panel = [day() for _ in range(30)]
        r = isel.realized_day(panel, 0, 7, 8, hold=20)
        self.assertAlmostEqual(r["realized_vs_average_bp"], 0.0)
        self.assertAlmostEqual(r["predicted_vs_average_bp"], 2.5)

    def test_convergence_shows_up_as_realized_return(self):
        panel = [day() for _ in range(30)]
        for t in range(2, 30):
            panel[t]["C"] = bond(0.5)  # the cheap issue converges to its peers after entry
        r = isel.realized_day(panel, 0, 7, 8, hold=20)
        # Gap closes by 2.5 bp * 650 / 100 face, annualized over 20/252 years.
        self.assertAlmostEqual(r["realized_vs_richest_bp"], 2.5e-4 * 650 / 100 * 1e4 / (20 / 252))


if __name__ == "__main__":
    unittest.main()
