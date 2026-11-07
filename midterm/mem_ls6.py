"""Round 6, declared before running (2 new trials; ~75 total) + an exploratory hold-out peek.
FASTER REGIME: same as mem_ls5 but binaries use shorter windows:  b1 = G above 50d SMA, b2 = G above 100d SMA, b3 = share of names above their own 50d SMA > 50%.
  F2 graded fast       : e = (b1+b2+b3)/3*2-1 on the EW 18-name basket
  F4 fast + spread     : 0.5 x F2 + 0.5 x N2 (vol-targeted memory-vs-hyperscaler spread)
Pass rule UNCHANGED from mem_ls5 (discovery 2021+: Sharpe>=0.7, DD<35%, 2022>0, >=4/6 positive-Sharpe years). Advancers get a gated hold-out look
(2011-2020, Sharpe>=0.4, DD<40%).
EXPLORATORY PEEK (not a pass test): G2 and G4 (round 5, slower regime) on 2011-2020, shown regardless, labelled as a second/third use of that window.
After this script the 2011-2020 window is spent for this family; no further variants will be tested on it."""
import numpy as np
import pandas as pd

COST = 2e-4
close = pd.read_parquet("data/close.parquet")
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna(); US = spy.index; RS = spy.pct_change()
UNI = ["MU", "WDC", "STX", "SNDK", "NVDA", "AVGO", "AMD", "AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM", "DELL", "ANET", "VRT", "EQIX", "CEG"]
P = close[UNI].reindex(US).ffill(); R = P.pct_change()
avail = (P.notna().rolling(200).sum() >= 200).shift(1).fillna(False).astype(bool)
w = avail.astype(float).div(avail.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
Gr = (w * R.fillna(0)).sum(axis=1).where(avail.sum(axis=1) >= 8); G = (1 + Gr.fillna(0)).cumprod()

def regime(fast, slow, bw):
    b1, b2 = G > G.rolling(fast).mean(), G > G.rolling(slow).mean()
    b3 = (P > P.rolling(bw).mean()).where(avail).mean(axis=1) > 0.5
    n = pd.concat([b1, b2, b3], axis=1).astype(float).shift(1).sum(axis=1)
    ready = G.rolling(max(slow, 200)).mean().shift(1).notna() & (avail.sum(axis=1) >= 8)
    return ((n / 3) * 2 - 1).where(ready, 0.0), ready

def basket_ret(e, ready):
    W = w.mul(e, axis=0)
    return ((W * R.fillna(0)).sum(axis=1) - COST * W.diff().abs().sum(axis=1).fillna(0)).where(ready).dropna()

eF, rdy = regime(50, 100, 50)
f2 = basket_ret(eF, rdy)
n2 = pd.read_pickle("mem_ls3_rets.pkl")["N2 vol-targeted"].dropna()
prev = pd.read_pickle("mem_ls5_rets.pkl")
def comb(a, b, wa, wb):
    i = a.index.intersection(b.index); return wa * a.loc[i] + wb * b.loc[i]
TR = {"F2 graded fast": (f2, eF), "F4 fast + spread": (comb(f2, n2, 0.5, 0.5), eF)}
EW = ((w * R.fillna(0)).sum(axis=1) - COST * w.diff().abs().sum(axis=1).fillna(0)).where(avail.sum(axis=1) >= 8).dropna()

def stat(r, a, b):
    r = r.loc[a:b].dropna(); nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    yr = r.groupby(r.index.year).apply(lambda x: x.mean() / x.std() * np.sqrt(252) if len(x) > 40 else np.nan)
    ret_y = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), ann=nav.iloc[-1] ** (252 / len(r)) - 1, dd=(nav / nav.cummax() - 1).min(),
                beta=np.cov(r, s)[0, 1] / s.var(), yr=yr, ret_y=ret_y)

DISC, HOLD = ("2021-01-01", "2026-11-02"), ("2011-01-01", "2020-12-31")
line = lambda k, s: f"  {k:26s} Sharpe {s['sharpe']:+.2f} CAGR {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f}"
print("DISCOVERY 2021-01 to latest")
adv = []
for k, (r, e) in TR.items():
    s = stat(r, *DISC)
    ok = s["sharpe"] >= 0.7 and s["dd"] > -0.35 and s["ret_y"].get(2022, -1) > 0 and (s["yr"] > 0).sum() >= 4
    if ok: adv.append(k)
    print(line(k, s) + f" | 2022 {s['ret_y'].get(2022, np.nan):+.1%} | yrs>0 {(s['yr']>0).sum()}/{s['yr'].notna().sum()} | short {(e.loc[DISC[0]:]<0).mean():.0%} of days | {'ADVANCE' if ok else 'fail'}")
print("\n  yearly:\n" + pd.DataFrame({k: stat(v[0], *DISC)["ret_y"] for k, v in TR.items()}).round(3).to_string())
if adv:
    print("\nGATED HOLD-OUT 2011-2020 (advancers)")
    for k in adv:
        s = stat(TR[k][0], *HOLD); print(line(k, s) + f" | {'PASS' if s['sharpe']>=0.4 and s['dd']>-0.40 else 'FAIL'}")
print("\nEXPLORATORY PEEK 2011-2020 (not a pass test; slow-regime G2/G4 from round 5; references)")
for k, r in (("SPY", RS), ("EW buy&hold 18", EW), ("G2 graded (100/200d)", prev["G2 graded"]), ("G4 G2+spread (100/200d)", prev["G4 G2 + mem/hyper spread"])):
    s = stat(r, *HOLD); print(line(k, s) + " | yrs>0 " + f"{(s['yr']>0).sum()}/{s['yr'].notna().sum()}")
s2, s4 = stat(prev["G2 graded"], *HOLD), stat(prev["G4 G2 + mem/hyper spread"], *HOLD)
print("\n  yearly 2011-20:\n" + pd.DataFrame({"SPY": stat(RS, *HOLD)["ret_y"], "EW18": stat(EW, *HOLD)["ret_y"], "G2": s2["ret_y"], "G4": s4["ret_y"]}).round(3).to_string())
