"""Round 4: composite-momentum long/short, ALWAYS in single stocks. Declared before running (4 new trials; ~69 total).
Basis: feature_study.py (2021+ only) -- theme momentum, 63d momentum and distance from 100d SMA predicted next 5/20d excess returns positively
(t ~1.5-2.4, same sign at both horizons, stronger in the second half); reversal did not. The low-vol/low-beta anomaly is NOT used (regime effect).
Same universe, costs, beta-neutral SPY overlay, windows, PASS rule (Sharpe>=0.5, DD<30%, |beta|<0.15, 2022>0, >=4/6 positive-Sharpe years)
and gated HOLD-OUT rule (2011-2020, advancers only, Sharpe>=0.3, DD<35%). Note: 2011-2020 already had one look (N2), so this is look #2.
SCORE = average of cross-sectional z-scores of: 63d return vs SPY, own-theme 63d return vs SPY, price/100d SMA - 1 (prior close).
TRIALS (weekly rebalance, dollar-neutral legs then SPY beta overlay; 100% of capital in the stock legs at all times)
  C1 score-weighted : long names with score>0 in proportion to score (leg sums to 1), short names with score<0 likewise
  C2 extremes       : long top 6 / short bottom 6 by score, equal weight
  C3 C1 + N2        : equal capital in C1 and N2 (vol-targeted memory-vs-hyperscaler spread, from mem_ls3)
  C4 C1 vol-targeted: C1 scaled by min(1, 15% / trailing 60d annualised vol of C1), lagged"""
import json
import numpy as np
import pandas as pd

COST, TARGET = 2e-4, 0.15
close = pd.read_parquet("data/close.parquet")
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna(); US = spy.index; RS = spy.pct_change()
TH = {"memory": ["MU", "WDC", "STX", "SNDK"], "chips": ["NVDA", "AVGO", "AMD"], "hyper": ["AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM"],
      "infra": ["DELL", "ANET", "VRT", "EQIX", "CEG"]}
UNI = [t for v in TH.values() for t in v]; theme_of = {t: g for g, v in TH.items() for t in v}
P = close[UNI].reindex(US).ffill(); R = P.pct_change()
avail = (P.notna().rolling(200).sum() >= 200).shift(1).fillna(False).astype(bool)
roll_beta = R.rolling(120).cov(RS).div(RS.rolling(120).var(), axis=0).shift(1)
spy63 = (1 + RS).rolling(63).apply(np.prod, raw=True) - 1
m63 = P.pct_change(63).sub(spy63, axis=0)
tm63 = pd.DataFrame({t: R[TH[theme_of[t]]].mean(axis=1) for t in UNI})
tm63 = ((1 + tm63).rolling(63).apply(np.prod, raw=True) - 1).sub(spy63, axis=0)
dist = P / P.rolling(100).mean() - 1
z = lambda df: df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1).replace(0, np.nan), axis=0)
score = ((z(m63) + z(tm63) + z(dist)) / 3).shift(1)

def first_week(idx):
    m = pd.Series(idx.to_period("W"), index=idx); return (m != m.shift(1)).values

def hold(rows): return pd.DataFrame(rows).T.reindex(columns=UNI).fillna(0.0).reindex(US).ffill().fillna(0.0)

def finish(W):
    hedge = -(W * roll_beta.fillna(1.0)).sum(axis=1)
    gross = (W * R.fillna(0)).sum(axis=1) + hedge * RS.fillna(0)
    turn = W.diff().abs().sum(axis=1) + hedge.diff().abs()
    return (gross - COST * turn.fillna(0)).where(avail.sum(axis=1) >= 12).dropna(), W, hedge

def C(kind):
    rows = {}
    for d in US[first_week(US)]:
        a = [t for t in UNI if avail.at[d, t] and not np.isnan(score.at[d, t])]
        if len(a) < 12: rows[d] = {}; continue
        s = score.loc[d, a]
        if kind == "w":
            lo, sh = s[s > 0], s[s < 0]
            w = {**{t: v / lo.sum() for t, v in lo.items()}, **{t: v / abs(sh.sum()) for t, v in sh.items()}}
        else:
            srt = s.sort_values(); w = {**{t: 1 / 6 for t in srt.index[-6:]}, **{t: -1 / 6 for t in srt.index[:6]}}
        rows[d] = w
    return finish(hold(rows))

c1, c2 = C("w"), C("x")
vol = (c1[0].rolling(60).std().shift(1) * np.sqrt(252)); sc = (TARGET / vol).clip(upper=1.0).fillna(0.0)
c4 = ((c1[0] * sc.reindex(c1[0].index)).dropna(), c1[1].mul(sc, axis=0), c1[2] * sc)
n2 = pd.read_pickle("mem_ls3_rets.pkl")["N2 vol-targeted"].dropna()
idx = c1[0].index.intersection(n2.index)
c3 = (((c1[0].loc[idx] + n2.loc[idx]) / 2), c1[1].loc[idx], c1[2].loc[idx])
TR = {"C1 score-weighted": c1, "C2 top6/bottom6": c2, "C3 C1+N2 combo": c3, "C4 C1 vol-targeted": c4}

def stat(r, a, b):
    r = r.loc[a:b].dropna(); nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    yr = r.groupby(r.index.year).apply(lambda x: x.mean() / x.std() * np.sqrt(252) if len(x) > 40 else np.nan)
    ret_y = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), ann=r.mean() * 252, dd=(nav / nav.cummax() - 1).min(),
                beta=np.cov(r, s)[0, 1] / s.var(), yr=yr, ret_y=ret_y)

DISC, HOLD = ("2021-01-01", "2026-11-02"), ("2011-01-01", "2020-12-31")
out, adv = {}, []
print("DISCOVERY 2021-01 to latest (always in single stocks; beta-neutral spread, net of costs)")
for k, (r, W, h) in TR.items():
    s = stat(r, *DISC)
    ok = s["sharpe"] >= 0.5 and s["dd"] > -0.30 and abs(s["beta"]) < 0.15 and s["ret_y"].get(2022, -1) > 0 and (s["yr"] > 0).sum() >= 4
    if ok: adv.append(k)
    print(f"  {k:20s} Sharpe {s['sharpe']:+.2f} ann {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | 2022 {s['ret_y'].get(2022, np.nan):+.1%} | "
          f"yrs>0: {(s['yr']>0).sum()}/{s['yr'].notna().sum()} | avg gross {W.abs().sum(axis=1).loc[DISC[0]:].mean():.2f} | {'ADVANCE' if ok else 'fail'}")
    out[k] = dict(disc={a: round(float(b), 4) for a, b in s.items() if a not in ("yr", "ret_y")}, advance=bool(ok))
print("\n  yearly returns:\n" + pd.DataFrame({k: stat(v[0], *DISC)["ret_y"] for k, v in TR.items()}).round(3).to_string())
if adv:
    print("\nHOLD-OUT 2011-2020 (look #2, advancers only)")
    for k in adv:
        s = stat(TR[k][0], *HOLD); ok = s["sharpe"] >= 0.3 and s["dd"] > -0.35
        print(f"  {k:20s} Sharpe {s['sharpe']:+.2f} ann {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | {'PASS' if ok else 'FAIL'}")
        out[k]["hold"] = {a: round(float(b), 4) for a, b in s.items() if a not in ("yr", "ret_y")}; out[k]["hold_pass"] = bool(ok)
else:
    print("\nNo variant advanced; hold-out not examined.")
json.dump(out, open("mem_ls4_results.json", "w"), indent=1)
pd.DataFrame({k: v[0] for k, v in TR.items()}).to_pickle("mem_ls4_rets.pkl")
