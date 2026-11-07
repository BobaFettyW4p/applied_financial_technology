"""Cyclical-screen test, declared before running (4 trials, 42 total).
Cycle amplitude at month-end t = ln(max/min of price over the trailing 504 trading days), top-1000 liquid universe, price >= $5.
Members are held for the next month; each member slot (1/N) holds the stock while above its own 100-day average (decided at the prior
close), otherwise SPY. Unfilled slots are SPY. 2 bps per leg.
  V1 top 50 by amplitude (primary) | V2 top 100 | V3 control: ALL 1000 liquid names | V4 negative control: bottom 50 (least cyclical)
Pass rule (discovery): V1 beats its equal-weight buy-and-hold on Sharpe by >= 0.15 AND has a shallower max drawdown, AND V1's Sharpe gain
exceeds V3's gain and V4's gain. Hold-out: one look at all four."""
import numpy as np
import pandas as pd
import lab

COST, DISC_END = 2e-4, "2020-12-31"
C = lab.close                                    # S&P1500 cache, adjusted
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna().reindex(C.index).ffill()
R, RS = C.pct_change(), spy.pct_change()
ME = lab.ME
amp = np.log(C.rolling(504, min_periods=450).max() / C.rolling(504, min_periods=450).min()).loc[ME].where(lab.UNIV)
ON = (C > C.rolling(100).mean()).astype(float).shift(1)

def members(kind):
    r = amp.rank(axis=1, ascending=False)
    n = amp.notna().sum(axis=1)
    if kind == "top50": m = (r <= 50)
    elif kind == "top100": m = (r <= 100)
    elif kind == "bottom50": m = r.gt(n - 50, axis=0)
    elif kind == "all": m = amp.notna()
    m = m & amp.notna()
    return m

def run(kind):
    m = members(kind)
    N = {"top50": 50, "top100": 100, "bottom50": 50, "all": None}[kind]
    mem = m.reindex(C.index).ffill().shift(1).fillna(False).astype(float)            # membership known at prior month-end
    cnt = mem.sum(axis=1)
    slot = 1.0 / (N if N else cnt.where(cnt > 0))
    w_stock = mem.mul(ON.fillna(0)).mul(slot, axis=0)
    w_spy = (mem.mul(slot, axis=0).sum(axis=1) - w_stock.sum(axis=1)).clip(lower=0)
    rr = R.fillna(0)
    strat = (w_stock * rr).sum(axis=1) + w_spy * RS.fillna(0)
    turn = w_stock.diff().abs().sum(axis=1) + w_spy.diff().abs().fillna(0)
    strat = strat - turn * COST
    bh = (mem.mul(slot, axis=0) * rr).sum(axis=1)
    ok = cnt > 0
    return strat[ok], bh[ok], turn[ok], mem

def stat(r, a, b):
    r = r.loc[a:b]; nav = (1 + r).cumprod()
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), cagr=nav.iloc[-1] ** (252 / len(r)) - 1, dd=(nav / nav.cummax() - 1).min())

res = {k: run(k) for k in ("top50", "top100", "all", "bottom50")}
W = {"DISCOVERY 2011-2020": ("2011-01-01", DISC_END), "HOLD-OUT 2021-26 (one look, 4 variants declared)": ("2021-01-01", "2026-11-02")}
rows = []
for w, (a, b) in W.items():
    print(w, "| SPY:", {k: round(v, 2) for k, v in stat(RS.dropna(), a, b).items()})
    for k, (s, bh, t, mem) in res.items():
        S, H = stat(s, a, b), stat(bh, a, b)
        print(f"  {k:9s} rule: Sharpe {S['sharpe']:+.2f} CAGR {S['cagr']:+.1%} DD {S['dd']:.0%} | buy&hold same names: Sharpe {H['sharpe']:+.2f} CAGR {H['cagr']:+.1%} DD {H['dd']:.0%} "
              f"| dSharpe {S['sharpe']-H['sharpe']:+.2f} dDD {S['dd']-H['dd']:+.0%} | avg daily turnover {t.loc[a:b].mean():.3f}")
        rows.append(dict(window=w[:5], variant=k, **{f"rule_{x}": y for x, y in S.items()}, **{f"bh_{x}": y for x, y in H.items()}))
pd.DataFrame(rows).round(4).to_csv("mem_cyc_results.csv", index=False)

mem = res["top50"][3]
last = mem.iloc[-1]; names = last[last > 0].index
tr = (C[names].iloc[-1] > C[names].rolling(100).mean().iloc[-1])
print("\nlatest top-50 cyclical members, count above 100d:", int(tr.sum()), "/", len(names))
print("memory trio in V1 latest membership:", [t for t in ("MU", "WDC", "STX") if t in names])
print("sample of members:", ", ".join(sorted(names)[:50]))
