"""Estimate QuantConnect order counts and the effect of the rebalance band for F4 on the AI-era window (offline, same signal function)."""
import sys, types, importlib.util
import numpy as np, pandas as pd
fake = types.ModuleType("AlgorithmImports"); fake.QCAlgorithm = object; sys.modules["AlgorithmImports"] = fake
spec = importlib.util.spec_from_file_location("f4", "algorithms/f4_regime_spread.py"); f4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(f4)
A = f4.F4RegimeSpread
close = pd.read_parquet("data/close.parquet"); spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna()
UNI = A.MEM + A.OTHER + A.HYP
C = close[UNI].reindex(spy.index).ffill(); C["SPY"] = spy; R = C.pct_change()
START = "2022-11-22"
dates = C.loc[START:"2026-08-07"].index
T = {}
for d in dates:
    i = C.index.get_loc(d); T[d] = A.f4_targets(C.iloc[max(0, i - 419): i + 1])
T = pd.DataFrame(T).T.fillna(0.0).reindex(columns=C.columns).fillna(0.0)
print(f"window {dates[0].date()} to {dates[-1].date()}, {len(dates)} days\n")
print("band   orders  orders/yr  Sharpe  CAGR   maxDD  cost(bps/yr)")
for band in (0.0, 0.01, 0.02, 0.03, 0.05):
    p = pd.Series(0.0, index=C.columns); orders = 0; rets = []; costs = []
    for k, d in enumerate(dates):
        r = R.loc[d].fillna(0)
        pr = float((p * r).sum()); rets.append(pr)                 # yesterday's holdings earn today's return
        p = p * (1 + r) / (1 + pr)                                 # drift
        tgt = T.loc[d]
        if (tgt - p).abs().max() > band:
            diff = (tgt - p).abs(); orders += int((diff > 5e-4).sum()); costs.append(2e-4 * diff.sum()); p = tgt.copy()
        else: costs.append(0.0)
    s = pd.Series(rets, index=dates) - pd.Series(costs, index=dates)
    nav = (1 + s).cumprod(); y = len(s) / 252
    print(f"{band:4.2f}  {orders:6d}  {orders/y:8.0f}  {s.mean()/s.std()*np.sqrt(252):6.2f} {nav.iloc[-1]**(1/y)-1:6.1%} {(nav/nav.cummax()-1).min():6.0%}  {np.sum(costs)/y*1e4:6.0f}")
