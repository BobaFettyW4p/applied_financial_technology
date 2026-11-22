"""Combine the curve analysis outputs into the one JSON file the /curve page reads.

Inputs (data/processed/): curve_comparison.json (curve_models.py), rich_cheap.csv
(rich_cheap.py, selected model), signal_backtest.json (signal_backtest.py),
issue_selection.json (issue_selection.py) and, if present, robustness.json
(robustness_checks.py). Output: curve_page.json, uploaded to
R2 with the price data. Fails if the inputs disagree on the selected model or
the selected model's scores, so the page cannot mix runs.

    python scripts/build_curve_page.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
PERSIST_MIN_DAYS = 20
METRICS = ("cv_rmse_bp", "blocked_cv_rmse_bp", "loo_rmse_bp", "in_sample_rmse_bp", "effective_dof", "runs_z",
           "lag1_autocorr", "bucket_bias_bp", "stability_median_std_bp", "wiggles",
           "min_forward_pct", "max_forward_pct")
HORIZON_FIELDS = ("fm_slope", "fm_t", "gross_bp", "gross_t", "delayed_gross_bp",
                  "delayed_gross_t", "net_bp", "net_t", "delayed_net_bp", "delayed_net_t",
                  "hit_rate", "days")


def load(name):
    return json.loads((PROCESSED / name).read_text())


def build():
    comp, bt, iss = load("curve_comparison.json"), load("signal_backtest.json"), \
        load("issue_selection.json")
    sel = comp["selected"]
    if bt["selected"] != sel or iss["model"] != sel:
        raise ValueError(f"Selected model differs: comparison {sel}, backtest {bt['selected']}, "
                         f"issue selection {iss['model']}. Rerun the pipeline.")
    with (PROCESSED / "rich_cheap.csv").open(newline="") as f:
        rc_rows = {r["cusip"]: r for r in csv.DictReader(f)}

    history = bt["rc_history"]
    persist = {}
    for cusip in {c for day in history.values() for c in day}:
        xs = [day[cusip] for day in history.values() if cusip in day]
        if len(xs) >= PERSIST_MIN_DAYS:
            persist[cusip] = {"mean_bp": round(mean(xs), 2),
                              "cheap_share": round(sum(x > 0 for x in xs) / len(xs), 3),
                              "days": len(xs)}

    bonds = []
    for b in comp["bonds"]:
        r = rc_rows.get(b["cusip"])
        if r is None or abs(float(r["rc_bp"]) - b["rc_bp"][sel]) > 0.011:
            raise ValueError(f"{b['cusip']}: rich_cheap.csv does not match curve_comparison.json; "
                             "rerun rich_cheap.py")
        bonds.append({
            "cusip": b["cusip"], "type": b["security_type"], "coupon": b["coupon"],
            "maturity": b["maturity"], "years": b["years"], "liquidity": b["liquidity_status"],
            "in_fit": b["in_fit"], "market_ytm": b["market_ytm"],
            "fair_ytm": float(r["fair_ytm"]), "price_gap": float(r["price_gap"]),
            "rc": b["rc_bp"], "persist": persist.get(b["cusip"]),
        })

    paired = comp["paired_vs_selected"]["results"]
    paired_blocked = comp.get("paired_blocked_vs_selected", {}).get("results", {})
    models = [{
        "key": m["key"], "label": m["label"], "description": m["description"],
        "metrics": {k: m["metrics"][k] for k in METRICS},
        "paired": paired.get(m["key"]), "paired_blocked": paired_blocked.get(m["key"]),
        "curve": m["curve"], "buckets": m["buckets"],
        "half_life_days": bt["models"].get(m["key"], {}).get("half_life_days"),
        "backtest": {h: {k: v.get(k) for k in HORIZON_FIELDS}
                     for h, v in bt["models"].get(m["key"], {}).get("horizons", {}).items()},
    } for m in comp["models"]]

    return {
        "price_date": comp["price_date"], "selected": sel,
        "fit_count": comp["fit_count"], "scored_count": comp["scored_count"],
        "selection_rule": comp["selection_rule"],
        "paired_method": comp["paired_vs_selected"]["method"],
        "models": models, "bonds": bonds,
        "backtest": {"window": bt["window"], "days": bt["days"], "dropped_days": bt["dropped_days"],
                     "horizons": bt["horizons"], "method": bt["method"],
                     "profiles": {k: bt["models"][k]["profile"]
                                  for k in (sel, "nss") if k in bt["models"]},
                     "persist_min_days": PERSIST_MIN_DAYS},
        "issue_selection": {"windows": iss["windows"], "groups": iss["groups"],
                            "holds_days": iss["holds_days"]},
        "robustness": robustness(),
    }


def robustness():
    """robustness_checks.py output, if it has been run (the page omits the section otherwise)."""
    path = PROCESSED / "robustness.json"
    if not path.exists():
        return None
    r = json.loads(path.read_text())
    return {k: r[k] for k in ("watch", "forward_range_years", "penalty_sweep", "best_lambda_blocked",
                              "best_lambda_interleaved", "nss_reference", "liquidity_specs",
                              "feature_labels")}


def main():
    doc = build()
    out = PROCESSED / "curve_page.json"
    out.write_text(json.dumps(doc, separators=(",", ":")) + "\n")
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB, {len(doc['bonds'])} securities, "
          f"{len(doc['models'])} models)")


if __name__ == "__main__":
    main()
