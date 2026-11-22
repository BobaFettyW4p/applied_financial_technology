"""Checks for the rich/cheap signal backtest on synthetic panels with known answers."""

from datetime import date
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import signal_backtest as sb


def bond(rc_bp, dur=5.0, cost_buy=0.0, cost_sell=0.0, in_fit=True):
    return {"rc": rc_bp / 1e4, "dur": dur, "in_fit": in_fit, "years": 5.0,
            "cost_buy": cost_buy, "cost_sell": cost_sell}


def reverting_panel(days=30, n=50, phi=0.5):
    """rc_{t+1} = phi * rc_t exactly; bonds spread from -5 to +5 bp on day 0."""
    start = [-5 + 10 * i / (n - 1) for i in range(n)]
    return [{f"B{i}": bond(r * phi ** t) for i, r in enumerate(start)} for t in range(days)]


class CalendarTests(unittest.TestCase):
    def test_settlement_skips_weekends_and_holidays(self):
        self.assertEqual(sb.next_business_day(date(2026, 11, 9)), date(2026, 11, 10))
        self.assertEqual(sb.next_business_day(date(2026, 11, 10)), date(2026, 11, 12))
        self.assertEqual(sb.next_business_day(date(2026, 9, 4)), date(2026, 9, 8))
        self.assertEqual(sb.next_business_day(date(2026, 11, 20)), date(2026, 11, 23))


class TradeTests(unittest.TestCase):
    def test_cheap_bond_converging_earns_its_residual(self):
        gross, net = sb.trade_bp(bond(4.0), bond(0.0), side=+1)
        self.assertAlmostEqual(gross, 4.0)
        self.assertAlmostEqual(net, 4.0)

    def test_rich_short_earns_and_costs_are_charged(self):
        # 1/32 point spread on each side, dollar duration 5 -> 1/32 / 5 * 1e4 bp each.
        c = 1 / 32
        gross, net = sb.trade_bp(bond(-3.0, cost_sell=c), bond(0.0, cost_buy=c), side=-1)
        self.assertAlmostEqual(gross, 3.0)
        self.assertAlmostEqual(net, 3.0 - 2 * c / 5 * 1e4)

    def test_no_convergence_no_gross_pnl(self):
        gross, _ = sb.trade_bp(bond(4.0), bond(4.0), side=+1)
        self.assertAlmostEqual(gross, 0.0)


class SignalTests(unittest.TestCase):
    def test_fama_macbeth_recovers_reversion_and_half_life(self):
        panel = reverting_panel(phi=0.5)
        slopes = sb.fama_macbeth(panel, 1)
        for s in slopes:
            self.assertAlmostEqual(s, -0.5)
        self.assertAlmostEqual(sb.half_life(-0.5), 1.0)
        self.assertAlmostEqual(sb.half_life(-1 + 0.5 ** (1 / 3)), 3.0)
        self.assertIsNone(sb.half_life(0.1))  # diverging: no half-life

    def test_portfolio_trades_extremes_and_profits_from_reversion(self):
        panel = reverting_panel(phi=0.5)
        p = sb.portfolio(panel, 0, 1)
        self.assertEqual(p["positions"], 20)  # 20% of 50 on each side
        self.assertGreater(p["gross"], 0)
        self.assertAlmostEqual(p["long"], p["short"])
        self.assertEqual(p["hit"], 1.0)

    def test_no_signal_means_no_pnl(self):
        panel = reverting_panel(phi=1.0)  # mispricings never close
        p = sb.portfolio(panel, 0, 5)
        self.assertAlmostEqual(p["gross"], 0.0)

    def test_portfolio_skips_bonds_missing_at_exit_and_out_of_fit(self):
        panel = reverting_panel(days=3, n=10)
        del panel[1]["B9"]
        panel[0]["B0"]["in_fit"] = False
        names = sb.candidates(panel, 0, (0, 1))
        self.assertNotIn("B9", names)
        self.assertNotIn("B0", names)
        self.assertIsNone(sb.portfolio(panel, 1, 5))  # exit beyond the panel

    def test_convergence_profile_decays(self):
        prof = sb.convergence_profile(reverting_panel(days=30, phi=0.8), days=5)
        cheap = prof["cheap_decile_bp"]
        self.assertTrue(all(a > b > 0 for a, b in zip(cheap, cheap[1:])))
        self.assertAlmostEqual(cheap[1] / cheap[0], 0.8, places=6)

    def test_newey_west_t_of_constant_positive_series_is_large(self):
        m, t = sb.nw_mean_t([1.0 + 0.01 * math.sin(i) for i in range(40)], 5)
        self.assertAlmostEqual(m, 1.0, places=2)
        self.assertGreater(t, 10)


if __name__ == "__main__":
    unittest.main()
