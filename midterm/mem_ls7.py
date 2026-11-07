"""Round 7: memory vs the REST of the ecosystem spread. Declared before running (4 new trials; ~79 total).
Motivation (research2.py, descriptive): memory/chips, memory/hyper and memory/infra ratios trend; memory/chips with a 50d trend beat holding the spread (1.10 vs 0.65).
Spread = equal-weight memory basket (MU WDC STX SNDK) minus equal-weight REST basket (all available chips + hyperscalers + infra names, 14 at most). Dollar-neutral,
then SPY beta overlay (120d betas, lagged). 2 bps per leg on all turnover. Signal known at the prior close: +1 (long memory / short rest) if the ratio is above its SMA else -1.
TRIALS
  V1 50d trend            : sign vs 50d SMA of the memory/rest ratio
  V2 100d trend           : same with 100d (robustness of window choice)
  V3 V1 vol-targeted      : V1 scaled by min(1, 15%/trailing-60d annualised spread vol), lagged
  V4 F2 + V3              : 0.5 x F2 (fast graded regime, long/short EW basket, from mem_ls6) + 0.5 x V3   (replaces the memory/hyper sleeve of F4)
MAIN TEST = AI-era window 2022-11-22 to latest. PASS: Sharpe >= 0.9, max DD shallower than 30%, |beta| < 0.25 (V4: |beta| < 0.35), positive Sharpe in BOTH halves
(2022-11-22..2024-06-30 and 2024-07-01..latest), and for V1/V2 both Sharpes >= 0.5 (insensitive to 50 vs 100). References: F4 and N2 on the same window.
PRE-AI CHECK (advancers only, 2011-01-03..2022-11-21; that data was already touched by N2/G2/G4 peeks, so this is a sanity check, not clean out-of-sample):
Sharpe >= 0.3 and max DD shallower than 40%."""
import numpy as np
import pandas as pd

COST, TARGET = 2e-4, 0.15
src = open("mem_ls6.py").read().split("DISC, HOLD =")[0]; ns = {}; exec(src, ns)
R, P, RS, avail, TR6 = ns["R"], ns["P"], ns["RS"], ns["avail"], ns["TR"]
US = RS.index
MEM = ["MU", "WDC", "STX", "SNDK"]; REST = [t for t in R.columns if t not in MEM]
roll_beta = R.rolling(120).cov(RS).div(RS.rolling(120).var(), axis=0).shift(1)

def basket(g):
    a = avail[g].astype(float); return a.div(a.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
wm, wr = basket(MEM), basket(REST)
rm = (wm * R[MEM].fillna(0)).sum(axis=1); rr = (wr * R[REST].fillna(0)).sum(axis=1)
spread = rm - rr
ratio = (1 + rm).cumprod() / (1 + rr).cumprod()
volscale = (TARGET / (spread.rolling(60).std().shift(1) * np.sqrt(252))).clip(upper=1.0).fillna(0.0)
ok = (avail[MEM].sum(axis=1) >= 1) & (avail[REST].sum(axis=1) >= 6)

def build(n, scale=None):
    sma = ratio.rolling(n).mean()
    sig = pd.Series(np.where((ratio > sma).shift(1).fillna(False), 1.0, -1.0), index=US).where(sma.shift(1).notna() & ok, 0.0)
    if scale is not None: sig = sig * scale
    W = pd.DataFrame(0.0, index=US, columns=list(R.columns))
    W[MEM] = wm.mul(sig, axis=0); W[REST] = -wr.mul(sig, axis=0)
    hedge = -(W * roll_beta.fillna(1.0)).sum(axis=1)
    gross = (W * R.fillna(0)).sum(axis=1) + hedge * RS.fillna(0)
    turn = W.diff().abs().sum(axis=1) + hedge.diff().abs()
    return (gross - COST * turn.fillna(0)).where(ok).dropna()

v1, v2, v3 = build(50), build(100), build(50, volscale)
f2 = TR6["F2 graded fast"][0]; i = f2.index.intersection(v3.index)
TR = {"V1 50d trend": v1, "V2 100d trend": v2, "V3 50d vol-targeted": v3, "V4 F2 + V3": 0.5 * f2.loc[i] + 0.5 * v3.loc[i]}
REF = {"F4 (F2 + mem/hyper)": TR6["F4 fast + spread"][0], "N2 (mem/hyper, 100d, vol-tgt)": pd.read_pickle("mem_ls3_rets.pkl")["N2 vol-targeted"].dropna()}

def stat(r, a, b=None):
    r = r.loc[a:b].dropna(); nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), cagr=nav.iloc[-1] ** (252 / len(r)) - 1, dd=(nav / nav.cummax() - 1).min(), beta=np.cov(r, s)[0, 1] / s.var())

W0, MID = "2022-11-22", "2024-06-30"
print(f"MAIN TEST {W0} to latest")
res, adv = {}, []
for k, r in {**TR, **REF}.items():
    a, h1, h2 = stat(r, W0), stat(r, W0, MID), stat(r, "2024-07-01")
    res[k] = (a, h1, h2)
    tag = ""
    if k in TR:
        bmax = 0.35 if k.startswith("V4") else 0.25
        ok_ = a["sharpe"] >= 0.9 and a["dd"] > -0.30 and abs(a["beta"]) < bmax and h1["sharpe"] > 0 and h2["sharpe"] > 0
        res[k] = (a, h1, h2, ok_); tag = " | " + ("PASS-main" if ok_ else "fail")
    print(f"  {k:30s} Sharpe {a['sharpe']:+.2f} CAGR {a['cagr']:+.1%} DD {a['dd']:.0%} beta {a['beta']:+.2f} | halves {h1['sharpe']:+.2f} / {h2['sharpe']:+.2f}{tag}")
robust = res["V1 50d trend"][0]["sharpe"] >= 0.5 and res["V2 100d trend"][0]["sharpe"] >= 0.5
print(f"  50d/100d robustness (both V1 and V2 Sharpe >= 0.5): {'yes' if robust else 'NO'}")
print("\n  calendar-year returns in the window")
print(pd.DataFrame({k: r.loc[W0:].groupby(r.loc[W0:].index.year).apply(lambda x: (1 + x).prod() - 1) for k, r in {**TR, **REF}.items()}).round(3).T.to_string())
adv = [k for k in TR if res[k][3]]
if adv:
    print("\nPRE-AI CHECK 2011-01-03 to 2022-11-21 (advancers only; sanity check, not clean OOS)")
    for k in adv:
        s = stat(TR[k], "2011-01-03", "2022-11-21"); print(f"  {k:30s} Sharpe {s['sharpe']:+.2f} CAGR {s['cagr']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | {'PASS' if s['sharpe']>=0.3 and s['dd']>-0.40 else 'FAIL'}")
else:
    print("\nNo variant passed the main test; pre-AI window not examined.")
pd.DataFrame(TR).to_pickle("mem_ls7_rets.pkl")
