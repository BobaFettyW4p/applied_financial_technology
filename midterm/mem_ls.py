"""Long/short, SPY-neutral rules, declared before running (6 new trials; ~57 total).
DISCOVERY = 2021-01-01 to latest (includes the 2022 bear). HOLD-OUT = 2011-2020, ONE look, advancers only (code gates it).
Universe: 18 names (software bucket removed): memory MU WDC STX SNDK | chips NVDA AVGO AMD | hyperscale AMZN GOOGL MSFT META ORCL IBM
  | infra DELL ANET VRT EQIX CEG. A name is tradable after 200 days of history. Signals use the prior close.
Construction: capital fully deployed in the stock legs (long leg weights sum to 1, short leg to -1, L5 is one signed 1/7 sleeve), then a SPY
  overlay sets portfolio beta to ~0 (trailing 120d betas, lagged). Costs 2 bps per leg on all turnover incl. the hedge. No cash return is
  credited, so numbers are the long/short spread, not total return vs a T-bill.
TRIALS
  L1 trend sign    : long names above 100d SMA, short names below; each leg equal weight (empty leg = SPY hedge only). daily
  L2 rel momentum  : monthly, long top 5 / short bottom 5 by 126d return
  L3 theme-neutral : monthly, within each theme long the better half and short the worse half by 126d return
  L4 infra fade    : weekly, among DELL ANET VRT EQIX CEG long the 2 worst / short the 2 best prior-5-day returns
  L5 hyperscale lead: daily, sign of hyperscale basket's last-2-day SPY-residual return; long (short) the 7 chip+memory names
  L6 combo         : equal capital in L2, L4, L5 (L1/L3 excluded as the combo uses the research-supported legs only)
PASS RULE (discovery): net Sharpe >= 0.5, max drawdown shallower than 30%, |beta| < 0.15, positive 2022, and positive Sharpe in >= 4 of 6 calendar years.
HOLD-OUT RULE (advancers only): Sharpe >= 0.3 and max drawdown shallower than 35%."""
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
sma100 = P.rolling(100).mean(); trend_up = (P > sma100).shift(1).fillna(False).astype(bool)
ok_sma = sma100.notna().shift(1).fillna(False).astype(bool)
mom126 = (P.pct_change(126).sub(RS.rolling(126).apply(lambda x: np.prod(1 + x) - 1, raw=True), axis=0)).shift(1)
ret5 = P.pct_change(5).shift(1)
roll_beta = R.rolling(120).cov(RS).div(RS.rolling(120).var(), axis=0).shift(1)

def first_of(idx, freq):
    m = pd.Series(idx.to_period(freq), index=idx); return (m != m.shift(1)).values

def hold(rows):                                    # dict date -> {name: weight}; carry forward
    return pd.DataFrame(rows).T.reindex(columns=UNI).fillna(0.0).reindex(US).ffill().fillna(0.0)

def legs(longs, shorts):
    w = {}
    for t in longs: w[t] = w.get(t, 0) + 1.0 / len(longs)
    for t in shorts: w[t] = w.get(t, 0) - 1.0 / len(shorts)
    return w

def finish(W):
    hedge = -(W * roll_beta.fillna(1.0)).sum(axis=1)
    gross = (W * R.fillna(0)).sum(axis=1) + hedge * RS.fillna(0)
    turn = W.diff().abs().sum(axis=1) + hedge.diff().abs()
    r = gross - COST * turn.fillna(0)
    return r.where(avail.sum(axis=1) >= 8).dropna(), W, hedge

def L1():
    rows = {}
    for d in US:
        a = [t for t in UNI if avail.at[d, t] and ok_sma.at[d, t]]
        lo = [t for t in a if trend_up.at[d, t]]; sh = [t for t in a if not trend_up.at[d, t]]
        w = {}
        if lo: w.update({t: 1.0 / len(lo) for t in lo})
        if sh: w.update({t: -1.0 / len(sh) for t in sh})
        rows[d] = w
    return finish(hold(rows))

def monthly(fn):
    rows = {}
    for d in US[first_of(US, "M")]: rows[d] = fn(d)
    return finish(hold(rows))

def L2():
    def f(d):
        a = [t for t in UNI if avail.at[d, t] and not np.isnan(mom126.at[d, t])]
        if len(a) < 12: return {}
        s = sorted(a, key=lambda t: -mom126.at[d, t]); return legs(s[:5], s[-5:])
    return monthly(f)

def L3():
    def f(d):
        lo, sh = [], []
        for g in TH.values():
            a = [t for t in g if avail.at[d, t] and not np.isnan(mom126.at[d, t])]
            s = sorted(a, key=lambda t: -mom126.at[d, t]); k = len(s) // 2
            lo += s[:k]; sh += s[len(s) - k:]
        return legs(lo, sh) if lo and sh else {}
    return monthly(f)

def L4():
    rows = {}
    for d in US[first_of(US, "W")]:
        a = [t for t in TH["infra"] if avail.at[d, t] and not np.isnan(ret5.at[d, t])]
        if len(a) < 4: rows[d] = {}; continue
        s = sorted(a, key=lambda t: ret5.at[d, t]); rows[d] = legs(s[:2], s[-2:])
    return finish(hold(rows))

def L5():
    hres = (R[TH["hyper"]].sub(RS, axis=0)).mean(axis=1)
    sig = np.sign(((1 + hres).rolling(2).apply(np.prod, raw=True) - 1)).shift(1).fillna(0)
    tgt = TH["chips"] + TH["memory"]
    a = avail[tgt].astype(float); w = a.div(a.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    W = pd.DataFrame(0.0, index=US, columns=UNI); W[tgt] = w.mul(sig, axis=0)
    return finish(W)

def combo(parts):
    r = pd.concat([p[0] for p in parts], axis=1).dropna().mean(axis=1)
    W = sum(p[1].reindex(US).fillna(0) for p in parts) / len(parts)
    h = sum(p[2].reindex(US).fillna(0) for p in parts) / len(parts)
    return r, W, h

def stat(r, a, b):
    r = r.loc[a:b].dropna(); nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    yr = r.groupby(r.index.year).apply(lambda x: x.mean() / x.std() * np.sqrt(252) if len(x) > 40 else np.nan)
    ret_y = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), ann=r.mean() * 252, dd=(nav / nav.cummax() - 1).min(),
                beta=np.cov(r, s)[0, 1] / s.var(), yr=yr, ret_y=ret_y)

r1, r2, r3, r4, r5 = L1(), L2(), L3(), L4(), L5()
TR = {"L1 trend sign": r1, "L2 rel momentum": r2, "L3 theme-neutral": r3, "L4 infra fade": r4, "L5 hyper-lead": r5, "L6 combo L2+L4+L5": combo([r2, r4, r5])}
DISC, HOLD = ("2021-01-01", "2026-11-02"), ("2011-01-01", "2020-12-31")
out, adv = {}, []
print("DISCOVERY 2021-01 to latest (beta-neutral long/short spread, net of costs)")
for k, (r, W, h) in TR.items():
    s = stat(r, *DISC)
    ok = s["sharpe"] >= 0.5 and s["dd"] > -0.30 and abs(s["beta"]) < 0.15 and s["ret_y"].get(2022, -1) > 0 and (s["yr"] > 0).sum() >= 4
    if ok: adv.append(k)
    print(f"  {k:20s} Sharpe {s['sharpe']:+.2f} ann {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | 2022 {s['ret_y'].get(2022, np.nan):+.1%} | "
          f"yrs Sharpe>0: {(s['yr']>0).sum()}/{s['yr'].notna().sum()} | {'ADVANCE' if ok else 'fail'}")
    out[k] = dict(disc={a: round(float(b), 4) for a, b in s.items() if a not in ("yr", "ret_y")}, advance=bool(ok))
print("\n  yearly returns:\n" + pd.DataFrame({k: stat(v[0], *DISC)["ret_y"] for k, v in TR.items()}).round(3).to_string())
if adv:
    print("\nHOLD-OUT 2011-2020 (one look, advancers only)")
    for k in adv:
        s = stat(TR[k][0], *HOLD); ok = s["sharpe"] >= 0.3 and s["dd"] > -0.35
        print(f"  {k:20s} Sharpe {s['sharpe']:+.2f} ann {s['ann']:+.1%} DD {s['dd']:.0%} beta {s['beta']:+.2f} | {'PASS' if ok else 'FAIL'}")
        out[k]["hold"] = {a: round(float(b), 4) for a, b in s.items() if a not in ("yr", "ret_y")}; out[k]["hold_pass"] = ok
else:
    print("\nNo variant advanced; hold-out not examined.")
json.dump(out, open("mem_ls_results.json", "w"), indent=1)
pd.DataFrame({k: v[0] for k, v in TR.items()}).to_pickle("mem_ls_rets.pkl")
