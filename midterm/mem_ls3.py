"""Redesign round 3, declared before running (4 new trials; ~65 total). Everything else identical to mem_ls2.py: universe, costs (2 bps/leg),
beta-neutral SPY overlay, windows, PASS rule (Sharpe>=0.5, DD<30%, |beta|<0.15, 2022>0, >=4/6 positive-Sharpe years) and HOLD-OUT rule
(2011-2020, one look, advancers only: Sharpe>=0.3, DD<35%). Pass rules are NOT relaxed.
Diagnosis of M1 (memory basket vs hyperscaler basket, ratio vs 100d SMA): Sharpe 0.83 but DD -65% and 2022 -20%; the drawdown is a
large exposure to a volatile spread, and the 100d exit is slow.
TRIALS (the spread = equal-weight memory basket minus equal-weight hyperscaler basket; dollar-neutral, then SPY beta overlay)
  N1 faster exit      : M1 with a 50d SMA of the ratio
  N2 vol-targeted     : M1 (100d) with spread exposure scaled by min(1, 15% / trailing-60d annualised spread vol), lagged
  N3 confirmation     : long mem/short hyper only if the ratio is above BOTH its 50d and 100d SMA, reverse only if below BOTH, else flat
  N4 N3 vol-targeted  : N3 with the N2 scaling"""
import json
import numpy as np
import pandas as pd

COST, TARGET = 2e-4, 0.15
close = pd.read_parquet("data/close.parquet")
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna(); US = spy.index; RS = spy.pct_change()
MEMN, HYPN = ["MU", "WDC", "STX", "SNDK"], ["AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM"]
UNI = MEMN + HYPN
P = close[UNI].reindex(US).ffill(); R = P.pct_change()
avail = (P.notna().rolling(200).sum() >= 200).shift(1).fillna(False).astype(bool)
roll_beta = R.rolling(120).cov(RS).div(RS.rolling(120).var(), axis=0).shift(1)

def basket(g):
    a = avail[g].astype(float); return a.div(a.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
wm, wh = basket(MEMN), basket(HYPN)
rm = (wm * R[MEMN].fillna(0)).sum(axis=1); rh = (wh * R[HYPN].fillna(0)).sum(axis=1)
spread = rm - rh
ratio = (1 + rm).cumprod() / (1 + rh).cumprod()
sma = {n: ratio.rolling(n).mean() for n in (50, 100)}
up = {n: (ratio > sma[n]).shift(1).fillna(False) for n in (50, 100)}
have = {n: sma[n].shift(1).notna() for n in (50, 100)}
volscale = (TARGET / (spread.rolling(60).std().shift(1) * np.sqrt(252))).clip(upper=1.0).fillna(0.0)

def build(sig, scale=None):
    sig = pd.Series(sig, index=US).astype(float)
    if scale is not None: sig = sig * scale
    W = pd.DataFrame(0.0, index=US, columns=UNI)
    W[MEMN] = wm.mul(sig, axis=0); W[HYPN] = -wh.mul(sig, axis=0)
    hedge = -(W * roll_beta.fillna(1.0)).sum(axis=1)
    gross = (W * R.fillna(0)).sum(axis=1) + hedge * RS.fillna(0)
    turn = W.diff().abs().sum(axis=1) + hedge.diff().abs()
    r = (gross - COST * turn.fillna(0)).where(avail.sum(axis=1) >= 8)
    return r.dropna(), W, hedge

s100 = np.where(up[100], 1.0, -1.0) * have[100]
s50 = np.where(up[50], 1.0, -1.0) * have[50]
both_up = up[50] & up[100]; both_dn = (~up[50]) & (~up[100])
s_conf = (np.where(both_up, 1.0, 0.0) - np.where(both_dn, 1.0, 0.0)) * (have[50] & have[100])
TR = {"N1 50d exit": build(s50), "N2 vol-targeted": build(s100, volscale), "N3 confirmation": build(s_conf), "N4 N3 vol-targeted": build(s_conf, volscale)}

def stat(r, a, b):
    r = r.loc[a:b].dropna(); nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    yr = r.groupby(r.index.year).apply(lambda x: x.mean() / x.std() * np.sqrt(252) if len(x) > 40 else np.nan)
    ret_y = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), ann=r.mean() * 252, dd=(nav / nav.cummax() - 1).min(),
                beta=np.cov(r, s)[0, 1] / s.var(), yr=yr, ret_y=ret_y)

DISC, HOLD = ("2021-01-01", "2026-11-02"), ("2011-01-01", "2020-12-31")
out, adv = {}, []
print("DISCOVERY 2021-01 to latest")
for k, (r, W, h) in TR.items():
    s = stat(r, *DISC)
    ok = s["sharpe"] >= 0.5 and s["dd"] > -0.30 and abs(s["beta"]) < 0.15 and s["ret_y"].get(2022, -1) > 0 and (s["yr"] > 0).sum() >= 4
    if ok: adv.append(k)
    print(f"  {k:20s} Sharpe {s['sharpe']:+.2f} ann {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | 2022 {s['ret_y'].get(2022, np.nan):+.1%} | "
          f"yrs>0: {(s['yr']>0).sum()}/{s['yr'].notna().sum()} | avg gross {W.abs().sum(axis=1).loc[DISC[0]:].mean():.2f} | {'ADVANCE' if ok else 'fail'}")
    out[k] = dict(disc={a: round(float(b), 4) for a, b in s.items() if a not in ("yr", "ret_y")}, advance=bool(ok))
print("\n  yearly returns:\n" + pd.DataFrame({k: stat(v[0], *DISC)["ret_y"] for k, v in TR.items()}).round(3).to_string())
if adv:
    print("\nHOLD-OUT 2011-2020 (one look, advancers only)")
    for k in adv:
        s = stat(TR[k][0], *HOLD); ok = s["sharpe"] >= 0.3 and s["dd"] > -0.35
        print(f"  {k:20s} Sharpe {s['sharpe']:+.2f} ann {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | {'PASS' if ok else 'FAIL'}")
        out[k]["hold"] = {a: round(float(b), 4) for a, b in s.items() if a not in ("yr", "ret_y")}; out[k]["hold_pass"] = bool(ok)
else:
    print("\nNo variant advanced; hold-out not examined.")
json.dump(out, open("mem_ls3_results.json", "w"), indent=1)
pd.DataFrame({k: v[0] for k, v in TR.items()}).to_pickle("mem_ls3_rets.pkl")
