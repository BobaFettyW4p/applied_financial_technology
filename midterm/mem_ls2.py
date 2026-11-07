"""Redesign round 2, declared before running (4 new trials; ~61 total). Same universe, costs, beta-neutral SPY overlay, windows and PASS /
HOLD-OUT rules as mem_ls.py (unchanged: Sharpe>=0.5, DD<30%, |beta|<0.15, 2022>0, >=4/6 positive-Sharpe years; hold-out Sharpe>=0.3, DD<35%).
Design changes, each tied to a diagnosis from round 1:
  * Inverse-volatility (60d) weights inside each leg: round-1 drawdowns came from a few very volatile names (squeezes on shorts).
  * Shorts need CONFLUENCE (below 100d SMA AND bottom 40% of 126d relative momentum); longs the mirror. No forced equal-size legs: if no
    name qualifies the leg is empty and only the SPY hedge remains.  (user: short only when confident)
  * Group-level relationship rule instead of single-pair noise: memory basket vs hyperscaler basket relative strength trends (research C).
TRIALS
  M1 memory-vs-hyperscaler spread: long memory basket / short hyperscaler basket when their ratio is above its 100d SMA, reverse below. daily
  M2 confluence long/short: weekly, inverse-vol weights, rules above, whole 18-name universe
  M3 combo: equal capital M1 + M2
  M4 control: round-1 L2 (top5/bottom5 by 126d momentum, monthly) with inverse-vol weights only -- does vol weighting alone fix drawdown?"""
import json
import numpy as np
import pandas as pd

COST = 2e-4
close = pd.read_parquet("data/close.parquet")
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna(); US = spy.index; RS = spy.pct_change()
TH = {"memory": ["MU", "WDC", "STX", "SNDK"], "chips": ["NVDA", "AVGO", "AMD"], "hyper": ["AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM"],
      "infra": ["DELL", "ANET", "VRT", "EQIX", "CEG"]}
UNI = [t for v in TH.values() for t in v]
P = close[UNI].reindex(US).ffill(); R = P.pct_change()
avail = (P.notna().rolling(200).sum() >= 200).shift(1).fillna(False).astype(bool)
trend_up = (P > P.rolling(100).mean()).shift(1).fillna(False).astype(bool)
spy126 = (1 + RS).rolling(126).apply(np.prod, raw=True) - 1
mom126 = (P.pct_change(126).sub(spy126, axis=0)).shift(1)
vol60 = R.rolling(60).std().shift(1)
roll_beta = R.rolling(120).cov(RS).div(RS.rolling(120).var(), axis=0).shift(1)

def first_of(idx, freq):
    m = pd.Series(idx.to_period(freq), index=idx); return (m != m.shift(1)).values

def hold(rows):
    return pd.DataFrame(rows).T.reindex(columns=UNI).fillna(0.0).reindex(US).ffill().fillna(0.0)

def ivw(names, d, sign):
    if not names: return {}
    iv = {t: 1.0 / vol60.at[d, t] for t in names}; s = sum(iv.values())
    return {t: sign * v / s for t, v in iv.items()}

def finish(W):
    hedge = -(W * roll_beta.fillna(1.0)).sum(axis=1)
    gross = (W * R.fillna(0)).sum(axis=1) + hedge * RS.fillna(0)
    turn = W.diff().abs().sum(axis=1) + hedge.diff().abs()
    return (gross - COST * turn.fillna(0)).where(avail.sum(axis=1) >= 8).dropna(), W, hedge

def M1():
    def basket(g):
        a = avail[g].astype(float); return a.div(a.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    wm, wh = basket(TH["memory"]), basket(TH["hyper"])
    rm = (wm * R[TH["memory"]].fillna(0)).sum(axis=1); rh = (wh * R[TH["hyper"]].fillna(0)).sum(axis=1)
    ratio = (1 + rm).cumprod() / (1 + rh).cumprod()
    sig = np.where((ratio > ratio.rolling(100).mean()).shift(1).fillna(False), 1.0, -1.0)
    sig = pd.Series(sig, index=US).where(ratio.rolling(100).mean().shift(1).notna(), 0.0)
    W = pd.DataFrame(0.0, index=US, columns=UNI)
    W[TH["memory"]] = wm.mul(sig, axis=0); W[TH["hyper"]] = -wh.mul(sig, axis=0)
    return finish(W)

def M2():
    rows = {}
    for d in US[first_of(US, "W")]:
        a = [t for t in UNI if avail.at[d, t] and not np.isnan(mom126.at[d, t]) and not np.isnan(vol60.at[d, t])]
        if len(a) < 12: rows[d] = {}; continue
        rk = pd.Series({t: mom126.at[d, t] for t in a}).rank(pct=True)
        lo = [t for t in a if trend_up.at[d, t] and rk[t] >= 0.6]; sh = [t for t in a if (not trend_up.at[d, t]) and rk[t] <= 0.4]
        rows[d] = {**ivw(lo, d, 1), **ivw(sh, d, -1)}
    return finish(hold(rows))

def M4():
    rows = {}
    for d in US[first_of(US, "M")]:
        a = [t for t in UNI if avail.at[d, t] and not np.isnan(mom126.at[d, t]) and not np.isnan(vol60.at[d, t])]
        if len(a) < 12: rows[d] = {}; continue
        s = sorted(a, key=lambda t: -mom126.at[d, t]); rows[d] = {**ivw(s[:5], d, 1), **ivw(s[-5:], d, -1)}
    return finish(hold(rows))

def combo(parts):
    r = pd.concat([p[0] for p in parts], axis=1).dropna().mean(axis=1)
    return r, sum(p[1].reindex(US).fillna(0) for p in parts) / len(parts), sum(p[2].reindex(US).fillna(0) for p in parts) / len(parts)

def stat(r, a, b):
    r = r.loc[a:b].dropna(); nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    yr = r.groupby(r.index.year).apply(lambda x: x.mean() / x.std() * np.sqrt(252) if len(x) > 40 else np.nan)
    ret_y = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), ann=r.mean() * 252, dd=(nav / nav.cummax() - 1).min(),
                beta=np.cov(r, s)[0, 1] / s.var(), yr=yr, ret_y=ret_y)

m1, m2, m4 = M1(), M2(), M4()
TR = {"M1 mem-vs-hyper spread": m1, "M2 confluence L/S": m2, "M3 combo M1+M2": combo([m1, m2]), "M4 control invvol L2": m4}
DISC, HOLD = ("2021-01-01", "2026-11-02"), ("2011-01-01", "2020-12-31")
out, adv = {}, []
print("DISCOVERY 2021-01 to latest (beta-neutral spread, net of costs)")
for k, (r, W, h) in TR.items():
    s = stat(r, *DISC)
    ok = s["sharpe"] >= 0.5 and s["dd"] > -0.30 and abs(s["beta"]) < 0.15 and s["ret_y"].get(2022, -1) > 0 and (s["yr"] > 0).sum() >= 4
    if ok: adv.append(k)
    print(f"  {k:24s} Sharpe {s['sharpe']:+.2f} ann {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | 2022 {s['ret_y'].get(2022, np.nan):+.1%} | "
          f"yrs>0: {(s['yr']>0).sum()}/{s['yr'].notna().sum()} | avg gross {W.abs().sum(axis=1).loc[DISC[0]:].mean():.2f} | {'ADVANCE' if ok else 'fail'}")
    out[k] = dict(disc={a: round(float(b), 4) for a, b in s.items() if a not in ("yr", "ret_y")}, advance=bool(ok))
print("\n  yearly returns:\n" + pd.DataFrame({k: stat(v[0], *DISC)["ret_y"] for k, v in TR.items()}).round(3).to_string())
if adv:
    print("\nHOLD-OUT 2011-2020 (one look, advancers only)")
    for k in adv:
        s = stat(TR[k][0], *HOLD); ok = s["sharpe"] >= 0.3 and s["dd"] > -0.35
        print(f"  {k:24s} Sharpe {s['sharpe']:+.2f} ann {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | {'PASS' if ok else 'FAIL'}")
        out[k]["hold"] = {a: round(float(b), 4) for a, b in s.items() if a not in ("yr", "ret_y")}; out[k]["hold_pass"] = bool(ok)
else:
    print("\nNo variant advanced; hold-out not examined.")
json.dump(out, open("mem_ls2_results.json", "w"), indent=1)
pd.DataFrame({k: v[0] for k, v in TR.items()}).to_pickle("mem_ls2_rets.pkl")
