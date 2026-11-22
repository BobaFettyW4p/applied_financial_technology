"""Checks for the NSS rich/cheap refit: curve recovery and leave-one-out scoring."""

import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import rich_cheap as rc

TRUE = (0.050, -0.010, 0.005, 0.010, 2.0, 10.0)


def synthetic_bond(years, coupon, bump_bp=0.0):
    """Bond priced off the TRUE curve, optionally shifted by bump_bp of yield."""
    flows = []
    t = years
    while t > 1e-9:
        flows.append((t, coupon / 2 + (100 if t == years else 0)))
        t -= 0.5
    flows.reverse()
    shift = bump_bp / 1e4
    price = sum(cf * math.exp(-(rc.zero_rate(t, TRUE) + shift) * t) for t, cf in flows)
    yc = rc.zero_rate(years, TRUE)
    dur = sum(cf * t * math.exp(-yc * t) for t, cf in flows)
    return {"cusip": f"{years}-{coupon}", "years": years, "flows": flows, "dirty": price,
            "dur": dur, "ytm": 200 * (math.exp(yc / 2) - 1)}


class RichCheapTests(unittest.TestCase):
    def setUp(self):
        self.bonds = [synthetic_bond(y, c) for y in (1, 2, 3, 5, 7, 10, 15, 20, 25, 30)
                      for c in (2.0, 5.0)]

    def test_recovers_known_curve(self):
        params, sse = rc.fit_curve(self.bonds, taus=TRUE[4:])
        self.assertLess(math.sqrt(sse / len(self.bonds)) * 1e4, 0.01)
        for t in (1, 5, 10, 30):
            self.assertAlmostEqual(rc.zero_rate(t, params), rc.zero_rate(t, TRUE), places=6)

    def test_cheap_bond_scores_positive_and_loo_matches_refit(self):
        cheap = synthetic_bond(12, 4.0, bump_bp=5.0)  # yield 5 bp above the curve
        bonds = self.bonds + [cheap]
        params, _ = rc.fit_curve(bonds, taus=TRUE[4:])
        rc.score(bonds, bonds, params)
        self.assertAlmostEqual(cheap["resid"] * 1e4, 5.0, delta=0.3)
        self.assertGreater(abs(cheap["resid"]), abs(cheap["resid_in"]))

        rest = bonds[:-1]
        betas, _ = rc.fit_betas(rest, rc.precompute(rest, *TRUE[4:]), list(params[:4]))
        brute, _ = rc.residuals_and_jacobian([cheap], rc.precompute([cheap], *TRUE[4:]), betas)
        self.assertAlmostEqual(cheap["resid"], brute[0], delta=1e-6)

    def test_term_labels(self):
        self.assertEqual(rc.term_years("10-Year"), 10)
        self.assertEqual(rc.term_years("29-Year 9-Month"), 30)
        self.assertEqual(rc.term_years("30-Year 3-Month"), 30)


if __name__ == "__main__":
    unittest.main()
