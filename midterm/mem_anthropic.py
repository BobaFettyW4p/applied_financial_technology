"""Anthropic-ecosystem universe test, declared before running (6 new trials; ~51 total after the earlier 45).

UNIVERSE (25 US names, from the Anthropic S-1 plus AI-demand peers; chosen with hindsight, survivors only):
  cloud/compute partners & peers : AMZN GOOGL MSFT META ORCL IBM
  chip / component suppliers     : NVDA AVGO AMD  + memory core MU WDC STX SNDK
  distribution / software / SIs  : CRM NOW ADBE INTU PLTR DDOG ACN
  AI infrastructure              : DELL ANET VRT EQIX CEG
A name joins the book once it has 200 trading days of history (PLTR, DDOG, VRT, CEG, SNDK are short).

ALWAYS INVESTED: every rule below sums to 100% gross; whatever is not in a stock sits in SPY (2 bps per leg on turnover).
Signals use the prior close (no look-ahead).

TRIALS
  S1 slot trend   : equal slots; slot holds stock if close > its 100d SMA else SPY   (the existing memory rule, 25 names)
  S2 score-weight : stock weight = (#SMA50/100/200 above)/3 per slot, rest SPY   (graded exposure)
  S3 top-8 momentum: monthly, among names above 100d SMA take the 8 with best 126d return, 1/8 each; empty slots SPY
  S4 memory tilt  : S1 but MU/WDC/STX/SNDK slots count 2x
  S5 memory regime: if memory basket (MU,WDC,STX) is above its 100d SMA run S3, else 100% SPY
  S6 memory-led top-8: S3 where memory names that qualify are always included, other 8-len slots filled by momentum (ties to the memory idea)
References: R0 SPY, R1 equal-weight buy-and-hold of the 25 (daily rebalanced), R2 old six-stock memory basket (S1 rule).

PASS RULE (discovery 2011-2020 only): advance to hold-out if Sharpe >= max(R0, R1) Sharpe and max drawdown shallower than R1's.
Hold-out 2021-01 to 2026-10: ONE look at the advancing variants (all shown for completeness but only advancers count).
Also reported: average % of book in single stocks (not SPY), beta to SPY, top name's share of stock-specific P&L."""
import json
import numpy as np
import pandas as pd

COST, DISC_END, END = 2e-4, "2020-12-31", "2026-11-02"
close = pd.read_parquet("data/close.parquet")
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna(); US = spy.index; RS = spy.pct_change()
MEM = ["MU", "WDC", "STX", "SNDK"]
UNI = ["AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM", "NVDA", "AVGO", "AMD", "MU", "WDC", "STX", "SNDK",
       "CRM", "NOW", "ADBE", "INTU", "PLTR", "DDOG", "ACN", "DELL", "ANET", "VRT", "EQIX", "CEG"]
SIX = ["MU", "WDC", "STX", "LRCX", "AMAT", "KLAC"]
miss = [t for t in UNI + SIX if t not in close]; assert not miss, miss
P = close[sorted(set(UNI + SIX))].reindex(US).ffill()          # ffill only fills holidays/gaps; leading NaN stays
R = P.pct_change()
S50, S100, S200 = (P.rolling(n).mean() for n in (50, 100, 200))
avail = P.notna().rolling(200).sum().ge(200) & S200.notna()     # >= 200 days of history
avail = avail.shift(1).fillna(False).astype(bool)               # known at prior close
above = lambda S: (P > S).shift(1).fillna(False).astype(bool)   # prior-close signal
mom = P.pct_change(126).shift(1)

def to_returns(W):
    """W: stock weights (rows<=1) known before the day. Rest in SPY. Returns net daily return."""
    W = W.reindex(US).fillna(0.0)
    spy_w = 1 - W.sum(axis=1)
    gross = (W * R.reindex(columns=W.columns).fillna(0)).sum(axis=1) + spy_w * RS.fillna(0)
    turn = W.diff().abs().sum(axis=1) + spy_w.diff().abs()      # all legs traded
    return gross - COST * turn.fillna(0), W

def slots(names, weights=None):
    """equal (or relative-weight) slots over available names; return per-name slot weight."""
    names = [t for t in names]
    base = pd.DataFrame({t: (weights or {}).get(t, 1.0) for t in names}, index=US)
    a = avail[names]
    return (base * a).div((base * a).sum(axis=1).replace(0, np.nan), axis=0).fillna(0), a

def s1(names, w=None):
    slot, a = slots(names, w)
    return to_returns(slot * above(S100)[names])

def s2():
    slot, a = slots(UNI)
    score = (above(S50)[UNI].astype(float) + above(S100)[UNI] + above(S200)[UNI]) / 3
    return to_returns(slot * score)

def month_start(idx):
    m = pd.Series(idx.to_period("M"), index=idx)
    return m != m.shift(1)

def topk(names, k=8, force=()):
    ms = month_start(US)
    rows = {}
    for d in US[ms.values]:
        ok = [t for t in names if avail.at[d, t] and above(S100).at[d, t] and not np.isnan(mom.at[d, t])]
        pick = [t for t in force if t in ok]
        rest = sorted([t for t in ok if t not in pick], key=lambda t: -mom.at[d, t])
        pick = (pick + rest)[:k]
        rows[d] = {t: 1.0 / k for t in pick}
    W = pd.DataFrame(rows).T.reindex(columns=names).fillna(0.0).reindex(US).ffill().fillna(0.0)
    return W

def s3(): return to_returns(topk(UNI))
def s6(): return to_returns(topk(UNI, force=MEM))
def s5():
    W = topk(UNI)
    mem = P[["MU", "WDC", "STX"]].div(P[["MU", "WDC", "STX"]].iloc[0]).mean(axis=1)   # equal-weight index level (rebased)
    mem_on = (mem > mem.rolling(100).mean()).shift(1).fillna(False).astype(float)
    return to_returns(W.mul(mem_on, axis=0))

def ew_bh():
    a = avail[UNI]; w = a.div(a.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    ret = (w * R[UNI].fillna(0)).sum(axis=1) - COST * w.diff().abs().sum(axis=1).fillna(0)
    return ret.where(a.sum(axis=1) > 0)

TR = {"S1 slot trend": s1(UNI), "S2 score weight": s2(), "S3 top8 momentum": s3(), "S4 memory tilt 2x": s1(UNI, {t: 2.0 for t in MEM}),
      "S5 memory regime": s5(), "S6 memory-led top8": s6()}
REF = {"R0 SPY": (RS, None), "R1 EW buy&hold 25": (ew_bh(), None), "R2 six-memory trend": s1(SIX)}  # (returns, weights)

def stat(r, a, b):
    r = r.loc[a:b].dropna()
    nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    beta = np.cov(r, s)[0, 1] / s.var()
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), cagr=nav.iloc[-1] ** (252 / len(r)) - 1, dd=(nav / nav.cummax() - 1).min(), beta=beta)

def share_stock(W, a, b):
    return float(W.loc[a:b].sum(axis=1).mean())

def top_share(W, a, b):
    spec = (W * (R.reindex(columns=W.columns) .sub(RS, axis=0))).loc[a:b].sum()
    return spec.idxmax(), float(spec.max() / spec.sum()) if spec.sum() > 0 else float("nan")

WIN = {"DISC": ("2011-01-01", DISC_END), "HOLD": ("2021-01-01", END)}
out = {}
for w, (a, b) in WIN.items():
    print(f"\n=== {w} {a} to {b} ===")
    base = {}
    for k, v in REF.items():
        r, W = v
        st = stat(r, a, b); base[k] = st
        extra = f" | stock share {share_stock(W,a,b):.0%}" if W is not None else ""
        print(f"  {k:22s} Sharpe {st['sharpe']:.2f} CAGR {st['cagr']:+.1%} DD {st['dd']:.0%} beta {st['beta']:.2f}{extra}")
    bar = max(base["R0 SPY"]["sharpe"], base["R1 EW buy&hold 25"]["sharpe"])
    for k, (r, W) in TR.items():
        st = stat(r, a, b); top, sh = top_share(W, a, b)
        flag = ""
        if w == "DISC":
            ok = st["sharpe"] >= bar and st["dd"] > base["R1 EW buy&hold 25"]["dd"]
            flag = f" || {'ADVANCE' if ok else 'fail'} (bar Sharpe {bar:.2f}, R1 DD {base['R1 EW buy&hold 25']['dd']:.0%})"
        print(f"  {k:22s} Sharpe {st['sharpe']:.2f} CAGR {st['cagr']:+.1%} DD {st['dd']:.0%} beta {st['beta']:.2f} | stocks {share_stock(W,a,b):.0%} of book | top {top} {sh:.0%}{flag}")
        out[f"{w}|{k}"] = {**{kk: round(float(vv), 4) for kk, vv in st.items()}, "stock_share": round(share_stock(W, a, b), 3)}
json.dump(out, open("mem_anthropic_results.json", "w"), indent=1)
pd.DataFrame({k: v[0] for k, v in TR.items()}).to_pickle("mem_anthropic_rets.pkl")
