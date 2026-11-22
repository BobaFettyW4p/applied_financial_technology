"""Rank Treasury notes and bonds as rich or cheap against a fitted zero curve.

The curve model defaults to the one curve_models.py selects by nested
cross-validation (a smoothing spline on the forward rate; see that script for
the comparison). --model nss runs the original Nelson-Siegel-Svensson fit
described below; every model shares the same objective, fit set and
leave-one-out scoring.

Unlike plot_yield_curve.py, which fits Nelson-Siegel-Svensson to yields to
maturity, this fits NSS as a *zero-coupon* curve and prices every security's
remaining cash flows off it, so coupon effects are handled by the model rather
than left in the residuals:

    z(t) = b0 + b1*L1(t) + b2*C1(t) + b3*C2(t)        (continuously compounded)
    model dirty price  P_hat = sum_j cf_j * exp(-z(t_j) * t_j)

The betas minimize sum_i ((P_hat_i - P_i) / D_i)^2, where D_i is the bond's
dollar duration (price change per unit yield). Dividing a price error by D_i
turns it into an approximate yield error, so every bond counts in yield terms
and long bonds don't dominate. For fixed (tau1, tau2) the betas are found by
Levenberg-Marquardt; the taus by a grid search plus local refinement.

Following Gurkaynak-Sack-Wright (Fed), on-the-run and first off-the-run issues
are excluded from the fit (their liquidity premium would bend the curve toward
them) but are still scored against it.

Residuals are leave-one-out: each fitted bond is scored against a curve that
did not use it, via the closed form e_i / (1 - h_ii) on the linearized problem
(h_ii = the bond's leverage), so a bond cannot hide its mispricing by pulling
the curve toward itself.

    rc_bp > 0  cheap: market yield above the curve, price below fair value
    rc_bp < 0  rich:  market yield below the curve, price above fair value

Standard library only.

    python scripts/rich_cheap.py
    python scripts/rich_cheap.py --min-years 1 --top 15
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from plot_yield_curve import (
    DEFAULT_MIN_YEARS, nss_loadings, remaining_coupons, solve_linear, yield_to_maturity,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRICES = ROOT / "data" / "processed" / "treasury_prices.csv"
DEFAULT_REFERENCE = ROOT / "data" / "processed" / "treasury_reference.json"
DEFAULT_TERMS_DIR = ROOT / "data" / "reference"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "rich_cheap.csv"
YEAR = 365.25
OTR_LABELS = {0: "on-the-run", 1: "first off-the-run"}


def years_between(start: date, end: date) -> float:
    return (end - start).days / YEAR


def term_years(label: str) -> int:
    """'10-Year' -> 10, '29-Year 9-Month' -> 30 (reopening terms round to the original)."""
    years = re.search(r"(\d+)-Year", label)
    months = re.search(r"(\d+)-Month", label)
    return round((int(years.group(1)) if years else 0)
                 + (int(months.group(1)) if months else 0) / 12)


def load_original_terms(terms_dir: Path, price_date: date):
    """cusip -> (original term in years, original issue date), from the first auction."""
    rows = defaultdict(list)
    for r in json.loads((terms_dir / "auctions.json").read_text()):
        rows[r["cusip"]].append((r["issue_date"], r["reopening"], r["security_term"]))
    for cusip, items in json.loads((terms_dir / "additional_terms.json").read_text()).items():
        for r in items:
            rows[cusip].append((r["issueDate"][:10], r["reopening"],
                                r.get("originalSecurityTerm") or r["securityTerm"]))
    terms = {}
    for cusip, items in rows.items():
        issued = [i for i in items if i[0] and i[0] != "null"
                  and date.fromisoformat(i[0]) <= price_date]
        if not issued:
            continue
        issue, _, label = min(issued, key=lambda i: (i[1] != "No", i[0]))
        terms[cusip] = (term_years(label), date.fromisoformat(issue))
    return terms


def otr_ranks(bonds):
    """0 = on-the-run, 1 = first off-the-run, ... within each original term."""
    by_term = defaultdict(list)
    for b in bonds:
        if b["original_term"] is not None:
            by_term[b["original_term"]].append(b)
    for group in by_term.values():
        group.sort(key=lambda b: b["issue_date"], reverse=True)
        for rank, b in enumerate(group):
            b["otr_rank"] = rank


def load_bonds(prices: Path, reference: Path, terms_dir: Path):
    schedules = {r["cusip"]: r["coupon_dates"]
                 for r in json.loads(reference.read_text())}
    bonds = []
    with prices.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    price_date = date.fromisoformat(rows[0]["price_date"])
    terms = load_original_terms(terms_dir, price_date)
    for r in rows:
        bonds.append(make_bond(r, schedules[r["cusip"]], terms))
    otr_ranks(bonds)
    return bonds, price_date


def make_bond(r, coupon_dates, terms):
    """One security from a treasury_prices row (strings or numbers) and its coupon dates."""
    settle = date.fromisoformat(str(r["settlement_date"]))
    maturity = date.fromisoformat(str(r["maturity"]))
    coupon = float(r["coupon"])
    dirty = float(r["dirty_price"])
    # prepare_data.py rejects irregular current periods, so every remaining
    # coupon is a regular half-year coupon.
    flows = [(years_between(settle, d), coupon / 2 + (100 if d == maturity else 0))
             for d in map(date.fromisoformat, coupon_dates) if d > settle]
    n = remaining_coupons(date.fromisoformat(str(r["next_coupon_date"])), maturity)
    w = int(r["days_to_next_coupon"]) / int(r["coupon_period_days"])
    ytm = yield_to_maturity(dirty, coupon, n, w)
    # Dollar duration w.r.t. the continuously compounded equivalent yield.
    yc = 2 * math.log(1 + ytm / 200)
    dur = sum(cf * t * math.exp(-yc * t) for t, cf in flows)
    original_term, issue = terms.get(r["cusip"], (None, None))
    return {
        "cusip": r["cusip"], "security_type": r["security_type"], "coupon": coupon,
        "maturity": maturity, "years": years_between(settle, maturity),
        "dirty": dirty, "ytm": ytm, "dur": dur, "flows": flows,
        "original_term": original_term, "issue_date": issue,
        "age_years": years_between(issue, settle) if issue else None,
        "otr_rank": None,
    }


# --- Fitting ---------------------------------------------------------------

def precompute(bonds, tau1, tau2):
    """Per cash flow: (amount, t, loadings*t) for fixed taus."""
    return [[(cf, t, tuple(l * t for l in nss_loadings(t, tau1, tau2)))
             for t, cf in b["flows"]] for b in bonds]


def residuals_and_jacobian(bonds, pre, betas):
    """Duration-scaled price errors r_i = (P_hat - P) / D and their Jacobian."""
    res, jac = [], []
    for b, flows in zip(bonds, pre):
        p_hat, g = 0.0, [0.0, 0.0, 0.0, 0.0]
        for cf, _, lt in flows:
            pv = cf * math.exp(-(betas[0] * lt[0] + betas[1] * lt[1]
                                 + betas[2] * lt[2] + betas[3] * lt[3]))
            p_hat += pv
            for k in range(4):
                g[k] -= pv * lt[k]
        res.append((p_hat - b["dirty"]) / b["dur"])
        jac.append([gk / b["dur"] for gk in g])
    return res, jac


def normal_equations(res, jac):
    jtj = [[sum(row[i] * row[j] for row in jac) for j in range(4)] for i in range(4)]
    jtr = [sum(row[i] * r for row, r in zip(jac, res)) for i in range(4)]
    return jtj, jtr


def fit_betas(bonds, pre, betas, max_iter=50):
    """Levenberg-Marquardt for the betas at fixed taus. Returns (betas, sse)."""
    res, jac = residuals_and_jacobian(bonds, pre, betas)
    sse = sum(r * r for r in res)
    damping = 1e-3
    for _ in range(max_iter):
        jtj, jtr = normal_equations(res, jac)
        while True:
            a = [[jtj[i][j] * (1 + damping if i == j else 1) for j in range(4)]
                 for i in range(4)]
            step = solve_linear(a, [-x for x in jtr])
            if step is None:
                return betas, math.inf
            trial = [b + s for b, s in zip(betas, step)]
            t_res, t_jac = residuals_and_jacobian(bonds, pre, trial)
            t_sse = sum(r * r for r in t_res)
            if t_sse < sse:
                break
            damping *= 10
            if damping > 1e8:
                return betas, sse
        improvement = (sse - t_sse) / max(sse, 1e-30)
        betas, res, jac, sse = trial, t_res, t_jac, t_sse
        damping = max(damping / 10, 1e-9)
        if improvement < 1e-10:
            break
    return betas, sse


def initial_betas(bonds):
    by_maturity = sorted(bonds, key=lambda b: b["years"])
    k = max(1, len(by_maturity) // 5)
    cont = lambda b: 2 * math.log(1 + b["ytm"] / 200)
    short = sum(map(cont, by_maturity[:k])) / k
    long = sum(map(cont, by_maturity[-k:])) / k
    return [long, short - long, 0.0, 0.0]


def fit_curve(bonds, taus=None):
    """Fit NSS zero curve. Returns ((b0, b1, b2, b3, tau1, tau2), sse)."""
    start = initial_betas(bonds)
    if taus is not None:
        betas, sse = fit_betas(bonds, precompute(bonds, *taus), start)
        return (*betas, *taus), sse

    def evaluate(t1, t2, warm):
        return fit_betas(bonds, precompute(bonds, t1, t2), warm)

    # Coarse grid, tau2 >= 1.5 * tau1 keeps the curvature terms distinct.
    grid = [0.25 * 1.4 ** i for i in range(14)]  # 0.25y .. ~20y
    best = (math.inf, start, None, None)
    for tau1 in grid:
        warm = best[1]
        for tau2 in grid:
            if tau2 >= 1.5 * tau1:
                betas, sse = evaluate(tau1, tau2, warm)
                if sse < math.inf:
                    warm = betas
                if sse < best[0]:
                    best = (sse, betas, tau1, tau2)
    sse, betas, tau1, tau2 = best
    step = 1.4
    for _ in range(12):
        step = step ** 0.5
        for t1 in (tau1 / step, tau1, tau1 * step):
            for t2 in (tau2 / step, tau2, tau2 * step):
                if t2 >= 1.5 * t1 and (t1, t2) != (tau1, tau2):
                    b, e = evaluate(t1, t2, betas)
                    if e < sse:
                        sse, betas, tau1, tau2 = e, b, t1, t2
    return (*betas, tau1, tau2), sse


def zero_rate(t, params):
    b0, b1, b2, b3, tau1, tau2 = params
    return sum(b * f for b, f in zip((b0, b1, b2, b3), nss_loadings(t, tau1, tau2)))


def score(bonds, fit_set, params):
    """In-sample residual for every bond and leave-one-out residual for fit bonds."""
    betas, taus = list(params[:4]), params[4:]
    res, jac = residuals_and_jacobian(bonds, precompute(bonds, *taus), betas)
    in_fit = {id(b) for b in fit_set}
    jtj, _ = normal_equations([0.0] * len(fit_set),
                              [j for b, j in zip(bonds, jac) if id(b) in in_fit])
    inv = [solve_linear(jtj, [1.0 if i == k else 0.0 for i in range(4)]) for k in range(4)]
    for b, r, j in zip(bonds, res, jac):
        b["resid_in"] = r
        if id(b) in in_fit:
            # Leverage of this bond in the linearized fit; LOO residual = r / (1 - h).
            h = sum(j[a] * inv[a][c] * j[c] for a in range(4) for c in range(4))
            b["leverage"] = h
            b["resid"] = r / (1 - h)
        else:
            b["leverage"] = None
            b["resid"] = r  # already out of sample


# --- Output ----------------------------------------------------------------

def otr_label(rank):
    if rank is None:
        return "unknown"
    return OTR_LABELS.get(rank, "off-the-run")


def write_csv(bonds, path: Path):
    cols = ["cusip", "security_type", "coupon", "maturity", "years_to_maturity",
            "original_term", "issue_date", "age_years", "liquidity_status", "in_fit",
            "dirty_price", "market_ytm", "fair_ytm", "fair_dirty_price", "price_gap",
            "rc_bp", "rc_bp_in_sample", "leverage", "signal"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for b in sorted(bonds, key=lambda b: b["resid"], reverse=True):
            bp = b["resid"] * 1e4
            w.writerow([
                b["cusip"], b["security_type"], f'{b["coupon"]:g}', b["maturity"].isoformat(),
                f'{b["years"]:.3f}',
                f'{b["original_term"]}-Year' if b["original_term"] else "",
                b["issue_date"].isoformat() if b["issue_date"] else "",
                f'{b["age_years"]:.2f}' if b["age_years"] is not None else "",
                otr_label(b["otr_rank"]), "yes" if b["in_fit"] else "no",
                f'{b["dirty"]:.6f}', f'{b["ytm"]:.4f}', f'{b["ytm"] - bp / 100:.4f}',
                f'{b["dirty"] + b["resid"] * b["dur"]:.6f}', f'{b["resid"] * b["dur"]:.6f}',
                f'{bp:.2f}', f'{b["resid_in"] * 1e4:.2f}',
                f'{b["leverage"]:.4f}' if b["leverage"] is not None else "",
                "cheap" if bp > 0 else "rich",
            ])


def print_summary(bonds, fit_set, params, sse, top):
    b0, b1, b2, b3, tau1, tau2 = params
    rmse = math.sqrt(sse / len(fit_set)) * 1e4
    print(f"NSS zero curve: b0={b0 * 100:.4f} b1={b1 * 100:.4f} b2={b2 * 100:.4f} "
          f"b3={b3 * 100:.4f} (%)  tau1={tau1:.3f}y tau2={tau2:.3f}y")
    print(f"Fit on {len(fit_set)} of {len(bonds)} securities; RMSE {rmse:.2f} bp")
    print("Zero rates: " + "  ".join(f"{t}y {zero_rate(t, params) * 100:.3f}%"
                                     for t in (1, 2, 5, 10, 20, 30)))
    print_rankings(bonds, fit_set, top)


def print_rankings(bonds, fit_set, top):
    def row(b):
        return (f'  {b["cusip"]}  {b["coupon"]:6.3f}% {b["maturity"].isoformat()}  '
                f'{otr_label(b["otr_rank"]):<17} {b["resid"] * 1e4:+7.2f} bp')

    for title, items in [
        ("Cheapest (fit set, leave-one-out)",
         sorted(fit_set, key=lambda b: b["resid"], reverse=True)[:top]),
        ("Richest (fit set, leave-one-out)", sorted(fit_set, key=lambda b: b["resid"])[:top]),
        ("Excluded from fit (on-the-run / first off-the-run)",
         sorted((b for b in bonds if b["otr_rank"] in (0, 1)),
                key=lambda b: b["years"])),
    ]:
        print(f"\n{title}:")
        for b in items:
            print(row(b))


def selected_model(path: Path = ROOT / "data" / "processed" / "curve_comparison.json"):
    """The model curve_models.py chose by cross-validation (smoothing spline if not run yet)."""
    return json.loads(path.read_text())["selected"] if path.exists() else "smoothing_spline"


def score_with_model(bonds, fit_set, key):
    """Fit any curve_models.py model and set resid (LOO), resid_in and leverage."""
    import curve_models as cm  # imported here: curve_models itself imports this module

    model = next((m for m in cm.build_models(fit_set) if m.key == key), None)
    if model is None:
        raise SystemExit(f"Unknown model {key!r}; choose from "
                         + ", ".join(m.key for m in cm.build_models(fit_set)))
    hyper, beta, _ = model.select(fit_set)
    res, jac = cm.evaluate(model.rows(fit_set, hyper), beta)
    h = cm.hat_diag(jac, model.penalty(hyper))
    loo = {id(b): (r, hi) for b, r, hi in zip(fit_set, res, h)}
    for b, r in zip(bonds, cm.residuals(model, hyper, beta, bonds)):
        b["resid_in"] = r
        if id(b) in loo:
            b["leverage"] = loo[id(b)][1]
            b["resid"] = r / max(1 - b["leverage"], 1e-3)
        else:
            b["leverage"] = None
            b["resid"] = r
    rmse = math.sqrt(sum(r * r for r in res) / len(res)) * 1e4
    print(f"{model.label}: {model.describe(hyper, beta)}")
    print(f"Fit on {len(fit_set)} of {len(bonds)} securities; in-sample RMSE {rmse:.2f} bp, "
          f"leave-one-out RMSE {cm.rmse_bp([b['resid'] for b in fit_set]):.2f} bp")
    print("Zero rates: " + "  ".join(f"{t}y {cm.zero_rate(model, hyper, beta, t) * 100:.3f}%"
                                     for t in (1, 2, 5, 10, 20, 30)))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=None,
                        help="curve model key from curve_models.py (default: the one "
                             "curve_comparison.json selected; 'nss' for the original fit)")
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--terms-dir", type=Path, default=DEFAULT_TERMS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-years", type=float, default=DEFAULT_MIN_YEARS,
                        help="drop securities maturing sooner than this (default: 0.5)")
    parser.add_argument("--include-otr", action="store_true",
                        help="keep on-the-run and first off-the-run issues in the fit")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    bonds, _ = load_bonds(args.prices, args.reference, args.terms_dir)
    bonds = [b for b in bonds if b["years"] >= args.min_years]
    for b in bonds:
        b["in_fit"] = args.include_otr or b["otr_rank"] not in (0, 1)
    fit_set = [b for b in bonds if b["in_fit"]]
    key = args.model or selected_model()
    if key == "nss":
        params, sse = fit_curve(fit_set)
        score(bonds, fit_set, params)
        print_summary(bonds, fit_set, params, sse, args.top)
    else:
        score_with_model(bonds, fit_set, key)
        print_rankings(bonds, fit_set, args.top)
    write_csv(bonds, args.output)
    print(f"\nWrote {args.output} ({len(bonds)} securities)")


if __name__ == "__main__":
    main()
