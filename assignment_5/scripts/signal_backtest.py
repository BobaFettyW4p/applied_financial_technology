"""Does the rich/cheap signal predict anything? Test it on 62 days of FedInvest prices.

For every trading day in data/raw/history/ (Aug 24 - Nov 20, 2026):
  1. price every note/bond (end-of-day clean + accrued, T+1 settlement), keeping
     FedInvest's BUY (ask) and SELL (bid) quotes for transaction costs;
  2. fit each curve model from curve_models.py and score every bond: rc_bp is the
     leave-one-out yield residual (positive = cheap) exactly as rich_cheap.py does.

Then, for horizons h = 1, 5, 10, 20 trading days:

  Convergence   Fama-MacBeth regression of the change in rc over h days on today's
                rc, across bonds, one regression per day. Slope -1 = full convergence,
                0 = none. 1-day slope -> half-life of a mispricing.
  Trading P&L   Each day buy the cheapest 20% and sell the richest 20% of the fit
                set, equal DV01 per bond, hedged with the fitted curve. A position's
                hedged P&L is the change in its price gap to the curve:
                    long cheap:  (gap_entry - gap_exit),  gap = rc * dollar duration
                expressed in bp of yield per unit DV01. "Net" pays the actual
                FedInvest spread: buy at BUY, sell at SELL, at entry and exit.
  Delayed entry The same trade entered one day after the signal (at t+1 prices).
                Mean reversion that comes from noise in today's quote vanishes
                with a delay; a real mispricing does not.

t-statistics use Newey-West standard errors (lag = h) because h-day windows that
start on consecutive days overlap.

    python scripts/fetch_history_reference.py   # once, terms for matured CUSIPs
    python scripts/signal_backtest.py
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
import json
import math
import os
from pathlib import Path
from statistics import median

import curve_models as cm
from prepare_data import (
    accrued_interest, coupon_dates, coupon_period, load_prices, normalize_direct,
    optional_date, select_terms,
)
from rich_cheap import load_original_terms, make_bond, otr_label, otr_ranks

ROOT = Path(__file__).resolve().parents[1]
HISTORY_DIR = ROOT / "data" / "raw" / "history"
REFERENCE_DIRS = [ROOT / "data" / "reference", ROOT / "data" / "reference" / "history"]
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "signal_backtest.json"
# SIFMA-recommended bond market closures from the window through settlement.
HOLIDAYS = {date(2026, 9, 7), date(2026, 10, 12), date(2026, 11, 11), date(2026, 11, 26)}
HORIZONS = (1, 5, 10, 20)
PROFILE_DAYS = 20
FIT_MIN_YEARS = 0.5
SCORE_MIN_YEARS = 0.25


# --- Pricing each day ------------------------------------------------------

def next_business_day(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5 or d in HOLIDAYS:
        d += timedelta(days=1)
    return d


def load_reference(dirs):
    grouped, schedules = defaultdict(list), {}
    for d in dirs:
        for row in json.loads((d / "auctions.json").read_text()):
            grouped[row["cusip"]].append(row)
        for cusip, rows in json.loads((d / "additional_terms.json").read_text()).items():
            grouped[cusip].extend(normalize_direct(r) for r in rows)
        schedules.update(json.loads((d / "coupon_schedules.json").read_text()))
    return grouped, schedules


def original_terms(dirs, price_date):
    terms = {}
    for d in dirs:
        terms.update(load_original_terms(d, price_date))
    return terms


def price_day(path: Path, price_date: date, grouped, schedules, terms_map):
    """Bonds priced off end-of-day quotes; securities that can't be priced are skipped."""
    settlement = next_business_day(price_date)
    prices, _ = load_prices(path)
    bonds, skipped = [], []
    for p in prices:
        cusip = p["cusip"]
        try:
            terms = select_terms(p, grouped[cusip], price_date)
            dates = coupon_dates(cusip, schedules.get(cusip), terms, p["maturity"])
            start = optional_date(terms.get("original_dated_date")) or optional_date(
                terms.get("dated_date"))
            prev, nxt = coupon_period(dates, settlement, start)
            clean = p["prices"]["end_of_day"]
            if clean <= 0:
                raise ValueError("no end-of-day price")
            accrued = accrued_interest(p["coupon_rate"], prev, nxt, settlement)
        except (ValueError, KeyError, ArithmeticError) as exc:
            skipped.append({"cusip": cusip, "reason": str(exc).split(":")[-1].strip()})
            continue
        row = {
            "cusip": cusip, "security_type": p["security_type"],
            "coupon": float(p["coupon_rate"] * 100), "maturity": p["maturity"].isoformat(),
            "dirty_price": float(clean + accrued), "settlement_date": settlement.isoformat(),
            "next_coupon_date": nxt.isoformat(),
            "days_to_next_coupon": (nxt - settlement).days,
            "coupon_period_days": (nxt - prev).days,
        }
        b = make_bond(row, [d.isoformat() for d in dates], terms_map)
        if b["years"] < SCORE_MIN_YEARS:
            continue
        ask, bid = p["prices"]["buy"], p["prices"]["sell"]
        b["ask_dirty"] = float(ask + accrued) if ask > 0 else None
        b["bid_dirty"] = float(bid + accrued) if bid > 0 else None
        bonds.append(b)
    otr_ranks(bonds)
    for b in bonds:
        b["in_fit"] = b["years"] >= FIT_MIN_YEARS and b["otr_rank"] not in (0, 1)
    attach_costs(bonds)
    return bonds, skipped, settlement


def bucket_of(years):
    return next(i for i, (lo, hi) in enumerate(cm.BUCKETS) if lo <= years < hi)


def attach_costs(bonds):
    """Price cost of buying (ask - mid) and selling (mid - bid) vs the end-of-day price.

    Missing quotes take that day's median for bonds in the same maturity bucket.
    """
    buy, sell = defaultdict(list), defaultdict(list)
    for b in bonds:
        k = bucket_of(b["years"])
        if b["ask_dirty"] is not None:
            buy[k].append(max(b["ask_dirty"] - b["dirty"], 0.0))
        if b["bid_dirty"] is not None:
            sell[k].append(max(b["dirty"] - b["bid_dirty"], 0.0))
    all_buy = [x for v in buy.values() for x in v] or [0.0]
    all_sell = [x for v in sell.values() for x in v] or [0.0]
    for b in bonds:
        k = bucket_of(b["years"])
        b["cost_buy"] = (max(b["ask_dirty"] - b["dirty"], 0.0) if b["ask_dirty"] is not None
                         else median(buy[k] or all_buy))
        b["cost_sell"] = (max(b["dirty"] - b["bid_dirty"], 0.0) if b["bid_dirty"] is not None
                          else median(sell[k] or all_sell))
        b["quoted"] = b["ask_dirty"] is not None and b["bid_dirty"] is not None


# --- Scoring each day ------------------------------------------------------

def score_job(args):
    """Fit one model on one day; LOO residual for fit bonds, OOS for the rest."""
    day, key, bonds = args
    fit = [b for b in bonds if b["in_fit"]]
    model = next(m for m in cm.build_models(fit) if m.key == key)
    hyper, beta, _ = model.select(fit)
    res, jac = cm.evaluate(model.rows(fit, hyper), beta)
    loo = cm.loo_residuals(res, cm.hat_diag(jac, model.penalty(hyper)))
    rc = dict(zip((b["cusip"] for b in bonds), cm.residuals(model, hyper, beta, bonds)))
    rc.update(zip((b["cusip"] for b in fit), loo))
    return day, key, rc, {"in_sample_rmse_bp": cm.rmse_bp(res), "loo_rmse_bp": cm.rmse_bp(loo)}


# --- Statistics ------------------------------------------------------------

def nw_mean_t(xs, lags):
    """Mean and Newey-West t-statistic of a (possibly overlapping) series."""
    n = len(xs)
    if n < 3:
        return (sum(xs) / n if n else None), None
    mean = sum(xs) / n
    var = cm.newey_west_variance(xs, min(lags, n - 2))
    return mean, (mean / math.sqrt(var) if var > 0 else None)


def ols_slope(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxx = sum((a - mx) ** 2 for a in x)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / sxx if sxx else None


def half_life(slope_1d):
    phi = 1 + slope_1d
    return math.log(0.5) / math.log(phi) if 0 < phi < 1 else None


def gap(p):
    return p["rc"] * p["dur"]  # model price minus market price, per $100 face


def trade_bp(entry, exit_, side):
    """Hedged P&L of one position per unit of entry DV01, in bp: (gross, net)."""
    gross = side * (gap(entry) - gap(exit_))
    cost = (entry["cost_buy"] + exit_["cost_sell"] if side > 0
            else entry["cost_sell"] + exit_["cost_buy"])
    scale = 1e4 / entry["dur"]
    return gross * scale, (gross - cost) * scale


def candidates(panel, t, need):
    """Fit bonds at day t that are still scored on every day in `need`."""
    return [c for c, p in panel[t].items() if p["in_fit"]
            and all(c in panel[s] for s in need if s < len(panel))]


def portfolio(panel, t, h, frac=0.2, delay=0):
    """Long the cheapest `frac`, short the richest `frac`; mean bp per position."""
    e, x = t + delay, t + delay + h
    if x >= len(panel):
        return None
    names = sorted(candidates(panel, t, (e, x)), key=lambda c: panel[t][c]["rc"])
    k = max(1, int(len(names) * frac))
    legs = [(c, -1) for c in names[:k]] + [(c, +1) for c in names[-k:]]
    out = {"gross": [], "net": [], "long": [], "short": []}
    for c, side in legs:
        g, n = trade_bp(panel[e][c], panel[x][c], side)
        out["gross"].append(g)
        out["net"].append(n)
        out["long" if side > 0 else "short"].append(g)
    return {k2: sum(v) / len(v) for k2, v in out.items()} | {
        "hit": sum(g > 0 for g in out["gross"]) / len(out["gross"]), "positions": len(legs)}


def fama_macbeth(panel, h):
    slopes = []
    for t in range(len(panel) - h):
        names = candidates(panel, t, (t + h,))
        x = [panel[t][c]["rc"] * 1e4 for c in names]
        y = [(panel[t + h][c]["rc"] - panel[t][c]["rc"]) * 1e4 for c in names]
        s = ols_slope(x, y)
        if s is not None:
            slopes.append(s)
    return slopes


def convergence_profile(panel, frac=0.1, days=PROFILE_DAYS):
    """Mean rc (bp) of today's cheapest and richest decile over the next `days` days."""
    cheap, rich = [[] for _ in range(days + 1)], [[] for _ in range(days + 1)]
    for t in range(len(panel) - days):
        names = sorted(candidates(panel, t, range(t, t + days + 1)),
                       key=lambda c: panel[t][c]["rc"])
        k = max(1, int(len(names) * frac))
        for d in range(days + 1):
            cheap[d].append(sum(panel[t + d][c]["rc"] for c in names[-k:]) / k * 1e4)
            rich[d].append(sum(panel[t + d][c]["rc"] for c in names[:k]) / k * 1e4)
    avg = lambda v: round(sum(v) / len(v), 3) if v else None
    return {"days": list(range(days + 1)), "cheap_decile_bp": [avg(v) for v in cheap],
            "rich_decile_bp": [avg(v) for v in rich], "formation_days": len(cheap[0])}


def analyse(panel):
    out = {"horizons": {}}
    for h in HORIZONS:
        slopes = fama_macbeth(panel, h)
        slope, slope_t = nw_mean_t(slopes, h)
        row = {"fm_slope": slope, "fm_t": slope_t, "fm_days": len(slopes)}
        for label, delay in (("", 0), ("delayed_", 1)):
            ports = [p for p in (portfolio(panel, t, h, delay=delay) for t in range(len(panel)))
                     if p]
            for k in ("gross", "net", "long", "short"):
                m, tt = nw_mean_t([p[k] for p in ports], h)
                row[f"{label}{k}_bp"], row[f"{label}{k}_t"] = m, tt
            row[f"{label}hit_rate"] = sum(p["hit"] for p in ports) / len(ports)
            row[f"{label}days"] = len(ports)
            if not label:
                row["positions_per_day"] = sum(p["positions"] for p in ports) / len(ports)
                row["_net_series"] = [p["net"] for p in ports]
        out["horizons"][str(h)] = row
    out["half_life_days"] = half_life(out["horizons"]["1"]["fm_slope"])
    out["profile"] = convergence_profile(panel)
    return out


def paired_net(a, b, h):
    """Mean and NW t-stat of the per-day net P&L difference between two models."""
    xa, xb = a["horizons"][str(h)]["_net_series"], b["horizons"][str(h)]["_net_series"]
    return nw_mean_t([x - y for x, y in zip(xa, xb)], h)


# --- Driver ----------------------------------------------------------------

def build_panel(days, scores, key):
    panel = []
    for day_iso, bonds in days:
        rc = scores[(day_iso, key)]
        panel.append({b["cusip"]: {"rc": rc[b["cusip"]], "dur": b["dur"], "in_fit": b["in_fit"],
                                   "years": b["years"], "cost_buy": b["cost_buy"],
                                   "cost_sell": b["cost_sell"]} for b in bonds})
    return panel


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--history-dir", type=Path, default=HISTORY_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--models", default="ns,nss,regression_spline,smoothing_spline,vrp,"
                        "overfit_spline")
    parser.add_argument("--workers", type=int, default=os.cpu_count())
    args = parser.parse_args()
    keys = args.models.split(",")

    grouped, schedules = load_reference(REFERENCE_DIRS)
    days, day_info, dropped = [], [], []
    for path in sorted(args.history_dir.glob("securityprice_*.csv")):
        d = date.fromisoformat(path.stem.split("_")[1])
        bonds, skipped, settle = price_day(path, d, grouped, schedules,
                                           original_terms(REFERENCE_DIRS, d))
        if len(bonds) < 100:  # e.g. end-of-day prices not yet published
            dropped.append({"date": d.isoformat(), "priced": len(bonds),
                            "reasons": sorted({s["reason"] for s in skipped})})
            print(f"Dropping {d}: only {len(bonds)} securities priced "
                  f"({', '.join(dropped[-1]['reasons'])})")
            continue
        days.append((d.isoformat(), bonds))
        reasons = defaultdict(int)
        for s in skipped:
            reasons[s["reason"]] += 1
        day_info.append({"date": d.isoformat(), "settlement": settle.isoformat(),
                         "scored": len(bonds), "in_fit": sum(b["in_fit"] for b in bonds),
                         "quoted": sum(b["quoted"] for b in bonds),
                         "skipped": dict(reasons)})
    print(f"Priced {len(days)} days, {days[0][0]} to {days[-1][0]}; "
          f"{min(i['in_fit'] for i in day_info)}-{max(i['in_fit'] for i in day_info)} "
          f"bonds in each day's fit")

    jobs = [(d, k, bonds) for d, bonds in days for k in keys]
    scores, fit_stats = {}, defaultdict(dict)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for n, (d, k, rc, stats) in enumerate(pool.map(score_job, jobs, chunksize=2), 1):
            scores[(d, k)] = rc
            fit_stats[d][k] = stats
            if n % 60 == 0:
                print(f"  scored {n}/{len(jobs)} day-model fits", flush=True)

    results = {k: analyse(build_panel(days, scores, k)) for k in keys}
    labels = {m.key: m.label for m in cm.build_models([b for b in days[0][1] if b["in_fit"]])}
    selected = json.loads((ROOT / "data" / "processed" / "curve_comparison.json")
                          .read_text())["selected"] if (ROOT / "data" / "processed" /
                                                         "curve_comparison.json").exists() \
        else "smoothing_spline"
    paired = {k: {str(h): dict(zip(("mean_bp", "t"), paired_net(results[selected], results[k], h)))
                  for h in HORIZONS} for k in keys if k != selected and selected in results}

    for info in day_info:
        info["fit"] = fit_stats[info["date"]]
    rnd = lambda v: round(v, 4) if isinstance(v, float) else v
    doc = {
        "window": [days[0][0], days[-1][0]], "days": len(days), "horizons": list(HORIZONS),
        "dropped_days": dropped,
        "selected": selected, "labels": labels,
        "method": {
            "signal": "leave-one-out yield residual rc_bp (positive = cheap)",
            "portfolio": "long cheapest 20%, short richest 20% of fit set, equal DV01, "
                         "curve-hedged; P&L in bp of yield per unit DV01 per position",
            "costs": "buy at FedInvest BUY, sell at SELL; missing quotes use the day's "
                     "median for the maturity bucket",
            "t_stats": "Newey-West, lag = horizon",
        },
        "models": {k: {
            "half_life_days": rnd(r["half_life_days"]),
            "horizons": {h: {kk: rnd(vv) for kk, vv in row.items() if not kk.startswith("_")}
                         for h, row in r["horizons"].items()},
            "profile": r["profile"],
        } for k, r in results.items()},
        "selected_minus_model_net_bp": {k: {h: {kk: rnd(vv) for kk, vv in v.items()}
                                            for h, v in d.items()} for k, d in paired.items()},
        "daily": day_info,
        "rc_history": {d: {c: round(v * 1e4, 2) for c, v in scores[(d, selected)].items()}
                       for d, _ in days} if selected in keys else None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=1) + "\n")
    print_report(doc)
    print(f"\nWrote {args.output}")


def print_report(doc):
    fmt = lambda v, w=7, d=2: f"{v:>{w}.{d}f}" if isinstance(v, (int, float)) else f"{'-':>{w}}"
    print(f"\nWindow {doc['window'][0]} to {doc['window'][1]} ({doc['days']} days)")
    for h in map(str, doc["horizons"]):
        print(f"\n--- {h}-day horizon ---")
        print(f"{'model':<44}{'FM slope':>9}{'t':>6}{'gross':>8}{'t':>6}{'net':>8}{'t':>6}"
              f"{'hit':>6}{'delay net':>10}{'t':>6}")
        for k, m in sorted(doc["models"].items(),
                           key=lambda kv: -(kv[1]["horizons"][h]["net_bp"] or -1e9)):
            r = m["horizons"][h]
            mark = "*" if k == doc["selected"] else " "
            print(f"{mark}{doc['labels'].get(k, k):<43}{fmt(r['fm_slope'], 9, 3)}"
                  f"{fmt(r['fm_t'], 6, 1)}{fmt(r['gross_bp'], 8)}{fmt(r['gross_t'], 6, 1)}"
                  f"{fmt(r['net_bp'], 8)}{fmt(r['net_t'], 6, 1)}{fmt(r['hit_rate'], 6)}"
                  f"{fmt(r['delayed_net_bp'], 10)}{fmt(r['delayed_net_t'], 6, 1)}")
    print("\nHalf-life of a mispricing (days, from the 1-day FM slope):")
    for k, m in doc["models"].items():
        print(f"  {doc['labels'].get(k, k):<43} {fmt(m['half_life_days'], 6, 1)}")
    sel = doc["selected"]
    prof = doc["models"][sel]["profile"]
    print(f"\nConvergence of {doc['labels'][sel]} deciles "
          f"({prof['formation_days']} formation days), mean rc_bp:")
    for d in (0, 1, 2, 5, 10, 20):
        print(f"  day {d:>2}: cheap {prof['cheap_decile_bp'][d]:+6.2f}   "
              f"rich {prof['rich_decile_bp'][d]:+6.2f}")
    print(f"\nNet P&L, {doc['labels'][sel]} minus each model (bp per position, NW t):")
    for k, d in doc["selected_minus_model_net_bp"].items():
        print(f"  {doc['labels'].get(k, k):<43}" + "".join(
            f"  {h}d {fmt(v['mean_bp'], 6)} ({fmt(v['t'], 4, 1)})" for h, v in d.items()))


if __name__ == "__main__":
    main()
