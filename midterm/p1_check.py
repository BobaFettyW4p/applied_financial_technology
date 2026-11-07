"""Offline checks for algorithms/p1_regime_basket.py: (1) parity with the research P1 series (mem_ls9), (2) order counts and band effect per QC run window."""
import sys, types, importlib.util
import numpy as np, pandas as pd
fake = types.ModuleType("AlgorithmImports"); fake.QCAlgorithm = object; sys.modules["AlgorithmImports"] = fake
spec = importlib.util.spec_from_file_location("p1", "algorithms/p1_regime_basket.py"); p1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p1)
A = p1.P1RegimeBasket
close = pd.read_parquet("data/close.parquet"); spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna()
UNI = A.MEM + A.CHIPS + A.HYP + A.INFRA
C = close[UNI].reindex(spy.index).ffill(); C["SPY"] = spy; R = C.pct_change()

def targets(a, b):
    dates = C.loc[a:b].index; T = {}
    for d in dates:
        i = C.index.get_loc(d); T[d] = A.p1_targets(C.iloc[max(0, i - 419): i + 1])[0]
    return pd.DataFrame(T).T.fillna(0.0).reindex(columns=C.columns).fillna(0.0)

def sim(T, band):
    p = pd.Series(0.0, index=C.columns); orders = 0; rets, costs = [], []
    for d in T.index:
        r = R.loc[d].fillna(0); pr = float((p * r).sum()); rets.append(pr); p = p * (1 + r) / (1 + pr)
        diff = (T.loc[d] - p).abs()
        if diff.max() > band:
            orders += int((diff > 5e-4).sum()); costs.append(2e-4 * diff.sum()); p = T.loc[d].copy()
        else: costs.append(0.0)
    s = pd.Series(rets, index=T.index) - pd.Series(costs, index=T.index); nav = (1 + s).cumprod(); y = len(s) / 252
    return orders, s.mean() / s.std() * np.sqrt(252), nav.iloc[-1] ** (1 / y) - 1, (nav / nav.cummax() - 1).min()

T = targets("2022-11-22", "2026-08-07")
# parity: daily rebalance, no band, vs research P1 series
Wn = T.shift(1).fillna(0.0); gross = (Wn * R.reindex(T.index)[C.columns].fillna(0)).sum(axis=1)
port = (gross - 2e-4 * Wn.diff().abs().sum(axis=1).fillna(0)).iloc[1:]
ref = pd.read_pickle("mem_ls9_rets.pkl")["P1 same binary gate"].reindex(port.index).dropna(); i = port.index.intersection(ref.index)
gr_ref = ref[i]
print("PARITY (2022-11-23..2026-08-07): corr of daily returns port vs research P1 =", round(float(np.corrcoef(port[i], gr_ref)[0, 1]), 4))
for nm, s in (("port", port[i]), ("research P1", gr_ref)):
    nav = (1 + s).cumprod(); print(f"  {nm:12s} Sharpe {s.mean()/s.std()*np.sqrt(252):+.2f} CAGR {nav.iloc[-1]**(252/len(s))-1:+.1%} DD {(nav/nav.cummax()-1).min():.0%}")
print("  regime up on", round(float((T[UNI].sum(axis=1) > 0.5).mean()), 2), "of days")
print("\nORDER COUNTS and band effect, AI-era window (2022-11-22 to 2026-08-07)")
print("band  orders  Sharpe  CAGR  maxDD")
for band in (0.0, 0.01, 0.02, 0.03):
    o, sh, cg, dd = sim(T, band); print(f"{band:4.2f} {o:6d}  {sh:6.2f} {cg:6.1%} {dd:6.0%}")
