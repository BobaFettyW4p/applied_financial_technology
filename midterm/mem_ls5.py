"""Round 5: bear-regime overlay, net exposure allowed to flip short. Declared before running (4 new trials; ~73 total).
Book is NOT beta-neutral here (no SPY overlay): always in single stocks, net long in bull regimes, net short in bear regimes.
REGIME (all from prior close): three binaries on the equal-weight 18-name basket G:
  b1 = G above its 100d SMA, b2 = G above its 200d SMA, b3 = breadth (share of names above own 100d SMA) > 50%.
TRIALS (exposure e applies to the EW basket of available names; costs 2 bps on all weight turnover)
  G1 regime-only  : e = +1 if at least 2 of 3 binaries true else -1
  G2 graded       : e = (b1+b2+b3)/3*2-1  in {-1, -1/3, +1/3, +1}
  G3 G2 + tilt    : G2 plus 0.5 x C1 (momentum score-weighted dollar-neutral long/short, from mem_ls4) -- cross-sectional relationships
  G4 G2 + spread  : 0.5 x G2 + 0.5 x N2 (vol-targeted memory-vs-hyperscaler spread, from mem_ls3) -- the memory relationship
NEW PASS RULE (declared now, discovery 2021-01 to latest, because beta-neutral rules no longer apply): Sharpe >= 0.7, max DD shallower than 35%,
positive return in 2022 and positive Sharpe in >= 4 of 6 calendar years. References printed: SPY and EW buy-and-hold of the 18.
HOLD-OUT (2011-2020, advancers only, look #2 of that window; N2 was look #1): Sharpe >= 0.4 and max DD shallower than 40%."""
import json
import numpy as np
import pandas as pd

COST = 2e-4
close = pd.read_parquet("data/close.parquet")
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna(); US = spy.index; RS = spy.pct_change()
UNI = ["MU", "WDC", "STX", "SNDK", "NVDA", "AVGO", "AMD", "AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM", "DELL", "ANET", "VRT", "EQIX", "CEG"]
P = close[UNI].reindex(US).ffill(); R = P.pct_change()
avail = (P.notna().rolling(200).sum() >= 200).shift(1).fillna(False).astype(bool)
w = avail.astype(float).div(avail.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
Gr = (w * R.fillna(0)).sum(axis=1).where(avail.sum(axis=1) >= 8)
G = (1 + Gr.fillna(0)).cumprod()
b1 = (G > G.rolling(100).mean()); b2 = (G > G.rolling(200).mean())
b3 = ((P > P.rolling(100).mean()).where(avail).mean(axis=1) > 0.5)
B = pd.concat([b1, b2, b3], axis=1).astype(float).shift(1)
ready = G.rolling(200).mean().shift(1).notna() & (avail.sum(axis=1) >= 8)
n = B.sum(axis=1)
e1 = pd.Series(np.where(n >= 2, 1.0, -1.0), index=US).where(ready, 0.0)
e2 = ((n / 3) * 2 - 1).where(ready, 0.0)

def basket_ret(e):
    W = w.mul(e, axis=0)
    r = (W * R.fillna(0)).sum(axis=1) - COST * W.diff().abs().sum(axis=1).fillna(0)
    return r.where(ready).dropna(), W

g1, W1 = basket_ret(e1); g2, W2 = basket_ret(e2)
c1 = pd.read_pickle("mem_ls4_rets.pkl")["C1 score-weighted"].dropna()
n2 = pd.read_pickle("mem_ls3_rets.pkl")["N2 vol-targeted"].dropna()
def comb(a, b, wa, wb):
    i = a.index.intersection(b.index); return wa * a.loc[i] + wb * b.loc[i]
TR = {"G1 regime-only": (g1, e1), "G2 graded": (g2, e2), "G3 G2 + momentum tilt": (comb(g2, c1, 1.0, 0.5), e2), "G4 G2 + mem/hyper spread": (comb(g2, n2, 0.5, 0.5), e2)}
EW = ((w * R.fillna(0)).sum(axis=1) - COST * w.diff().abs().sum(axis=1).fillna(0)).where(avail.sum(axis=1) >= 8).dropna()

def stat(r, a, b):
    r = r.loc[a:b].dropna(); nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    yr = r.groupby(r.index.year).apply(lambda x: x.mean() / x.std() * np.sqrt(252) if len(x) > 40 else np.nan)
    ret_y = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), ann=nav.iloc[-1] ** (252 / len(r)) - 1, dd=(nav / nav.cummax() - 1).min(),
                beta=np.cov(r, s)[0, 1] / s.var(), yr=yr, ret_y=ret_y)

DISC, HOLD = ("2021-01-01", "2026-11-02"), ("2011-01-01", "2020-12-31")
print("DISCOVERY 2021-01 to latest")
for k, r in (("SPY", RS), ("EW buy&hold 18", EW)):
    s = stat(r, *DISC); print(f"  {k:24s} Sharpe {s['sharpe']:+.2f} CAGR {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | 2022 {s['ret_y'].get(2022, np.nan):+.1%}")
out, adv = {}, []
for k, (r, e) in TR.items():
    s = stat(r, *DISC)
    ok = s["sharpe"] >= 0.7 and s["dd"] > -0.35 and s["ret_y"].get(2022, -1) > 0 and (s["yr"] > 0).sum() >= 4
    if ok: adv.append(k)
    print(f"  {k:24s} Sharpe {s['sharpe']:+.2f} CAGR {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | 2022 {s['ret_y'].get(2022, np.nan):+.1%} | "
          f"yrs>0: {(s['yr']>0).sum()}/{s['yr'].notna().sum()} | avg net exp {e.loc[DISC[0]:].mean():+.2f}, short {(e.loc[DISC[0]:]<0).mean():.0%} of days | {'ADVANCE' if ok else 'fail'}")
    out[k] = dict(disc={a: round(float(b), 4) for a, b in s.items() if a not in ("yr", "ret_y")}, advance=bool(ok))
print("\n  yearly returns:\n" + pd.DataFrame({**{"SPY": stat(RS, *DISC)["ret_y"], "EW18": stat(EW, *DISC)["ret_y"]}, **{k: stat(v[0], *DISC)["ret_y"] for k, v in TR.items()}}).round(3).to_string())
if adv:
    print("\nHOLD-OUT 2011-2020 (advancers only)")
    for k in adv:
        s = stat(TR[k][0], *HOLD); ok = s["sharpe"] >= 0.4 and s["dd"] > -0.40
        print(f"  {k:24s} Sharpe {s['sharpe']:+.2f} CAGR {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | {'PASS' if ok else 'FAIL'}")
        out[k]["hold"] = {a: round(float(b), 4) for a, b in s.items() if a not in ("yr", "ret_y")}; out[k]["hold_pass"] = bool(ok)
else:
    print("\nNo variant advanced; hold-out not examined.")
json.dump(out, open("mem_ls5_results.json", "w"), indent=1)
pd.DataFrame({k: v[0] for k, v in TR.items()}).to_pickle("mem_ls5_rets.pkl")
