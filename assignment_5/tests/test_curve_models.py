"""Checks for the curve-model comparison: spline maths, curve recovery, LOO, diagnostics."""

import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))

import curve_models as cm
import rich_cheap as rc
from test_rich_cheap import TRUE, synthetic_bond

KNOTS = [0.0] * 4 + [1, 2, 3.5, 5, 7, 10, 15, 20, 25] + [30.5] * 4


def synthetic_set(bumps=None):
    bonds = [synthetic_bond(y, c) for y in (1, 1.5, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 18, 20,
                                             22, 25, 27, 30) for c in (1.5, 4.0, 6.0)]
    for b in bonds:
        b["years"] = max(t for t, _ in b["flows"])
    return bonds


class BSplineTests(unittest.TestCase):
    def test_partition_of_unity(self):
        for t in (0.0, 0.3, 1.0, 4.2, 19.99, 30.5):
            self.assertAlmostEqual(sum(cm.bspline_values(KNOTS, 3, t)), 1.0, places=12)

    def test_integral_matches_numerical(self):
        model = cm.Spline("s", "s", KNOTS[4:-4], 30.5)
        for t in (0.4, 2.0, 9.3, 30.0):
            n = 4000
            h = t / n
            numeric = [0.0] * model.k
            for i in range(n):  # midpoint rule
                v = cm.bspline_values(KNOTS, 3, (i + 0.5) * h)
                numeric = [a + b * h for a, b in zip(numeric, v)]
            for a, b in zip(model.g(t), numeric):
                self.assertAlmostEqual(a, b, delta=2e-5)  # midpoint-rule error

    def test_second_derivative_matches_finite_difference(self):
        h = 1e-4
        for t in (0.7, 4.4, 12.1):
            exact = cm.bspline_derivs(KNOTS, 3, t, 2)
            lo, mid, hi = (cm.bspline_values(KNOTS, 3, t + d) for d in (-h, 0, h))
            for e, a, b, c in zip(exact, lo, mid, hi):
                self.assertAlmostEqual(e, (a - 2 * b + c) / (h * h), places=3)

    def test_penalty_ignores_linear_forward_curve(self):
        model = cm.Spline("s", "s", KNOTS[4:-4], 30.5, weight=cm.vrp_weight)
        # Greville abscissae reproduce f(t) = a + b t exactly, so f'' = 0.
        greville = [sum(KNOTS[k + 1:k + 4]) / 3 for k in range(model.k)]
        beta = [0.04 + 0.001 * g for g in greville]
        self.assertAlmostEqual(cm.quad_form(model.omega, beta), 0.0, places=12)
        bent = beta[:]
        bent[6] += 0.002
        self.assertGreater(cm.quad_form(model.omega, bent), 0.0)


class FitTests(unittest.TestCase):
    def test_generic_nss_matches_rich_cheap(self):
        bonds = synthetic_set()
        bonds[10]["dirty"] -= 0.2  # make the fit non-trivial
        model = cm.NelsonSiegel("nss", "nss", svensson=True)
        beta, res, _ = model.fit(bonds, TRUE[4:])
        params, sse = rc.fit_curve(bonds, taus=TRUE[4:])
        self.assertAlmostEqual(sum(r * r for r in res), sse, delta=1e-12)
        for a, b in zip(beta, params[:4]):
            self.assertAlmostEqual(a, b, places=7)

    def test_spline_recovers_smooth_curve(self):
        bonds = synthetic_set()
        model = cm.Spline("s", "s", KNOTS[4:-4], 30.5, weight=cm.constant_weight)
        beta, res, _ = model.fit(bonds, 1e-8)
        self.assertLess(cm.rmse_bp(res), 0.05)
        for t in (1, 5, 10, 20, 30):
            self.assertAlmostEqual(cm.zero_rate(model, None, beta, t), rc.zero_rate(t, TRUE),
                                   delta=2e-6)  # 0.02 bp

    def test_penalized_loo_matches_refit(self):
        bonds = synthetic_set()
        cheap = synthetic_bond(9, 3.0, bump_bp=4.0)
        cheap["years"] = 9
        bonds.append(cheap)
        model = cm.Spline("s", "s", KNOTS[4:-4], 30.5, weight=cm.constant_weight)
        lam = 1e-4
        beta, res, jac = model.fit(bonds, lam)
        loo = cm.loo_residuals(res, cm.hat_diag(jac, model.penalty(lam)))
        refit, _, _ = model.fit(bonds[:-1], lam, beta)
        brute = cm.residuals(model, None, refit, [cheap])[0]
        self.assertAlmostEqual(loo[-1] * 1e4, brute * 1e4, delta=0.05)
        self.assertAlmostEqual(loo[-1] * 1e4, 4.0, delta=0.5)

    def test_lambda_selection_returns_grid_value(self):
        bonds = synthetic_set()
        for i, b in enumerate(bonds):  # deterministic +-1 bp noise
            b["dirty"] += (1 if i % 3 else -1) * 1e-4 * b["dur"]
        model = cm.Spline("s", "s", KNOTS[4:-4], 30.5, weight=cm.constant_weight)
        lam, beta, sweep = model.select(bonds)
        self.assertIn(lam, cm.LAMBDA_GRID)
        self.assertEqual(len(sweep), len(cm.LAMBDA_GRID))
        best = min(sweep, key=lambda s: s["blocked_cv_rmse_bp"])
        self.assertEqual(best["lambda"], lam)

    def test_liquidity_feature_recovers_known_spread(self):
        # Every third bond trades 3 bp cheap; flagging them via a feature should
        # recover gamma = 3 bp and leave those bonds' scores near zero.
        bonds = synthetic_set()
        flagged = set(range(0, len(bonds), 3))
        cheap = [synthetic_bond(b["years"], b["flows"][0][1] * 2, bump_bp=3.0 if i in flagged else 0.0)
                 for i, b in enumerate(bonds)]
        for i, b in enumerate(cheap):
            b["years"] = bonds[i]["years"]
            b["age_years"] = 12.0 if i in flagged else 1.0
            b["coupon"], b["ytm"] = 4.0, 4.0
        model = cm.Spline("s", "s", KNOTS[4:-4], 30.5, weight=cm.constant_weight, features=("old",))
        beta, res, _ = model.fit(cheap, 1e-8)
        self.assertAlmostEqual(beta[-1] * 1e4, 3.0, delta=0.05)
        self.assertLess(cm.rmse_bp(res), 0.05)
        self.assertAlmostEqual(cm.liquidity_spread(model, beta, cheap[0]) * 1e4, 3.0, delta=0.05)
        # The curve part is unaffected by the extra coefficient.
        self.assertAlmostEqual(cm.zero_rate(model, None, beta, 10), rc.zero_rate(10, TRUE), delta=2e-6)


class DiagnosticTests(unittest.TestCase):
    def test_runs_test_direction(self):
        _, _, z_alt = cm.runs_test([1, -1] * 20)
        _, _, z_block = cm.runs_test([1] * 20 + [-1] * 20)
        self.assertGreater(z_alt, 3)
        self.assertLess(z_block, -3)

    def test_spearman(self):
        self.assertAlmostEqual(cm.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(cm.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)

    def test_newey_west_zero_lags_is_iid_variance(self):
        d = [0.3, -1.2, 2.0, 0.7, -0.4, 1.1]
        m = sum(d) / len(d)
        iid = sum((x - m) ** 2 for x in d) / len(d) / len(d)
        self.assertAlmostEqual(cm.newey_west_variance(d, 0), iid)

    def test_newey_west_widens_for_clustered_errors(self):
        clustered = [1.0] * 10 + [-1.0] * 10 + [1.0] * 10 + [-1.0] * 10
        self.assertGreater(cm.newey_west_variance(clustered, 5),
                           cm.newey_west_variance(clustered, 0))

    def test_diebold_mariano_identical_and_clearly_worse(self):
        import random
        rng = random.Random(3)
        eb = [rng.gauss(0, 1e-4) for _ in range(300)]
        tie = cm.diebold_mariano(eb, eb)
        self.assertEqual(tie["dm_stat"], 0.0)
        self.assertAlmostEqual(tie["p_value"], 1.0)
        worse = cm.diebold_mariano([2 * e for e in eb], eb)
        self.assertGreater(worse["dm_stat"], 3)
        self.assertLess(worse["p_value"], 0.01)

    def test_block_bootstrap_interval_brackets_difference(self):
        import random
        rng = random.Random(5)
        eb = [rng.gauss(0, 1e-4) for _ in range(300)]
        ea = [1.5 * e for e in eb]
        lo, hi = cm.block_bootstrap_rmse_diff(ea, eb, reps=500)
        diff = cm.rmse_bp(ea) - cm.rmse_bp(eb)
        self.assertLess(lo, diff)
        self.assertGreater(hi, diff)
        self.assertGreater(lo, 0)

    def test_blocked_folds_are_contiguous_maturity_ranges(self):
        bonds = [{"years": y} for y in range(1, 31)]
        fs = cm.blocked_folds(bonds, 5)
        self.assertEqual(sorted(i for f in fs for i in f), list(range(30)))
        for f in fs:
            ys = sorted(bonds[i]["years"] for i in f)
            self.assertEqual(ys, list(range(ys[0], ys[0] + len(ys))))

    def test_folds_partition_and_span_curve(self):
        bonds = [{"years": y} for y in range(1, 31)]
        fs = cm.folds(bonds, 5)
        self.assertEqual(sorted(i for f in fs for i in f), list(range(30)))
        for f in fs:
            self.assertLess(min(bonds[i]["years"] for i in f), 6)
            self.assertGreater(max(bonds[i]["years"] for i in f), 25)


if __name__ == "__main__":
    unittest.main()
