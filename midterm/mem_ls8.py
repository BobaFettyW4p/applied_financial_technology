"""Round 8: overnight split. Declared before running (4 new trials; ~83 total).
Motivation (research2.py, descriptive): across all four groups and SPY the close->open leg earned more with less risk than open->close (ALL 18: overnight Sharpe 1.92 vs
intraday 0.91). Always-invested design: the EW AI basket (18 names, same availability rule) is held OVERNIGHT every day; the INTRADAY leg is held only when the regime allows,
otherwise the capital sits in SPY (or is short the basket in O3). So orders occur only when the regime is down, not 4x18 trades a day.
Regime (known at the prior close): F2's graded exposure e in {-1,-1/3,+1/3,+1} from mem_ls6 (basket above 50d/100d SMA, breadth above 50d > 50%).
TRIALS (basket intraday weight x; remainder SPY; overnight basket weight = 1 in O2-O4)
  O2 binary swap : x = 1 if e > 0 else 0 (SPY intraday)
  O3 binary short: x = 1 if e > 0 else -1 (short the basket intraday when the regime is down: confident-short version)
  O4 graded swap : x = (e+1)/2 in [0,1] (SPY intraday for the rest)
  O1 reference   : overnight basket only, cash intraday (NOT always invested; shows what the split captures)
Costs: 2 bps per leg on name-weight turnover once a day, plus 2 bps x turnover at the open and at the close for the intraday switch (turnover 4|1-x| per day).
References: SPY, EW18 buy-and-hold, F4.
MAIN TEST (AI-era 2022-11-22 to latest) PASS: Sharpe >= 1.4, max DD shallower than 30%, positive return in every calendar year, Sharpe >= 1.0 in BOTH halves
(2022-11-22..2024-06-30, 2024-07-01..latest).
PRE-AI CHECK (advancers only, 2011-01-03..2022-11-21; touched earlier by peeks, so sanity only): Sharpe >= SPY's Sharpe over the same dates and max DD shallower than EW18 buy-and-hold's."""
import numpy as np
import pandas as pd

COST = 2e-4
src = open("mem_ls6.py").read().split("DISC, HOLD =")[0]; ns = {}; exec(src, ns)
R, RS, EW, TR6, eF, w, avail, UNI = ns["R"], ns["RS"], ns["EW"], ns["TR"], ns["eF"], ns["w"], ns["avail"], ns["UNI"]
US = RS.index
O = pd.read_parquet("data/open.parquet")[UNI].reindex(US); C = pd.read_parquet("data/close.parquet")[UNI].reindex(US)
on_n = (O / C.shift(1) - 1).fillna(0); id_n = (C / O - 1).fillna(0)
night = (w * on_n).sum(axis=1); day = (w * id_n).sum(axis=1)
so, sc = pd.read_parquet("data/mem_open.parquet")["SPY"].reindex(US), pd.read_parquet("data/mem_close.parquet")["SPY"].reindex(US)
spy_day = (sc / so - 1).fillna(0)
ok = avail.sum(axis=1) >= 8
wturn = w.diff().abs().sum(axis=1).fillna(0) * COST                       # daily name-weight churn (once a day)

def build(x):
    x = x.reindex(US).fillna(0.0)
    gross = (1 + night) * (1 + x * day + (1 - x) * spy_day) - 1
    cost = COST * 4 * (1 - x).abs() + wturn
    return (gross - cost).where(ok).dropna()

e = eF.reindex(US).fillna(0.0)
o2 = build((e > 0).astype(float)); o3 = build(pd.Series(np.where(e > 0, 1.0, -1.0), index=US)); o4 = build((e + 1) / 2)
o1 = (night - COST * 2 - wturn).where(ok).dropna()
TR = {"O2 binary swap": o2, "O3 binary short": o3, "O4 graded swap": o4}
REF = {"O1 overnight only (ref)": o1, "SPY": RS, "EW18 buy&hold": EW, "F4 (ref)": TR6["F4 fast + spread"][0]}

def stat(r, a, b=None):
    r = r.loc[a:b].dropna(); nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), cagr=nav.iloc[-1] ** (252 / len(r)) - 1, dd=(nav / nav.cummax() - 1).min(), beta=np.cov(r, s)[0, 1] / s.var())

W0, MID = "2022-11-22", "2024-06-30"
yr = lambda r: r.loc[W0:].groupby(r.loc[W0:].index.year).apply(lambda x: (1 + x).prod() - 1)
print(f"MAIN TEST {W0} to latest")
adv = []
for k, r in {**TR, **REF}.items():
    a, h1, h2 = stat(r, W0), stat(r, W0, MID), stat(r, "2024-07-01"); tag = ""
    if k in TR:
        ok_ = a["sharpe"] >= 1.4 and a["dd"] > -0.30 and (yr(r) > 0).all() and h1["sharpe"] >= 1.0 and h2["sharpe"] >= 1.0
        if ok_: adv.append(k)
        tag = " | " + ("PASS-main" if ok_ else "fail")
    print(f"  {k:26s} Sharpe {a['sharpe']:+.2f} CAGR {a['cagr']:+.1%} DD {a['dd']:.0%} beta {a['beta']:+.2f} | halves {h1['sharpe']:+.2f} / {h2['sharpe']:+.2f}{tag}")
print("\n  calendar-year returns in the window\n" + pd.DataFrame({k: yr(r) for k, r in {**TR, **REF}.items()}).round(3).T.to_string())
print("\n  share of days the intraday leg is on the basket (x>0):", round(float((e.loc[W0:] > 0).mean()), 2), "| mean x in O4:", round(float(((e.loc[W0:] + 1) / 2).mean()), 2))
if adv:
    a0, b0 = "2011-01-03", "2022-11-21"
    sp, ew = stat(RS, a0, b0), stat(EW, a0, b0)
    print(f"\nPRE-AI CHECK {a0}..{b0} (sanity only). SPY Sharpe {sp['sharpe']:+.2f}, EW18 buy&hold Sharpe {ew['sharpe']:+.2f} DD {ew['dd']:.0%}")
    for k in adv:
        s = stat(TR[k], a0, b0); print(f"  {k:26s} Sharpe {s['sharpe']:+.2f} CAGR {s['cagr']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | {'PASS' if s['sharpe']>=sp['sharpe'] and s['dd']>ew['dd'] else 'FAIL'}")
else:
    print("\nNo variant passed the main test; pre-AI window not examined.")
pd.DataFrame(TR).to_pickle("mem_ls8_rets.pkl")
