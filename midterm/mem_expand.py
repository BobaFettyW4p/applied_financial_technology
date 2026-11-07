"""Expanded-basket test, declared before running (3 trials, 45 total). Same rule: each equal slot holds its stock while above its own
100-day average (prior close), else SPY; 2 bps per leg.
  V0 reference: MU, WDC, STX | V1 + memory-capex equipment (LRCX, AMAT, KLAC) | V2 + storage systems (NTAP) | V3 both (7 names)
Pass rule (discovery, vs V0): Sharpe >= V0 - 0.10, max drawdown no deeper than V0, and the largest single name's share of stock-specific
P&L (sum of slot weight x on x (r_stock - r_SPY)) smaller than V0's. Hold-out: one look at V1-V3 (V0 shown for reference)."""
import numpy as np
import pandas as pd

COST, DISC_END = 2e-4, "2020-12-31"
closeA = pd.read_parquet("data/close.parquet")
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna(); US = spy.index; RS = spy.pct_change()
VAR = {"V0 MU,WDC,STX": ["MU", "WDC", "STX"],
       "V1 +equipment": ["MU", "WDC", "STX", "LRCX", "AMAT", "KLAC"],
       "V2 +NTAP": ["MU", "WDC", "STX", "NTAP"],
       "V3 +both": ["MU", "WDC", "STX", "LRCX", "AMAT", "KLAC", "NTAP"]}

def slot(t):
    c = closeA[t].dropna().reindex(US).ffill(); ma = c.rolling(100).mean()
    on = (c > ma).astype(float).shift(1); r = c.pct_change()
    ret = on * r + (1 - on) * RS - COST * on.diff().abs() * 2
    return ret, on * (r - RS)                 # slot return, stock-specific component

def book(names):
    parts = [slot(t) for t in names]; N = len(names)
    ret = pd.concat([p[0] for p in parts], axis=1, keys=names)
    spec = pd.concat([p[1] for p in parts], axis=1, keys=names) / N
    ok = ret.notna().all(axis=1)
    return ret[ok].mean(axis=1), spec[ok]

def stat(r, a, b):
    r = r.loc[a:b]; nav = (1 + r).cumprod()
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), cagr=nav.iloc[-1] ** (252 / len(r)) - 1, dd=(nav / nav.cummax() - 1).min())

def concentration(spec, a, b):
    s = spec.loc[a:b].sum()
    top = s.idxmax(); m = (1 + spec.loc[a:b]).resample("ME").prod() - 1
    return top, float(s.max() / s.sum()), float(spec.loc[a:b].resample("ME").sum().min().min())

W = {"DISCOVERY 2011-2020": ("2011-01-01", DISC_END), "HOLD-OUT 2021-26 (one look)": ("2021-01-01", "2026-11-02")}
B = {k: book(v) for k, v in VAR.items()}
base = {}
for w, (a, b) in W.items():
    print(w, "| SPY:", {k: round(float(v), 2) for k, v in stat(RS.dropna(), a, b).items()})
    for k, (r, spec) in B.items():
        S = stat(r, a, b); top, share, worst = concentration(spec, a, b)
        if k.startswith("V0"): base[w] = (S, share)
        line = f"  {k:15s} Sharpe {S['sharpe']:+.2f} CAGR {S['cagr']:+.1%} DD {S['dd']:.0%} | biggest name {top} = {share:.0%} of stock-specific P&L; worst name-month {worst:+.1%}"
        if w.startswith("DISC") and not k.startswith("V0"):
            S0, sh0 = base[w]
            ok = (S['sharpe'] >= S0['sharpe'] - 0.10) and (S['dd'] >= S0['dd']) and (share < sh0)
            line += f" || PASS? sharpe {'Y' if S['sharpe'] >= S0['sharpe']-0.10 else 'n'} dd {'Y' if S['dd'] >= S0['dd'] else 'n'} conc {'Y' if share < sh0 else 'n'} -> {'PASS' if ok else 'FAIL'}"
        print(line)
