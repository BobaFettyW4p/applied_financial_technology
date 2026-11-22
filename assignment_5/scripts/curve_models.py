"""Compare yield-curve models for rich/cheap analysis on equal terms.

Every model describes the discount function the same way,

    -ln d(t) = sum_k beta_k * g_k(t)          (so z(t) = -ln d(t) / t)

and differs only in its basis g_k:

    ns       Nelson-Siegel, 3 betas + 1 shape parameter tau
    nss      Nelson-Siegel-Svensson, 4 betas + 2 taus (the current rich_cheap.py model)
    spline   cubic B-spline on the instantaneous forward rate, f(t) = sum beta_k B_k(t),
             so g_k(t) = integral_0^t B_k(s) ds. Optional roughness penalty
             lambda * integral w(t) f''(t)^2 dt:
               - regression spline: 9 fixed tenor knots, no penalty (McCulloch-style)
               - smoothing spline: ~30 maturity-quantile knots, constant w, lambda by
                 blocked CV (contiguous maturity blocks held out)
               - VRP: same knots, Waggoner (1997) variable roughness penalty
                 w(t) = 1 / 1e3 / 1e6 below 1y / 1-10y / above 10y, scale by CV
               - overfit: ~60 knots, no penalty (the "too flexible" extreme)

All models use the same bonds (on-the-run and first off-the-run excluded from
the fit), the same objective (duration-scaled price errors, i.e. yield errors)
and are scored the same ways:

    loo_rmse      leave-one-out yield error via the penalized hat matrix, the
                  residual rich_cheap.py reports as rc_bp
    cv_rmse       nested 10-fold CV: every fold re-selects the model's own
                  hyperparameters (taus or lambda) without seeing the test bonds
    blocked_cv    the same with contiguous maturity blocks as folds: a harsher
                  test that a curve cannot pass by learning a sector from its
                  own bonds
    runs_z        Wald-Wolfowitz runs test on LOO residual signs in maturity
                  order; strongly negative = residuals come in same-sign blocks,
                  i.e. the curve shape is wrong rather than the bonds mispriced
    lag1_autocorr correlation of neighbouring (by maturity) LOO residuals
    bucket_bias   RMS of the mean LOO residual across 7 maturity buckets
    forward curve min / max / roughness / number of wiggles
    stability     bootstrap 80% subsamples, re-selecting hyperparameters each
                  time; median per-bond std of the residual (bp)
    paired test   every model vs the CV-best one on the same bonds' CV errors:
                  Diebold-Mariano on squared errors with a Newey-West variance
                  (errors ordered by maturity, so neighbouring-bond correlation
                  is allowed for) plus a moving-block bootstrap 95% interval for
                  the RMSE difference. "Significantly worse" requires both.

Standard library only.

    python scripts/curve_models.py
    python scripts/curve_models.py --bootstrap 10 --workers 4
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from concurrent.futures import ProcessPoolExecutor
from operator import mul
from pathlib import Path

from plot_yield_curve import DEFAULT_MIN_YEARS, nss_loadings, solve_linear
from rich_cheap import DEFAULT_PRICES, DEFAULT_REFERENCE, DEFAULT_TERMS_DIR, load_bonds, otr_label

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "curve_comparison.json"
BUCKETS = [(0, 2), (2, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 31)]
TENORS = (1, 2, 3, 5, 7, 10, 20, 30)
LAMBDA_GRID = [10 ** (e / 2) for e in range(-20, 3)]  # 1e-10 .. 10
SELECT_BLOCKS = 10  # contiguous maturity blocks used to choose a spline's penalty
TAU_GRID = [0.25 * 1.4 ** i for i in range(14)]       # 0.25y .. ~20y, as rich_cheap.py
REGRESSION_KNOTS = [1, 2, 3, 5, 7, 10, 15, 20, 25]


# --- Linear algebra --------------------------------------------------------

def invert(a):
    """Gauss-Jordan inverse with partial pivoting; None if singular."""
    n = len(a)
    m = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-300:
            return None
        m[col], m[piv] = m[piv], m[col]
        p = m[col][col]
        m[col] = [x / p for x in m[col]]
        for r in range(n):
            if r != col and m[r][col] != 0.0:
                f = m[r][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [row[n:] for row in m]


def gram(jac):
    cols = list(zip(*jac))
    k = len(cols)
    out = [[0.0] * k for _ in range(k)]
    for i in range(k):
        for j in range(i, k):
            out[i][j] = out[j][i] = sum(map(mul, cols[i], cols[j]))
    return out


def quad_form(m, x):
    return sum(xi * sum(map(mul, row, x)) for xi, row in zip(x, m))


# --- Generic penalized fit -------------------------------------------------
# A "row" is one bond under one basis: (dirty, dur, cash flows, G columns), where
# G columns[k][j] = g_k(t_j) for the bond's j-th cash flow.

def evaluate(rows, beta):
    """Duration-scaled price errors r_i = (P_hat - P) / D and their Jacobian."""
    res, jac = [], []
    for dirty, dur, cfs, gcols in rows:
        expo = [0.0] * len(cfs)
        for b, col in zip(beta, gcols):
            if b:
                expo = [e + b * c for e, c in zip(expo, col)]
        pvs = [cf * math.exp(-e) for cf, e in zip(cfs, expo)]
        res.append((sum(pvs) - dirty) / dur)
        jac.append([-sum(map(mul, pvs, col)) / dur for col in gcols])
    return res, jac


def objective(res, beta, penalty):
    sse = sum(r * r for r in res)
    return sse + (quad_form(penalty, beta) if penalty else 0.0)


def gn_fit(rows, beta, penalty=None, max_iter=100):
    """Levenberg-Marquardt on sum r^2 + beta' penalty beta. Returns (beta, res, jac)."""
    k = len(beta)
    res, jac = evaluate(rows, beta)
    f = objective(res, beta, penalty)
    mu = 1e-4
    for _ in range(max_iter):
        jtj = gram(jac)
        jtr = [sum(row[i] * r for row, r in zip(jac, res)) for i in range(k)]
        if penalty:
            jtj = [[a + p for a, p in zip(ra, rp)] for ra, rp in zip(jtj, penalty)]
            jtr = [g + sum(map(mul, rp, beta)) for g, rp in zip(jtr, penalty)]
        floor = 1e-12 * max(jtj[i][i] for i in range(k))
        while True:
            a = [[jtj[i][j] + (mu * jtj[i][i] + mu * floor if i == j else 0.0)
                  for j in range(k)] for i in range(k)]
            step = solve_linear(a, [-g for g in jtr])
            if step is not None:
                trial = [b + s for b, s in zip(beta, step)]
                t_res, t_jac = evaluate(rows, trial)
                t_f = objective(t_res, trial, penalty)
                if t_f < f:
                    break
            mu *= 10
            if mu > 1e12:
                return beta, res, jac
        gain = (f - t_f) / max(f, 1e-300)
        beta, res, jac, f = trial, t_res, t_jac, t_f
        mu = max(mu / 10, 1e-12)
        if gain < 1e-10:
            break
    return beta, res, jac


def hat_diag(jac, penalty=None):
    """Leverage h_ii of the linearized penalized fit: J (J'J + P)^-1 J'."""
    a = gram(jac)
    if penalty:
        a = [[x + p for x, p in zip(ra, rp)] for ra, rp in zip(a, penalty)]
    ridge = 1e-12 * max(a[i][i] for i in range(len(a)))
    inv = invert([[x + (ridge if i == j else 0.0) for j, x in enumerate(row)]
                  for i, row in enumerate(a)])
    return [sum(map(mul, j, [sum(map(mul, r, j)) for r in inv])) for j in jac]


def loo_residuals(res, h):
    return [r / max(1 - hi, 1e-3) for r, hi in zip(res, h)]


def rmse_bp(xs):
    return math.sqrt(sum(x * x for x in xs) / len(xs)) * 1e4


def flat_rate(bonds):
    return sum(2 * math.log(1 + b["ytm"] / 200) for b in bonds) / len(bonds)


# --- B-splines -------------------------------------------------------------

def bspline_values(knots, p, t):
    """All degree-p B-spline basis values at t (length len(knots) - p - 1)."""
    n = len(knots) - 1
    t = min(max(t, knots[0]), knots[-1])
    vals = [0.0] * n
    for j in range(n):
        if knots[j] <= t < knots[j + 1]:
            vals[j] = 1.0
            break
    else:  # t at the right end: last non-degenerate interval
        j = max(i for i in range(n) if knots[i] < knots[i + 1])
        vals[j] = 1.0
    for q in range(1, p + 1):
        nxt = [0.0] * (n - q)
        for j in range(n - q):
            a = knots[j + q] - knots[j]
            b = knots[j + q + 1] - knots[j + 1]
            v = 0.0
            if a > 0 and vals[j]:
                v += (t - knots[j]) / a * vals[j]
            if b > 0 and vals[j + 1]:
                v += (knots[j + q + 1] - t) / b * vals[j + 1]
            nxt[j] = v
        vals = nxt
    return vals


def bspline_derivs(knots, p, t, order):
    """order-th derivative of every degree-p basis function at t."""
    if order == 0:
        return bspline_values(knots, p, t)
    low = bspline_derivs(knots, p - 1, t, order - 1)
    out = []
    for k in range(len(knots) - p - 1):
        a = knots[k + p] - knots[k]
        b = knots[k + p + 1] - knots[k + 1]
        out.append((p / a * low[k] if a > 0 else 0.0) - (p / b * low[k + 1] if b > 0 else 0.0))
    return out


GAUSS = (0.5 - 0.5 / math.sqrt(3), 0.5 + 0.5 / math.sqrt(3))  # 2-point, exact for cubics


def constant_weight(t):
    return 1.0


def vrp_weight(t):
    """Waggoner (1997) variable roughness penalty, relative scale."""
    return 1.0 if t < 1 else 1e3 if t < 10 else 1e6


# --- Liquidity features ----------------------------------------------------
# A bond's yield is curve + s_i with s_i = sum_j gamma_j * x_ij, so its discount
# exponent gains s_i * t: one more column x_ij * t per feature, unpenalized.
# gamma > 0 = bonds with that characteristic trade at a higher yield (cheaper).

FEATURES = {
    "premium": ("Coupon premium (coupon - yield, % pts)", lambda b: b["coupon"] - b["ytm"]),
    "old": ("Issued 10+ years ago", lambda b: 1.0 if (b["age_years"] or 0.0) >= 10 else 0.0),
    "age": ("log(1 + age in years)", lambda b: math.log1p(b["age_years"] or 0.0)),
}
LIQUIDITY = ("premium", "old")


def feature_values(bond, features):
    return [FEATURES[f][1](bond) for f in features]


def make_rows(bonds, gfun, features):
    out = []
    for b in bonds:
        times = [t for t, _ in b["flows"]]
        cols = [list(c) for c in zip(*(gfun(t) for t in times))]
        for x in feature_values(b, features):
            cols.append([x * t for t in times])
        out.append((b["dirty"], b["dur"], [cf for _, cf in b["flows"]], cols))
    return out


def liquidity_spread(model, beta, bond):
    """The bond's fitted liquidity spread in yield (decimal); 0 without features."""
    gammas = beta[model.nc:]
    return sum(g * x for g, x in zip(gammas, feature_values(bond, model.features)))


def pad_penalty(p, extra):
    if p is None or not extra:
        return p
    n = len(p)
    return [row + [0.0] * extra for row in p] + [[0.0] * (n + extra) for _ in range(extra)]


def describe_features(model, beta):
    return {f"gamma_{f}_bp": round(g * 1e4, 3) for f, g in zip(model.features, beta[model.nc:])}


# --- Model families --------------------------------------------------------

class NelsonSiegel:
    """Nelson-Siegel (svensson=False) or Nelson-Siegel-Svensson (True)."""

    def __init__(self, key, label, svensson, features=()):
        self.key, self.label, self.svensson = key, label, svensson
        self.features = tuple(features)
        self.nc = 4 if svensson else 3          # curve parameters
        self.k = self.nc + len(self.features)   # + liquidity coefficients

    def g(self, t, taus):
        tau2 = taus[1] if self.svensson else taus[0] * 2
        return [x * t for x in nss_loadings(t, taus[0], tau2)[:self.nc]]

    def forward_loadings(self, t, taus):
        x1 = t / taus[0]
        out = [1.0, math.exp(-x1), x1 * math.exp(-x1)]
        if self.svensson:
            x2 = t / taus[1]
            out.append(x2 * math.exp(-x2))
        return out

    def penalty(self, hyper):
        return None

    def rows(self, bonds, taus):
        return make_rows(bonds, lambda t: self.g(t, taus), self.features)

    def start(self, bonds):
        by_maturity = sorted(bonds, key=lambda b: b["years"])
        k = max(1, len(by_maturity) // 5)
        cont = lambda b: 2 * math.log(1 + b["ytm"] / 200)
        short = sum(map(cont, by_maturity[:k])) / k
        long = sum(map(cont, by_maturity[-k:])) / k
        return [long, short - long] + [0.0] * (self.k - 2)  # gammas start at 0

    def fit(self, bonds, hyper, beta=None):
        rows = self.rows(bonds, hyper)
        beta, res, jac = gn_fit(rows, beta or self.start(bonds))
        return beta, res, jac

    def select(self, bonds, hint=None):
        """Grid search + local refinement over taus, as rich_cheap.fit_curve."""
        def sse(taus, warm):
            beta, res, _ = self.fit(bonds, taus, warm)
            return sum(r * r for r in res), beta

        start = self.start(bonds)
        best = (math.inf, start, None)
        if self.svensson:
            for t1 in TAU_GRID:
                warm = best[1]
                for t2 in TAU_GRID:
                    if t2 >= 1.5 * t1:
                        e, beta = sse((t1, t2), warm)
                        if math.isfinite(e):
                            warm = beta
                        if e < best[0]:
                            best = (e, beta, (t1, t2))
        else:
            for t1 in TAU_GRID:
                e, beta = sse((t1,), best[1])
                if e < best[0]:
                    best = (e, beta, (t1,))
        e, beta, taus = best
        step = 1.4
        for _ in range(12):
            step = step ** 0.5
            for cand in self._neighbours(taus, step):
                ce, cb = sse(cand, beta)
                if ce < e:
                    e, beta, taus = ce, cb, cand
        return taus, beta, None

    def _neighbours(self, taus, step):
        if not self.svensson:
            return [(taus[0] / step,), (taus[0] * step,)]
        t1, t2 = taus
        return [(a, b) for a in (t1 / step, t1, t1 * step) for b in (t2 / step, t2, t2 * step)
                if b >= 1.5 * a and (a, b) != taus]

    def describe(self, hyper, beta):
        names = ["b0", "b1", "b2", "b3"][:self.nc]
        d = {n: round(v * 100, 4) for n, v in zip(names, beta)}
        d.update({f"tau{i + 1}": round(t, 4) for i, t in enumerate(hyper)})
        d.update(describe_features(self, beta))
        return d


class Spline:
    """Cubic B-spline forward curve with an optional (variable) roughness penalty."""

    def __init__(self, key, label, interior, hi, weight=None, lam=None, features=()):
        self.key, self.label = key, label
        self.features = tuple(features)
        self.knots = [0.0] * 4 + sorted(interior) + [hi] * 4
        self.nc = len(self.knots) - 4
        self.k = self.nc + len(self.features)
        self.hi = hi
        self.fixed_lam = lam          # None = choose lambda by leave-one-out
        self.weight = weight
        self.breaks = sorted(set(self.knots))
        # Cumulative integral of each basis function up to every breakpoint.
        self.cum = [[0.0] * self.nc]
        for a, b in zip(self.breaks, self.breaks[1:]):
            self.cum.append([c + s for c, s in zip(self.cum[-1], self._gauss(a, b))])
        self.omega = self._roughness() if weight else None

    def _gauss(self, a, b):
        total = [0.0] * self.nc
        for x in GAUSS:
            v = bspline_values(self.knots, 3, a + (b - a) * x)
            total = [s + vi * (b - a) / 2 for s, vi in zip(total, v)]
        return total

    def _roughness(self):
        """Omega_kl = integral w(t) B_k''(t) B_l''(t) dt (Simpson, exact per piece)."""
        cuts = sorted(set(self.breaks) | {1.0, 10.0})
        cuts = [c for c in cuts if 0 <= c <= self.hi]
        om = [[0.0] * self.nc for _ in range(self.nc)]
        eps = 1e-10
        for a, b in zip(cuts, cuts[1:]):
            w = self.weight((a + b) / 2)
            pts = [(a + eps, 1), ((a + b) / 2, 4), (b - eps, 1)]
            for t, c in pts:
                d2 = bspline_derivs(self.knots, 3, t, 2)
                scale = w * c * (b - a) / 6
                nz = [i for i, v in enumerate(d2) if v]
                for i in nz:
                    for j in nz:
                        om[i][j] += scale * d2[i] * d2[j]
        return om

    def g(self, t, hyper=None):
        if t >= self.hi:
            base = self.cum[-1]
            last = bspline_values(self.knots, 3, self.hi)
            return [c + v * (t - self.hi) for c, v in zip(base, last)]
        m = max(i for i, x in enumerate(self.breaks) if x <= t)
        a = self.breaks[m]
        return [c + s for c, s in zip(self.cum[m], self._gauss(a, t))] if t > a else self.cum[m][:]

    def forward_loadings(self, t, hyper=None):
        return bspline_values(self.knots, 3, min(t, self.hi))

    def penalty(self, lam):
        if not self.omega or not lam:
            return None
        return pad_penalty([[lam * x for x in row] for row in self.omega], len(self.features))

    def rows(self, bonds, hyper=None):
        return make_rows(bonds, self.g, self.features)

    def start(self, bonds):
        # Partition of unity: equal coefficients = flat forward curve; gammas start at 0.
        return [flat_rate(bonds)] * self.nc + [0.0] * len(self.features)

    def fit(self, bonds, lam, beta=None, rows=None):
        rows = rows or self.rows(bonds)
        return gn_fit(rows, beta or self.start(bonds), self.penalty(lam))

    def select(self, bonds, hint=None):
        """Lambda minimizing blocked cross-validated RMSE; returns (lam, beta, sweep).

        Blocks are contiguous maturity ranges, so a held-out bond's same-sector
        neighbours are held out with it: the penalty cannot be tuned to let the
        curve learn a sector's level from that sector's own bonds. (Leave-one-out
        and interleaved folds can, which favours too-flexible curves.)
        """
        if self.fixed_lam is not None or not self.omega:
            beta, _, _ = self.fit(bonds, self.fixed_lam or 0.0)
            return self.fixed_lam or 0.0, beta, None
        rows = self.rows(bonds)
        grid = sorted(LAMBDA_GRID, reverse=True)  # smooth -> rough, warm-started
        sq = dict.fromkeys(grid, 0.0)
        for block in blocked_folds(bonds, SELECT_BLOCKS):
            held = set(block)
            train = [r for i, r in enumerate(rows) if i not in held]
            test = [rows[i] for i in block]
            beta = self.start([b for i, b in enumerate(bonds) if i not in held])
            for lam in grid:
                beta, _, _ = gn_fit(train, beta, self.penalty(lam))
                res, _ = evaluate(test, beta)
                sq[lam] += sum(r * r for r in res)
        sweep, beta, best = [], self.start(bonds), None
        for lam in grid:
            beta, res, jac = gn_fit(rows, beta, self.penalty(lam))
            h = hat_diag(jac, self.penalty(lam))
            cv = math.sqrt(sq[lam] / len(rows)) * 1e4
            sweep.append({"lambda": lam, "blocked_cv_rmse_bp": cv,
                          "loo_rmse_bp": rmse_bp(loo_residuals(res, h)),
                          "in_sample_rmse_bp": rmse_bp(res), "edf": sum(h)})
            if best is None or cv < best[0]:
                best = (cv, lam, beta)
        sweep.reverse()
        return best[1], best[2], sweep

    def describe(self, hyper, beta):
        return {"knots": len(self.knots) - 8, "basis": self.nc,
                "lambda": hyper if self.omega else None, **describe_features(self, beta)}


def quantile_knots(bonds, count, lo=0.5, spacing=0.25):
    """Interior knots at maturity quantiles, at least `spacing` years apart."""
    ys = sorted(b["years"] for b in bonds)
    knots = []
    for i in range(1, count + 1):
        q = ys[min(len(ys) - 1, int(i * len(ys) / (count + 1)))]
        if q > lo and (not knots or q - knots[-1] >= spacing):
            knots.append(round(q, 4))
    return knots


def build_models(fit_bonds):
    hi = max(t for b in fit_bonds for t, _ in b["flows"]) + 0.01
    smooth_knots = quantile_knots(fit_bonds, 30)
    rough_knots = quantile_knots(fit_bonds, 80, spacing=0.1)
    return [
        NelsonSiegel("ns", "Nelson-Siegel", svensson=False),
        NelsonSiegel("nss", "Nelson-Siegel-Svensson", svensson=True),
        Spline("regression_spline", "Cubic spline, 9 tenor knots", REGRESSION_KNOTS, hi, lam=0.0),
        Spline("smoothing_spline", "Smoothing spline (blocked-CV penalty)", smooth_knots, hi,
               weight=constant_weight),
        Spline("vrp", "VRP spline (Waggoner variable penalty)", smooth_knots, hi,
               weight=vrp_weight),
        Spline("overfit_spline", f"Overfit spline, {len(rough_knots)} knots, no penalty",
               rough_knots, hi, lam=0.0),
    ]


# --- Curves and diagnostics ------------------------------------------------

def zero_rate(model, hyper, beta, t):
    return sum(map(mul, beta, model.g(t, hyper))) / t


def forward_rate(model, hyper, beta, t):
    return sum(map(mul, beta, model.forward_loadings(t, hyper)))


def residuals(model, hyper, beta, bonds):
    res, _ = evaluate(model.rows(bonds, hyper), beta)
    return res


def runs_test(xs):
    signs = [x > 0 for x in xs]
    n1 = sum(signs)
    n2 = len(signs) - n1
    runs = 1 + sum(a != b for a, b in zip(signs, signs[1:]))
    n = n1 + n2
    mu = 2 * n1 * n2 / n + 1
    var = 2 * n1 * n2 * (2 * n1 * n2 - n) / (n * n * (n - 1))
    return runs, mu, (runs - mu) / math.sqrt(var) if var > 0 else 0.0


def lag1_autocorr(xs):
    m = sum(xs) / len(xs)
    d = [x - m for x in xs]
    den = sum(x * x for x in d)
    return sum(a * b for a, b in zip(d, d[1:])) / den if den else 0.0


def bucket_means(bonds, resid):
    out = []
    for lo, hi in BUCKETS:
        v = [r for b, r in zip(bonds, resid) if lo <= b["years"] < hi]
        out.append({"from": lo, "to": hi, "n": len(v),
                    "mean_bp": sum(v) / len(v) * 1e4 if v else None})
    return out


def forward_diagnostics(model, hyper, beta):
    h = 0.05
    ts = [0.5 + i * h for i in range(int(29.5 / h) + 1)]
    f = [forward_rate(model, hyper, beta, t) for t in ts]
    d1 = [(b - a) / h for a, b in zip(f, f[1:])]
    d2 = [(c - 2 * b + a) / (h * h) for a, b, c in zip(f, f[1:], f[2:])]
    wiggles = sum(1 for a, b in zip(d1, d1[1:]) if a * b < 0)
    return {"min_forward_pct": min(f) * 100, "max_forward_pct": max(f) * 100,
            "roughness": sum(x * x for x in d2) * h, "wiggles": wiggles}


def spearman(a, b):
    def ranks(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return cov / math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))


# --- Paired model comparison -----------------------------------------------
# Errors cluster by maturity, so neighbouring bonds are not independent. Both
# tests work on the CV errors ordered by maturity and allow for that dependence.

def newey_west_lags(n):
    return int(4 * (n / 100) ** (2 / 9))


def newey_west_variance(d, lags):
    """Long-run variance of the mean of d (Bartlett kernel)."""
    n = len(d)
    m = sum(d) / n
    x = [v - m for v in d]
    lrv = sum(v * v for v in x) / n
    for k in range(1, lags + 1):
        lrv += 2 * (1 - k / (lags + 1)) * sum(a * b for a, b in zip(x, x[k:])) / n
    return max(lrv, 0.0) / n


def normal_two_sided_p(z):
    return math.erfc(abs(z) / math.sqrt(2))


def diebold_mariano(ea, eb, lags=None):
    """Test equal mean squared error. Positive stat = model a has larger errors."""
    d = [a * a - b * b for a, b in zip(ea, eb)]
    lags = newey_west_lags(len(d)) if lags is None else lags
    var = newey_west_variance(d, lags)
    mean = sum(d) / len(d)
    stat = mean / math.sqrt(var) if var > 0 else 0.0
    return {"mse_diff_bp2": mean * 1e8, "dm_stat": stat, "p_value": normal_two_sided_p(stat),
            "lags": lags}


def block_bootstrap_rmse_diff(ea, eb, block=10, reps=2000, seed=11):
    """95% moving-block bootstrap interval for RMSE(a) - RMSE(b), in bp."""
    n = len(ea)
    rng = random.Random(seed)
    starts = range(n - block + 1)
    sa, sb = [x * x for x in ea], [x * x for x in eb]
    diffs = []
    for _ in range(reps):
        idx = []
        while len(idx) < n:
            s = rng.choice(starts)
            idx.extend(range(s, s + block))
        idx = idx[:n]
        diffs.append((math.sqrt(sum(sa[i] for i in idx) / n)
                      - math.sqrt(sum(sb[i] for i in idx) / n)) * 1e4)
    diffs.sort()
    return diffs[int(0.025 * reps)], diffs[int(0.975 * reps) - 1]


def paired_comparison(results, order, alpha=0.05, errors="cv"):
    """Every model against the CV-best model, on maturity-ordered out-of-sample errors.

    errors="cv" uses the interleaved folds, "blocked_cv" the contiguous maturity blocks.
    """
    best = min(results, key=lambda r: r["metrics"]["cv_rmse_bp"])
    eb = [best[errors][i] for i in order]
    out = {}
    for r in results:
        if r is best:
            continue
        ea = [r[errors][i] for i in order]
        dm = diebold_mariano(ea, eb)
        lo, hi = block_bootstrap_rmse_diff(ea, eb)
        out[r["model"].key] = {
            **dm, "rmse_diff_bp": rmse_bp(ea) - rmse_bp(eb), "rmse_diff_ci95_bp": [lo, hi],
            "significantly_worse": dm["p_value"] < alpha and lo > 0,
        }
    return best["model"].key, out


# --- Out-of-sample jobs (run in worker processes) --------------------------

def cv_job(args):
    """Fit on train with hyperparameter re-selection; residuals for test bonds."""
    model, train, test = args
    hyper, beta, _ = model.select(train)
    return residuals(model, hyper, beta, test)


def bootstrap_job(args):
    model, sample, everyone, hint = args
    hyper, beta, _ = model.select(sample, hint)
    return residuals(model, hyper, beta, everyone), [zero_rate(model, hyper, beta, t)
                                                    for t in TENORS]


def folds(bonds, k):
    """Interleaved by maturity so every fold spans the whole curve."""
    order = sorted(range(len(bonds)), key=lambda i: bonds[i]["years"])
    return [[order[j] for j in range(f, len(order), k)] for f in range(k)]


def blocked_folds(bonds, k):
    """Contiguous maturity blocks: each fold holds out a whole stretch of the curve."""
    order = sorted(range(len(bonds)), key=lambda i: bonds[i]["years"])
    return [order[j * len(order) // k:(j + 1) * len(order) // k] for j in range(k)]


# --- Driver ----------------------------------------------------------------

def compare(bonds, fit_bonds, models, n_folds=10, n_boot=20, workers=None, seed=7, log=print):
    results = []
    by_years = sorted(range(len(fit_bonds)), key=lambda i: fit_bonds[i]["years"])
    fold_sets = folds(fit_bonds, n_folds)
    block_sets = blocked_folds(fit_bonds, n_folds)
    rng = random.Random(seed)
    samples = [sorted(rng.sample(range(len(fit_bonds)), int(0.8 * len(fit_bonds))))
               for _ in range(n_boot)]

    with ProcessPoolExecutor(max_workers=workers) as pool:
        for model in models:
            log(f"  {model.label}: fitting")
            hyper, beta, sweep = model.select(fit_bonds)
            res, jac = evaluate(model.rows(fit_bonds, hyper), beta)
            h = hat_diag(jac, model.penalty(hyper))
            loo = loo_residuals(res, h)

            log(f"  {model.label}: {n_folds}-fold CV (interleaved + blocked) + {n_boot} bootstraps")

            def out_of_sample(sets):
                args = [(model, [fit_bonds[i] for i in range(len(fit_bonds)) if i not in set(f)],
                         [fit_bonds[i] for i in f]) for f in sets]
                resid = [0.0] * len(fit_bonds)
                for f, out in zip(sets, pool.map(cv_job, args)):
                    for i, r in zip(f, out):
                        resid[i] = r
                return resid

            cv_resid = out_of_sample(fold_sets)
            blocked_resid = out_of_sample(block_sets)
            boot_args = [(model, [fit_bonds[i] for i in s], fit_bonds, hyper) for s in samples]
            boot_out = list(pool.map(bootstrap_job, boot_args))
            per_bond_std = []
            for i in range(len(fit_bonds)):
                xs = [o[0][i] for o in boot_out]
                m = sum(xs) / len(xs)
                per_bond_std.append(math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)))
            tenor_std = {}
            for j, t in enumerate(TENORS):
                zs = [o[1][j] for o in boot_out]
                m = sum(zs) / len(zs)
                tenor_std[f"{t}y"] = math.sqrt(sum((z - m) ** 2 for z in zs) / (len(zs) - 1)) * 1e4

            loo_sorted = [loo[i] for i in by_years]
            runs, runs_exp, runs_z = runs_test(loo_sorted)
            buckets = bucket_means(fit_bonds, loo)
            all_res = residuals(model, hyper, beta, bonds)
            loo_by_id = {id(b): r for b, r in zip(fit_bonds, loo)}
            results.append({
                "model": model, "hyper": hyper, "beta": beta, "sweep": sweep,
                "loo": loo, "cv": cv_resid, "blocked_cv": blocked_resid, "rc": [loo_by_id.get(id(b), r) for b, r in zip(bonds, all_res)],
                "metrics": {
                    "parameters": model.k + (len(hyper) if isinstance(hyper, tuple) else 0),
                    "effective_dof": sum(h),
                    "in_sample_rmse_bp": rmse_bp(res),
                    "loo_rmse_bp": rmse_bp(loo),
                    "cv_rmse_bp": rmse_bp(cv_resid),
                    "blocked_cv_rmse_bp": rmse_bp(blocked_resid),
                    "runs": runs, "runs_expected": runs_exp, "runs_z": runs_z,
                    "lag1_autocorr": lag1_autocorr(loo_sorted),
                    "bucket_bias_bp": math.sqrt(sum(b["mean_bp"] ** 2 * b["n"] for b in buckets
                                                    if b["n"]) / len(fit_bonds)),
                    "stability_median_std_bp": sorted(per_bond_std)[len(per_bond_std) // 2] * 1e4,
                    "zero_rate_std_bp": tenor_std,
                    **forward_diagnostics(model, hyper, beta),
                },
                "buckets": buckets,
            })
    return results


def to_json(bonds, fit_bonds, results, price_date):
    best = min(results, key=lambda r: r["metrics"]["cv_rmse_bp"])
    grid = [round(0.25 + i * 0.25, 2) for i in range(int(30.25 / 0.25))]
    keys = [r["model"].key for r in results]
    agreement = {a["model"].key: {b["model"].key: round(spearman(a["loo"], b["loo"]), 4)
                                  for b in results} for a in results}
    top = lambda r: {fit_bonds[i]["cusip"] for i in
                     sorted(range(len(fit_bonds)), key=lambda i: -r["loo"][i])[:20]}
    rnd = lambda x, n=4: None if x is None else round(x, n)
    order = sorted(range(len(fit_bonds)), key=lambda i: fit_bonds[i]["years"])
    tidy = lambda p: {k: {kk: ([rnd(x, 3) for x in vv] if isinstance(vv, list)
                               else vv if isinstance(vv, (bool, int)) else rnd(vv, 4))
                          for kk, vv in v.items()} for k, v in p.items()}
    paired = tidy(paired_comparison(results, order)[1])
    paired_blocked = tidy(paired_comparison(results, order, errors="blocked_cv")[1])
    return {
        "price_date": price_date.isoformat(),
        "fit_count": len(fit_bonds), "scored_count": len(bonds),
        "selection_rule": "lowest nested 10-fold cross-validated RMSE",
        "selected": best["model"].key,
        "models": [{
            "key": r["model"].key, "label": r["model"].label,
            "description": r["model"].describe(r["hyper"], r["beta"]),
            "metrics": {k: ({kk: rnd(vv, 3) for kk, vv in v.items()} if isinstance(v, dict)
                            else rnd(v)) for k, v in r["metrics"].items()},
            "buckets": [{**b, "mean_bp": rnd(b["mean_bp"], 3)} for b in r["buckets"]],
            "lambda_sweep": [{k: rnd(v, 6) if k != "lambda" else v for k, v in s.items()}
                             for s in r["sweep"]] if r["sweep"] else None,
            "curve": {
                "t": grid,
                "zero_pct": [rnd(zero_rate(r["model"], r["hyper"], r["beta"], t) * 100)
                             for t in grid],
                "forward_pct": [rnd(forward_rate(r["model"], r["hyper"], r["beta"], t) * 100)
                                for t in grid],
            },
            "top20_cheap_overlap_with_selected": len(top(r) & top(best)),
        } for r in results],
        "rank_agreement": agreement,
        "paired_vs_selected": {
            "method": ("Diebold-Mariano test of equal mean squared CV error (Newey-West variance, "
                       "bonds ordered by maturity) and 95% moving-block bootstrap interval "
                       "(block 10) for the RMSE difference; 'significantly worse' needs both"),
            "results": paired,
        },
        "paired_blocked_vs_selected": {
            "method": ("as paired_vs_selected, on errors from contiguous maturity-block folds "
                       "(each fold holds out a whole stretch of the curve)"),
            "results": paired_blocked,
        },
        "bonds": [{
            "cusip": b["cusip"], "security_type": b["security_type"], "coupon": b["coupon"],
            "maturity": b["maturity"].isoformat(), "years": round(b["years"], 3),
            "liquidity_status": otr_label(b["otr_rank"]), "in_fit": b["in_fit"],
            "market_ytm": round(b["ytm"], 4),
            "rc_bp": {k: round(r["rc"][i] * 1e4, 2) for k, r in zip(keys, results)},
        } for i, b in enumerate(bonds)],
    }


def print_scorecard(doc):
    cols = [("cv_rmse_bp", "CV bp", 7, 2), ("blocked_cv_rmse_bp", "blkCV", 7, 2),
            ("loo_rmse_bp", "LOO bp", 7, 2),
            ("in_sample_rmse_bp", "In bp", 7, 2), ("effective_dof", "EDF", 6, 1),
            ("runs_z", "runs z", 7, 1), ("lag1_autocorr", "AC(1)", 6, 2),
            ("bucket_bias_bp", "bias", 6, 2), ("stability_median_std_bp", "stab", 6, 2),
            ("wiggles", "wigl", 5, 0), ("min_forward_pct", "minF%", 6, 2),
            ("max_forward_pct", "maxF%", 6, 2)]
    print(f"\nPrice date {doc['price_date']}; fit on {doc['fit_count']} bonds, "
          f"scored {doc['scored_count']}")
    print(f"{'model':<44}" + "".join(f"{h:>{w}}" for _, h, w, _ in cols))
    for m in sorted(doc["models"], key=lambda m: m["metrics"]["cv_rmse_bp"]):
        mark = "*" if m["key"] == doc["selected"] else " "
        cell = lambda v, w, d: f"{'>999':>{w}}" if abs(v) > 999 else f"{v:>{w}.{d}f}"
        print(f"{mark}{m['label']:<43}" + "".join(
            cell(m['metrics'][k], w, d) for k, _, w, d in cols))
    print(f"\n* selected by {doc['selection_rule']}")
    print("CV = nested 10-fold, LOO = leave-one-out (rc_bp), EDF = effective parameters,")
    print("runs z / AC(1) = residual clustering by maturity (0 = random),")
    print("bias = maturity-bucket bias, stab = median bootstrap std of a bond's score.")
    print("\nMean LOO residual by maturity bucket (bp):")
    print(f"{'':<44}" + "".join(f"{f'{b['from']}-{b['to']}y':>8}"
                                for b in doc["models"][0]["buckets"]))
    for m in doc["models"]:
        print(f" {m['label']:<43}" + "".join(f"{b['mean_bp']:>8.2f}" for b in m["buckets"]))
    print("\nPaired test vs selected model (nested CV errors, maturity-ordered):")
    print(f"  {'model':<43}{'dRMSE bp':>9}{'95% CI':>17}{'DM':>7}{'p':>8}  verdict")
    labels = {m["key"]: m["label"] for m in doc["models"]}
    for key, r in sorted(doc["paired_vs_selected"]["results"].items(),
                         key=lambda kv: kv[1]["rmse_diff_bp"]):
        lo, hi = r["rmse_diff_ci95_bp"]
        verdict = "worse" if r["significantly_worse"] else "tied"
        print(f"  {labels[key]:<43}{r['rmse_diff_bp']:>+9.2f}   [{lo:+5.2f}, {hi:+5.2f}]"
              f"{r['dm_stat']:>7.2f}{r['p_value']:>8.4f}  {verdict}")
    print("\nRank agreement of rc_bp (Spearman) with selected model:")
    for m in doc["models"]:
        print(f"  {m['label']:<43} {doc['rank_agreement'][doc['selected']][m['key']]:.3f}"
              f"   top-20 cheap overlap {m['top20_cheap_overlap_with_selected']}/20")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--terms-dir", type=Path, default=DEFAULT_TERMS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-years", type=float, default=DEFAULT_MIN_YEARS)
    parser.add_argument("--folds", type=int, default=10)
    parser.add_argument("--bootstrap", type=int, default=20)
    parser.add_argument("--workers", type=int, default=os.cpu_count())
    parser.add_argument("--models", help="comma-separated subset of model keys")
    args = parser.parse_args()

    bonds, price_date = load_bonds(args.prices, args.reference, args.terms_dir)
    bonds = [b for b in bonds if b["years"] >= args.min_years]
    for b in bonds:
        b["in_fit"] = b["otr_rank"] not in (0, 1)
    fit_bonds = [b for b in bonds if b["in_fit"]]
    models = build_models(fit_bonds)
    if args.models:
        wanted = args.models.split(",")
        models = [m for m in models if m.key in wanted]
    results = compare(bonds, fit_bonds, models, args.folds, args.bootstrap, args.workers)
    doc = to_json(bonds, fit_bonds, results, price_date)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=1) + "\n")
    print_scorecard(doc)
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
