"""Fallback test, declared before running (2 trials -> 31 total): when a name's trend is off, its 1/3 slot holds
(A) SPY, or (B) SPY only while SPY is above its own 200-day average, else cash. Compared with the shipped cash version.
Costs: 2 bps per side on every switch between the stock and the fallback."""
import json
import numpy as np
import pandas as pd
from mem_combo import *

SPY_T = (C["SPY"] > C["SPY"].rolling(200).mean()).astype(float)

def slot(t, fallback):
    on = sh(TREND[t]).reindex(US).fillna(0)                 # stock held today?
    fb = {"cash": 0 * on, "spy": 1 - on, "spy_gated": (1 - on) * sh(SPY_T).reindex(US).fillna(0)}[fallback]
    gross = on * R[t] + fb * R["SPY"]
    cost = (on.diff().abs().fillna(0) + fb.diff().abs().fillna(0)) * COST       # each leg pays COST on its own trades
    return gross - cost

def book(fallback): return pd.concat([slot(t, fallback) for t in BASKET], axis=1).mean(axis=1).dropna()

res = {"cash (shipped)": book("cash"), "SPY fallback": book("spy"), "gated-SPY fallback": book("spy_gated"),
       "SPY buy&hold": R["SPY"].reindex(US).dropna(), "theme buy&hold": pd.read_pickle("mem_rets.pkl")["theme_buyhold"]}
pd.to_pickle(res, "mem_fallback_rets.pkl")
def row(r, a, b):
    r = r.loc[a:b]; nav = (1 + r).cumprod(); yrs = len(r) / 252
    return f"Sharpe {r.mean()/r.std()*np.sqrt(252):+.2f}  CAGR {nav.iloc[-1]**(1/yrs)-1:+6.1%}  maxDD {(nav/nav.cummax()-1).min():.0%}"
for lab_, (a, b) in (("DISCOVERY 2011-2020", ("2011-01-01", "2020-12-31")), ("HOLD-OUT 2021-26 (one look each, declared)", ("2021-01-01", "2026-11-02"))):
    print(lab_)
    for k, v in res.items(): print(f"  {k:20s} {row(v, a, b)}")
print("\nrolling 21-day return (full period), SPY fallback book vs cash book:")
for k in ("cash (shipped)", "SPY fallback"):
    m = ((1 + res[k]).rolling(21).apply(np.prod, raw=True) - 1).dropna()
    print(f"  {k:16s} mean {m.mean():+.1%}  5th {m.quantile(.05):+.1%}  P(<0) {(m<0).mean():.0%}")
