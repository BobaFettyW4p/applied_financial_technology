"""The buy-and-hold edge: which issue to buy within a maturity range.

The signal backtest showed rich/cheap gaps barely converge within 20 days, so a
convergence trade loses to the bid/ask spread. A buy-and-hold investor pays the
spread anyway, though, and persistent cheapness is then extra yield for free.
For every day and maturity window (e.g. 7-8 years), using the selected curve's
daily scores from signal_backtest.py:

  pick        the cheapest issue (highest rc) among all scored securities in
              the window, including on-the-run issues (scored out of sample)
  vs          the window average, the richest issue, and the newest issue (the
              most recently issued security in the window, a liquidity-first
              buyer's default)
  pickup      rc(pick) - rc(alternative), in bp of yield to maturity
  net pickup  pickup minus the difference in purchase cost, converted to yield
              (buying at FedInvest's BUY price lowers your yield by cost / DV01)
  realized    did the pickup show up in returns? The curve-hedged excess return
              of pick minus alternative, held h days, annualized in bp, chosen on
              day t but bought at day t+1 prices so quote noise on the signal day
              can't help. If cheapness persists, realized ~= pickup (carry).

    python scripts/signal_backtest.py   # first: daily scores
    python scripts/issue_selection.py
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

import signal_backtest as sb

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKTEST = ROOT / "data" / "processed" / "signal_backtest.json"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "issue_selection.json"
WINDOWS = [(0.5, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 10),
           (10, 15), (15, 20), (20, 25), (25, 30.5)]
GROUPS = {"0.5-5y": (0.5, 5), "5-10y": (5, 10), "10-30y": (10, 30.5), "all": (0.5, 30.5)}
HOLDS = (20, 40)
MIN_ISSUES = 3
ALTERNATIVES = ("average", "richest", "newest")


def build_panel(days, rc_history):
    """Per day: cusip -> fields needed for scoring, costs and returns."""
    panel = []
    for d, bonds in days:
        rc = rc_history[d]
        panel.append({b["cusip"]: {
            "rc": rc[b["cusip"]] / 1e4, "dur": b["dur"], "dirty": b["dirty"],
            "years": b["years"], "in_fit": b["in_fit"], "issue_date": b["issue_date"],
            "cost_buy": b["cost_buy"], "cost_sell": b["cost_sell"],
        } for b in bonds if b["cusip"] in rc})
    return panel


def cost_bp(p):
    """Purchase cost as a one-time reduction in yield to maturity, bp."""
    return p["cost_buy"] / p["dur"] * 1e4


def hedged_return_bp(entry, exit_, years):
    """Curve-hedged excess return, annualized bp: change in the price gap / price."""
    return (sb.gap(entry) - sb.gap(exit_)) / entry["dirty"] * 1e4 / years


def window_choices(day, lo, hi):
    names = [c for c, p in day.items() if lo <= p["years"] < hi]
    if len(names) < MIN_ISSUES:
        return None
    names.sort(key=lambda c: day[c]["rc"])
    dated = [c for c in names if day[c]["issue_date"]]
    return {"pick": names[-1], "richest": names[0], "all": names,
            "newest": max(dated, key=lambda c: day[c]["issue_date"]) if dated else None}


def selection_day(panel, t, lo, hi):
    """Pickups (bp of yield) of the cheapest issue vs each alternative on day t."""
    ch = window_choices(panel[t], lo, hi)
    if not ch:
        return None
    day = panel[t]
    pick = day[ch["pick"]]
    avg_rc = sum(day[c]["rc"] for c in ch["all"]) / len(ch["all"])
    avg_cost = sum(cost_bp(day[c]) for c in ch["all"]) / len(ch["all"])
    out = {"issues": len(ch["all"]), "pick": ch["pick"],
           "pick_discount_usd_per_100mm": sb.gap(pick) * 1e6}
    alts = {"average": (avg_rc, avg_cost), "richest": (day[ch["richest"]]["rc"],
                                                       cost_bp(day[ch["richest"]]))}
    if ch["newest"] and ch["newest"] != ch["pick"]:
        alts["newest"] = (day[ch["newest"]]["rc"], cost_bp(day[ch["newest"]]))
    elif ch["newest"]:
        alts["newest"] = (pick["rc"], cost_bp(pick))  # the newest issue is the cheapest
    for name, (rc, cost) in alts.items():
        pickup = (pick["rc"] - rc) * 1e4
        out[f"pickup_vs_{name}_bp"] = pickup
        out[f"net_pickup_vs_{name}_bp"] = pickup - (cost_bp(pick) - cost)
    return out


def realized_day(panel, t, lo, hi, hold, delay=1):
    """Annualized hedged return (bp) of the pick minus each alternative, entered at t+delay."""
    e, x = t + delay, t + delay + hold
    if x >= len(panel):
        return None
    ch = window_choices(panel[t], lo, hi)
    if not ch:
        return None
    alive = lambda c: c in panel[e] and c in panel[x]
    if not alive(ch["pick"]):
        return None
    years = hold / 252
    ret = lambda c: hedged_return_bp(panel[e][c], panel[x][c], years)
    pick = ret(ch["pick"])
    peers = [c for c in ch["all"] if alive(c)]
    out = {"predicted_vs_average_bp": (panel[e][ch["pick"]]["rc"] - sum(
        panel[e][c]["rc"] for c in peers) / len(peers)) * 1e4,
        "realized_vs_average_bp": pick - sum(ret(c) for c in peers) / len(peers)}
    if alive(ch["richest"]):
        out["realized_vs_richest_bp"] = pick - ret(ch["richest"])
    if ch["newest"] and alive(ch["newest"]):
        out["realized_vs_newest_bp"] = pick - ret(ch["newest"])
    return out


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def summarize(rows, keys, lags):
    out = {}
    for k in keys:
        series = [r[k] for r in rows if r.get(k) is not None]
        m, t = sb.nw_mean_t(series, lags) if len(series) >= 3 else (mean(series), None)
        if len(series) < 2 * lags:
            t = None  # windows overlap so heavily there is ~1 independent observation
        out[k] = m
        out[f"{k}_t"] = t
    return out


def analyse(panel, dates):
    sel_keys = (["issues", "pick_discount_usd_per_100mm"]
                + [f"{p}vs_{a}_bp" for a in ALTERNATIVES for p in ("pickup_", "net_pickup_")])
    real_keys = ["predicted_vs_average_bp", "realized_vs_average_bp", "realized_vs_richest_bp",
                 "realized_vs_newest_bp"]
    windows, groups = [], {}
    by_window_sel, by_window_real = {}, {h: {} for h in HOLDS}
    for lo, hi in WINDOWS:
        sel = [r for r in (selection_day(panel, t, lo, hi) for t in range(len(panel))) if r]
        by_window_sel[(lo, hi)] = sel
        row = {"from": lo, "to": hi, "days": len(sel)}
        if sel:
            row.update(summarize(sel, sel_keys, 5))
            picks = {}
            for r in sel:
                picks[r["pick"]] = picks.get(r["pick"], 0) + 1
            top, n = max(picks.items(), key=lambda kv: kv[1])
            row["most_picked"] = {"cusip": top, "share_of_days": n / len(sel)}
            row["distinct_picks"] = len(picks)
        for h in HOLDS:
            real = [r for r in (realized_day(panel, t, lo, hi, h) for t in range(len(panel))) if r]
            by_window_real[h][(lo, hi)] = real
            if real:
                row[f"hold_{h}d"] = summarize(real, real_keys, h) | {"days": len(real)}
        windows.append(row)
    for name, (lo, hi) in GROUPS.items():
        members = [w for w in WINDOWS if w[0] >= lo and w[1] <= hi]
        # Average across windows each day, so every window counts once per day.
        daily_sel = []
        for t in range(len(panel)):
            rows = [r for w in members for r in [selection_day(panel, t, *w)] if r]
            if rows:
                daily_sel.append({k: mean([r[k] for r in rows if k in r]) for k in sel_keys})
        g = summarize(daily_sel, sel_keys, 5)
        for h in HOLDS:
            daily = []
            for t in range(len(panel)):
                rows = [r for w in members for r in [realized_day(panel, t, *w, h)] if r]
                if rows:
                    daily.append({k: mean([r[k] for r in rows if k in r]) for k in real_keys})
            g[f"hold_{h}d"] = summarize(daily, real_keys, h) | {"days": len(daily)}
        groups[name] = g
    return {"windows": windows, "groups": groups}


def print_report(doc):
    f = lambda v, w=7, d=2: f"{v:>{w}.{d}f}" if isinstance(v, (int, float)) else f"{'-':>{w}}"
    print(f"\nIssue selection with {doc['model_label']}, {doc['window'][0]} to {doc['window'][1]}")
    print("Pickup = yield of the cheapest issue in the window minus the alternative (bp);")
    print("net = after the difference in FedInvest purchase cost. Realized = annualized")
    print("curve-hedged return, pick minus window average, bought the day after selection.\n")
    print(f"{'window':>10}{'issues':>7}{'vs avg':>8}{'net':>7}{'vs rich':>8}{'vs new':>8}{'net':>7}"
          f"{'$/100mm':>10}{'pred':>7}{'real20':>8}{'t':>6}{'real40':>8}{'t':>6}  most picked")
    for w in doc["windows"]:
        if not w["days"]:
            continue
        h20, h40 = w.get("hold_20d", {}), w.get("hold_40d", {})
        print(f"{w['from']:>4}-{w['to']:<4}y{f(w['issues'], 6, 1)}"
              f"{f(w['pickup_vs_average_bp'], 8)}{f(w['net_pickup_vs_average_bp'])}"
              f"{f(w['pickup_vs_richest_bp'], 8)}{f(w['pickup_vs_newest_bp'], 8)}"
              f"{f(w['net_pickup_vs_newest_bp'])}{f(w['pick_discount_usd_per_100mm'], 10, 0)}"
              f"{f(h20.get('predicted_vs_average_bp'))}{f(h20.get('realized_vs_average_bp'), 8)}"
              f"{f(h20.get('realized_vs_average_bp_t'), 6, 1)}"
              f"{f(h40.get('realized_vs_average_bp'), 8)}{f(h40.get('realized_vs_average_bp_t'), 6, 1)}"
              f"  {w['most_picked']['cusip']} {w['most_picked']['share_of_days']:.0%}")
    print("\nBy maturity group (each window weighted equally per day):")
    print(f"{'group':>10}{'vs avg':>8}{'net':>7}{'vs new':>8}{'net':>7}"
          f"{'pred20':>8}{'real20':>8}{'t':>6}{'real40':>8}{'t':>6}{'vs new 40':>10}{'t':>6}")
    for name, g in doc["groups"].items():
        h20, h40 = g["hold_20d"], g["hold_40d"]
        print(f"{name:>10}{f(g['pickup_vs_average_bp'], 8)}{f(g['net_pickup_vs_average_bp'])}"
              f"{f(g['pickup_vs_newest_bp'], 8)}{f(g['net_pickup_vs_newest_bp'])}"
              f"{f(h20['predicted_vs_average_bp'], 8)}{f(h20['realized_vs_average_bp'], 8)}"
              f"{f(h20['realized_vs_average_bp_t'], 6, 1)}{f(h40['realized_vs_average_bp'], 8)}"
              f"{f(h40['realized_vs_average_bp_t'], 6, 1)}{f(h40['realized_vs_newest_bp'], 10)}"
              f"{f(h40['realized_vs_newest_bp_t'], 6, 1)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backtest", type=Path, default=DEFAULT_BACKTEST)
    parser.add_argument("--history-dir", type=Path, default=sb.HISTORY_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    bt = json.loads(args.backtest.read_text())
    rc_history = bt["rc_history"]
    grouped, schedules = sb.load_reference(sb.REFERENCE_DIRS)
    days = []
    for d in sorted(rc_history):
        dd = date.fromisoformat(d)
        bonds, _, _ = sb.price_day(args.history_dir / f"securityprice_{d}.csv", dd, grouped,
                                   schedules, sb.original_terms(sb.REFERENCE_DIRS, dd))
        days.append((d, bonds))
    panel = build_panel(days, rc_history)
    result = analyse(panel, [d for d, _ in days])
    rnd = lambda v: round(v, 4) if isinstance(v, float) else v
    clean = lambda o: ({k: clean(v) for k, v in o.items()} if isinstance(o, dict)
                       else [clean(v) for v in o] if isinstance(o, list) else rnd(o))
    doc = {"model": bt["selected"], "model_label": bt["labels"][bt["selected"]],
           "window": bt["window"], "holds_days": list(HOLDS), "min_issues": MIN_ISSUES,
           "method": __doc__.split("\n\n")[1].strip(), **clean(result)}
    args.output.write_text(json.dumps(doc, indent=1) + "\n")
    print_report(doc)
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
