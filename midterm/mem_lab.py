"""Memory-theme strategy screen. Discovery 2011-2020; hold-out 2021+ gets one joint look for pre-declared survivors.
Daily strategies on US-listed memory names. Intraday trades enter at the open, exit at the close (5 bps per side)."""
import json
import numpy as np
import pandas as pd

D = "data/mem_%s.parquet"
CALL, OALL = pd.read_parquet(D % "close"), pd.read_parquet(D % "open")
US = CALL["MU"].dropna().index                    # master calendar = US trading days
C = CALL.ffill().reindex(US)                      # prices on the US calendar (Asian closes carried over US holidays)
O = OALL.reindex(US)
R = C.pct_change()
GAP, OC = O / C.shift(1) - 1, C / O - 1
DISC_END, COST = "2020-12-31", 2e-4
LOG, LOOKS = "mem_trials.csv", "mem_holdout.json"

ASIA = ["SKhynix", "Samsung", "Nanya", "Winbond"]
def _zret(col):
    r = CALL[col].dropna().pct_change()           # return on the stock's OWN trading calendar
    return r / r.rolling(63, min_periods=40).std().shift(1)
_z = pd.concat({a: _zret(a) for a in ASIA}, axis=1)
_zu = _z.reindex(US)                               # Asia day-t return, known before US open on day t
A = _zu.mean(axis=1).where(_zu.notna().sum(axis=1) >= 2)   # composite
A_sk = _zu["SKhynix"]

def beta_roll(y, x, w=252):
    return (y.rolling(w, min_periods=120).cov(x) / x.rolling(w, min_periods=120).var()).shift(1)

def sharpe(x): x = x.dropna(); return float(x.mean() / x.std(ddof=1) * np.sqrt(252)) if x.std() > 0 else np.nan
def tstat(x): x = x.dropna(); return float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))) if x.std() > 0 else np.nan

def intraday(pos, tgt):
    """pos known pre-open in [-1,1]; earns open->close of tgt, pays COST each side."""
    return (pos.reindex(US).fillna(0) * OC[tgt].reindex(US) - 2 * COST * pos.reindex(US).fillna(0).abs()).dropna()

def daily_hold(pos, tgt):
    """pos set at prior close, earns close->close; pays COST per unit change."""
    p = pos.reindex(US).fillna(0).shift(1).fillna(0)
    return (p * R[tgt].reindex(US) - COST * p.diff().abs().fillna(0)).dropna()

def stats(r, window):
    r = r.loc[:DISC_END] if window == "disc" else r.loc["2021-01-01":]
    act = r[r != 0]
    nav = (1 + r).cumprod()
    return dict(sharpe=sharpe(r), ann_ret=r.mean() * 252, t=tstat(r), max_dd=float((nav / nav.cummax() - 1).min()),
                active_frac=len(act) / max(len(r), 1), hit=float((act > 0).mean()) if len(act) else np.nan, days=len(r))

def log(name, family, thesis, r):
    row = dict(name=name, family=family, thesis=thesis, **stats(r, "disc"))
    df = pd.DataFrame([row])
    try:
        df = pd.concat([pd.read_csv(LOG).query("name != @name"), df])
    except FileNotFoundError: pass
    df.to_csv(LOG, index=False); return row

def holdout(names_returns):
    """Record hold-out looks. MERGES into the log (never overwrites earlier looks), so look count stays auditable."""
    try: prev = json.load(open(LOOKS))
    except FileNotFoundError: prev = {}
    new = {n: stats(r, "hold") for n, r in names_returns.items()}
    clean = lambda d: {a: (None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)) for a, v in d.items()}
    for n, d in new.items():
        prev[n] = clean(d)
    json.dump(prev, open(LOOKS, "w"), indent=1)
    return new
