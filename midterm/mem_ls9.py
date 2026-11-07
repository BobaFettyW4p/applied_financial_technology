"""Round 9: gate BOTH legs of the overnight split. Declared before running (4 new trials; ~87 total).
Diagnosis (O2): the intraday leg was gated but the overnight leg stayed fully long through every selloff, so O2 lost 38% in 2022 and 11% in 2018 (worse than buy-and-hold).
Regime e (known at the prior close) = F2 graded exposure in {-1,-1/3,+1/3,+1} (mem_ls6). Overnight basket weight a, intraday basket weight x; the rest of each leg is SPY.
(A signal known at the prior close gates the whole day, so legs only differ if the gates differ; the overnight gate is looser because that leg carries the premium.)
TRIALS
  P1 same binary gate : a = x = 1 if e > 0 else 0                       (plain close-to-close gate; baseline for the split)
  P2 split binary     : a = 1 if e > -1 else 0 ; x = 1 if e > 0 else 0   (overnight stays on unless ALL three regime signals are bearish)
  P3 graded split     : a = (e+1)/2 ; x = max(e, 0)
  P4 graded + short   : a = (e+1)/2 ; x = e (basket SHORT intraday when e < 0, SPY long the whole leg then; SPY = 1 - max(x,0) otherwise)
Costs: 2 bps per leg on name-weight churn once a day plus 2 bps x turnover at the open and at the close for every switch between the overnight and intraday positions.
MAIN TEST (AI-era 2022-11-22 to latest) PASS: Sharpe >= 1.4, max DD shallower than 30%, positive return in each FULL calendar year (2023, 2024, 2025) and in 2026 to date
(the 5-week 2022 stub is excluded, correcting round 8), Sharpe >= 1.0 in BOTH halves (2022-11-22..2024-06-30, 2024-07-01..latest).
BEAR-PROTECTION CHECK (advancers only, 2011-01-03..2022-11-21; touched earlier by peeks, so sanity only): Sharpe >= SPY's, max DD shallower than EW18 buy-and-hold's,
and the 2022 calendar-year return better than EW18's. References: O2, SPY, EW18, F4."""
import numpy as np
import pandas as pd

COST = 2e-4
src = open("mem_ls6.py").read().split("DISC, HOLD =")[0]; ns = {}; exec(src, ns)
R, RS, EW, TR6, eF, w, avail, UNI = ns["R"], ns["RS"], ns["EW"], ns["TR"], ns["eF"], ns["w"], ns["avail"], ns["UNI"]
US = RS.index
O = pd.read_parquet("data/open.parquet")[UNI].reindex(US); C = pd.read_parquet("data/close.parquet")[UNI].reindex(US)
night = (w * (O / C.shift(1) - 1).fillna(0)).sum(axis=1); day = (w * (C / O - 1).fillna(0)).sum(axis=1)
so, sc = pd.read_parquet("data/mem_open.parquet")["SPY"].reindex(US), pd.read_parquet("data/mem_close.parquet")["SPY"].reindex(US)
spy_day = (sc / so - 1).fillna(0); spy_night = (so / sc.shift(1) - 1).fillna(0)
ok = avail.sum(axis=1) >= 8
wturn = w.diff().abs().sum(axis=1).fillna(0) * COST
e = eF.reindex(US).fillna(0.0)

def build(a, x):
    a, x = a.reindex(US).fillna(0.0), x.reindex(US).fillna(0.0)
    s_a = 1 - a                                                        # SPY weight overnight
    s_x = 1 - x.clip(lower=0)                                          # SPY weight intraday (=1 when basket is short)
    gross = (1 + a * night + s_a * spy_night) * (1 + x * day + s_x * spy_day) - 1
    t_open = (x - a).abs() + (s_x - s_a).abs()                         # switch overnight -> intraday position
    a_next, s_a_next = a.shift(-1).fillna(a), s_a.shift(-1).fillna(s_a)
    t_close = (a_next - x).abs() + (s_a_next - s_x).abs()              # switch intraday -> next overnight position
    return (gross - COST * (t_open + t_close) - wturn).where(ok).dropna()

b = lambda c: c.astype(float)
p1 = build(b(e > 0), b(e > 0)); p2 = build(b(e > -0.999), b(e > 0))
p3 = build((e + 1) / 2, e.clip(lower=0)); p4 = build((e + 1) / 2, e)
TR = {"P1 same binary gate": p1, "P2 split binary": p2, "P3 graded split": p3, "P4 graded + short": p4}
o2 = pd.read_pickle("mem_ls8_rets.pkl")["O2 binary swap"]
REF = {"O2 (ref)": o2, "SPY": RS, "EW18 buy&hold": EW, "F4 (ref)": TR6["F4 fast + spread"][0]}

def stat(r, a, b_=None):
    r = r.loc[a:b_].dropna(); nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), cagr=nav.iloc[-1] ** (252 / len(r)) - 1, dd=(nav / nav.cummax() - 1).min(), beta=np.cov(r, s)[0, 1] / s.var())
W0, MID = "2022-11-22", "2024-06-30"
yr = lambda r, a=W0: r.loc[a:].groupby(r.loc[a:].index.year).apply(lambda x: (1 + x).prod() - 1)
print(f"MAIN TEST {W0} to latest")
adv = []
for k, r in {**TR, **REF}.items():
    a, h1, h2 = stat(r, W0), stat(r, W0, MID), stat(r, "2024-07-01"); tag = ""
    if k in TR:
        y = yr(r); full = y.drop(2022, errors="ignore")
        ok_ = a["sharpe"] >= 1.4 and a["dd"] > -0.30 and (full > 0).all() and h1["sharpe"] >= 1.0 and h2["sharpe"] >= 1.0
        if ok_: adv.append(k)
        tag = " | " + ("PASS-main" if ok_ else "fail")
    print(f"  {k:22s} Sharpe {a['sharpe']:+.2f} CAGR {a['cagr']:+.1%} DD {a['dd']:.0%} beta {a['beta']:+.2f} | halves {h1['sharpe']:+.2f} / {h2['sharpe']:+.2f}{tag}")
print("\n  calendar-year returns in the window (2022 = 5-week stub)\n" + pd.DataFrame({k: yr(r) for k, r in {**TR, **REF}.items()}).round(3).T.to_string())
if adv:
    a0, b0 = "2011-01-03", "2022-11-21"; sp, ew = stat(RS, a0, b0), stat(EW, a0, b0)
    y_ew = (1 + EW.loc["2022-01-01":b0]).prod() - 1
    print(f"\nBEAR-PROTECTION CHECK {a0}..{b0} (sanity only). SPY Sharpe {sp['sharpe']:+.2f}; EW18 DD {ew['dd']:.0%}, 2022 {y_ew:+.1%}")
    for k in adv:
        s = stat(TR[k], a0, b0); y22 = (1 + TR[k].loc["2022-01-01":b0]).prod() - 1
        print(f"  {k:22s} Sharpe {s['sharpe']:+.2f} CAGR {s['cagr']:+.1%} DD {s['dd']:.0%} 2022 {y22:+.1%} | {'PASS' if s['sharpe']>=sp['sharpe'] and s['dd']>ew['dd'] and y22>y_ew else 'FAIL'}")
else:
    print("\nNo variant passed the main test; pre-AI window not examined.")
pd.DataFrame(TR).to_pickle("mem_ls9_rets.pkl")
