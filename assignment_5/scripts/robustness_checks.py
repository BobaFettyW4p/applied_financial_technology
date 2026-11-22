"""Two robustness checks on the selected curve, reproducing the numbers on the page.

1. Penalty sweep. For each smoothing penalty lambda, the spline's out-of-sample
   error under interleaved folds (a held-out bond's same-sector neighbours stay
   in training) and blocked folds (whole maturity ranges held out), with the
   forward-rate range from 8 to 14 years and the scores of a few watched bonds.
   Blocked folds are what curve_models.py now uses to choose lambda.

2. Liquidity factors. Each specification adds per-bond yield spreads
   gamma * characteristic to the fit (see curve_models.FEATURES), for both the
   smoothing spline and Nelson-Siegel-Svensson, scored by nested 10-fold CV and
   tested against the same model without them (Diebold-Mariano).

    python scripts/robustness_checks.py
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import curve_models as cm
import rich_cheap as rc

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "robustness.json"
SWEEP = [10 ** (e / 2) for e in range(-12, 5)]   # 1e-6 .. 100
SPECS = [(), ("premium",), ("old",), ("age",), ("premium", "old"), ("premium", "age")]
# The on-the-run and two recent 10-year notes, the old 4.5% Feb 2036 bond, and
# two 1997 thirty-year bonds: the securities whose scores depend most on the model.
WATCH = ["91282CRF0", "91282CQQ7", "91282CPZ8", "912810FT0", "912810FB9", "912810FA1"]
FORWARD_RANGE = (8.0, 14.0)
K = 10

_STATE = {}


def setup():
    bonds, price_date = rc.load_bonds(rc.DEFAULT_PRICES, rc.DEFAULT_REFERENCE, rc.DEFAULT_TERMS_DIR)
    bonds = [b for b in bonds if b["years"] >= 0.5]
    for b in bonds:
        b["in_fit"] = b["otr_rank"] not in (0, 1)
    fit = [b for b in bonds if b["in_fit"]]
    hi = max(t for b in fit for t, _ in b["flows"]) + 0.01
    return bonds, fit, hi, cm.quantile_knots(fit, 30), price_date


def init_worker():
    _STATE["data"] = setup()


def forward_range(model, hyper, beta):
    lo, hi = FORWARD_RANGE
    ts = [lo + 0.05 * i for i in range(int((hi - lo) / 0.05) + 1)]
    fw = [cm.forward_rate(model, hyper, beta, t) * 100 for t in ts]
    return [min(fw), max(fw)]


def scores(model, hyper, beta, bonds, fit, loo=None):
    out = dict(zip((b["cusip"] for b in bonds), cm.residuals(model, hyper, beta, bonds)))
    if loo is not None:
        out.update(zip((b["cusip"] for b in fit), loo))
    return {c: round(out[c] * 1e4, 2) for c in WATCH if c in out}


def oos(fit, sets, fitter):
    """Out-of-sample residuals: fitter(train) -> (model, hyper, beta) per fold."""
    resid = [0.0] * len(fit)
    for f in sets:
        held = set(f)
        model, hyper, beta = fitter([fit[i] for i in range(len(fit)) if i not in held])
        for i, r in zip(f, cm.residuals(model, hyper, beta, [fit[i] for i in f])):
            resid[i] = r
    return resid


def sweep_job(lam):
    bonds, fit, hi, knots, _ = _STATE["data"]
    make = lambda: cm.Spline("s", "s", knots, hi, weight=cm.constant_weight)

    def fixed(train):
        m = make()
        return m, lam, m.fit(train, lam)[0]

    m = make()
    beta, _, _ = m.fit(fit, lam)
    return {"lambda": lam,
            "interleaved_cv_bp": cm.rmse_bp(oos(fit, cm.folds(fit, K), fixed)),
            "blocked_cv_bp": cm.rmse_bp(oos(fit, cm.blocked_folds(fit, K), fixed)),
            "forward_8_14y_pct": forward_range(m, lam, beta),
            "scores_bp": scores(m, lam, beta, bonds, fit)}


def nss_blocked_job(_):
    bonds, fit, hi, knots, _ = _STATE["data"]
    m = cm.NelsonSiegel("nss", "nss", svensson=True)

    def select(train):
        h, b, _ = m.select(train)
        return m, h, b

    h, beta, _ = m.select(fit)
    return {"interleaved_cv_bp": cm.rmse_bp(oos(fit, cm.folds(fit, K), select)),
            "blocked_cv_bp": cm.rmse_bp(oos(fit, cm.blocked_folds(fit, K), select)),
            "forward_8_14y_pct": forward_range(m, h, beta), "scores_bp": scores(m, h, beta, bonds, fit)}


def make_model(kind, feats, knots, hi):
    if kind == "smoothing_spline":
        return cm.Spline(kind, kind, knots, hi, weight=cm.constant_weight, features=feats)
    return cm.NelsonSiegel(kind, kind, svensson=True, features=feats)


def spec_job(args):
    kind, feats = args
    bonds, fit, hi, knots, _ = _STATE["data"]

    def select(train):
        m = make_model(kind, feats, knots, hi)
        h, b, _ = m.select(train)
        return m, h, b

    m, hyper, beta = select(fit)
    res, jac = cm.evaluate(m.rows(fit, hyper), beta)
    loo = cm.loo_residuals(res, cm.hat_diag(jac, m.penalty(hyper)))
    cv = oos(fit, cm.folds(fit, K), select)
    order = sorted(range(len(fit)), key=lambda i: fit[i]["years"])
    return {"model": kind, "features": list(feats), "cv_bp": cm.rmse_bp(cv),
            "loo_bp": cm.rmse_bp(loo), "runs_z": cm.runs_test([loo[i] for i in order])[2],
            "gammas_bp": cm.describe_features(m, beta),
            "forward_8_14y_pct": forward_range(m, hyper, beta),
            "scores_bp": scores(m, hyper, beta, bonds, fit, loo), "_cv": cv}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=os.cpu_count())
    args = parser.parse_args()

    bonds, fit, hi, knots, price_date = setup()
    with ProcessPoolExecutor(max_workers=args.workers, initializer=init_worker) as pool:
        nss_future = pool.submit(nss_blocked_job, None)
        sweep = list(pool.map(sweep_job, SWEEP))
        specs = list(pool.map(spec_job, [(k, f) for k in ("smoothing_spline", "nss") for f in SPECS]))
        nss_ref = nss_future.result()

    order = sorted(range(len(fit)), key=lambda i: fit[i]["years"])
    base = {s["model"]: s["_cv"] for s in specs if not s["features"]}
    for s in specs:
        if s["features"]:
            dm = cm.diebold_mariano([s["_cv"][i] for i in order],
                                    [base[s["model"]][i] for i in order])
            s["vs_no_liquidity"] = {"dm_stat": dm["dm_stat"], "p_value": dm["p_value"]}
        del s["_cv"]
    best_blocked = min(sweep, key=lambda r: r["blocked_cv_bp"])
    best_inter = min(sweep, key=lambda r: r["interleaved_cv_bp"])
    doc = tidy({
        "price_date": price_date.isoformat(), "watch": WATCH, "forward_range_years": FORWARD_RANGE,
        "penalty_sweep": sweep, "best_lambda_blocked": best_blocked["lambda"],
        "best_lambda_interleaved": best_inter["lambda"], "nss_reference": nss_ref,
        "liquidity_specs": specs,
        "feature_labels": {k: v[0] for k, v in cm.FEATURES.items()},
    })
    args.output.write_text(json.dumps(doc, indent=1) + "\n")
    print_report(doc)
    print(f"\nWrote {args.output}")


def tidy(o):
    """Round floats to 4 places for the JSON, keeping small penalties (lambda) exact."""
    if isinstance(o, dict):
        return {k: tidy(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [tidy(v) for v in o]
    if isinstance(o, float) and abs(o) >= 1e-3:
        return round(o, 4)
    return o


def print_report(doc):
    w = doc["watch"]
    print(f"Penalty sweep (smoothing spline): best by blocked CV {doc['best_lambda_blocked']:.0e}, "
          f"by interleaved CV {doc['best_lambda_interleaved']:.0e}")
    print(f"{'lambda':>8}{'interleaved':>13}{'blocked':>9}{'fwd 8-14y':>14}  " + " ".join(f"{c:>10}" for c in w))
    for r in doc["penalty_sweep"]:
        lo, hi = r["forward_8_14y_pct"]
        print(f"{r['lambda']:8.0e}{r['interleaved_cv_bp']:13.2f}{r['blocked_cv_bp']:9.2f}   {lo:4.2f}-{hi:4.2f}%  "
              + " ".join(f"{r['scores_bp'][c]:+10.2f}" for c in w))
    n = doc["nss_reference"]
    print(f"{'NSS':>8}{n['interleaved_cv_bp']:13.2f}{n['blocked_cv_bp']:9.2f}   "
          f"{n['forward_8_14y_pct'][0]:4.2f}-{n['forward_8_14y_pct'][1]:4.2f}%  "
          + " ".join(f"{n['scores_bp'][c]:+10.2f}" for c in w))
    print("\nLiquidity factors (nested 10-fold CV; DM test vs the same model without them):")
    for s in doc["liquidity_specs"]:
        vs = s.get("vs_no_liquidity")
        lo, hi = s["forward_8_14y_pct"]
        print(f"  {s['model']:<17}{'+'.join(s['features']) or '-':<14}CV {s['cv_bp']:.2f}  "
              f"{'p=%.2f' % vs['p_value'] if vs else '      '}  "
              f"fwd {lo:.2f}-{hi:.2f}%  {s['gammas_bp']}  "
              + " ".join(f"{s['scores_bp'][c]:+6.2f}" for c in w))


if __name__ == "__main__":
    main()
