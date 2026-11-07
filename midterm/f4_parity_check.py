"""Offline parity check: run the algorithm's pure signal function day by day (no QuantConnect) and compare its P&L with the research F4 series (mem_ls6)."""
import sys, types, importlib.util
import numpy as np, pandas as pd
fake = types.ModuleType("AlgorithmImports"); fake.QCAlgorithm = object; sys.modules["AlgorithmImports"] = fake
spec = importlib.util.spec_from_file_location("f4", "algorithms/f4_regime_spread.py"); f4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(f4)
A = f4.F4RegimeSpread
close = pd.read_parquet("data/close.parquet"); spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna()
UNI = A.MEM + A.OTHER + A.HYP
C = close[UNI].reindex(spy.index).ffill(); C["SPY"] = spy
R = C.pct_change()
dates = C.loc["2021-01-01":"2026-10-28"].index
rows, prev = {}, {}
for d in dates:
    i = C.index.get_loc(d); win = C.iloc[max(0, i - 419): i + 1]
    rows[d] = A.f4_targets(win)
W = pd.DataFrame(rows).T.fillna(0.0)
Wn = W.shift(1).reindex(columns=C.columns).fillna(0.0)           # targets from close t-1 apply to day t
gross = (Wn * R.reindex(W.index)[C.columns].fillna(0)).sum(axis=1)
cost = 2e-4 * Wn.diff().abs().sum(axis=1).fillna(0)
port = (gross - cost).iloc[2:]
ref = pd.read_pickle("mem_ls6_rets.pkl") if False else None
import subprocess
# rebuild research F4 from mem_ls6 pieces without re-printing
src = open("mem_ls6.py").read().split("DISC, HOLD =")[0]; ns = {}; exec(src, ns)
res = ns["TR"]["F4 fast + spread"][0].loc[port.index[0]:port.index[-1]]
i = port.index.intersection(res.index)
print("days", len(i), "corr", round(float(np.corrcoef(port[i], res[i])[0, 1]), 4))
for nm, s in (("port", port[i]), ("research", res[i])):
    nav = (1 + s).cumprod(); print(f"{nm:9s} Sharpe {s.mean()/s.std()*np.sqrt(252):+.2f} CAGR {nav.iloc[-1]**(252/len(s))-1:+.1%} DD {(nav/nav.cummax()-1).min():.0%} 2022 {(1+s.loc['2022']).prod()-1:+.1%}")
print("avg gross", round(float(W.abs().sum(axis=1).mean()), 2), "max gross", round(float(W.abs().sum(axis=1).max()), 2))
