"""Pre-declared memory-theme candidates (all counted as trials)."""
import numpy as np
import pandas as pd
from mem_lab import *

K = []   # (name, family, thesis, returns_fn)
def cand(name, family, thesis):
    def deco(fn): K.append((name, family, thesis, fn)); return fn
    return deco

BASKET = ["MU", "WDC", "STX"]
def basket(fn): return pd.concat([fn(t) for t in BASKET], axis=1).mean(axis=1)

# ---------------- Asia -> US open-to-close (needs Asia data at 9:30 ET) ----------------
@cand("asia_oc_MU_ls", "asia-lead", "Asia memory leaders close hours before the US open; the open only partly absorbs it, so go with the Asia move open-to-close")
def _(): return intraday(np.sign(A), "MU")

@cand("asia_oc_MU_long", "asia-lead", "Same, long-only: buy MU at the open only when Asia memory was up")
def _(): return intraday((A > 0).astype(float), "MU")

@cand("asia_oc_MU_thr", "asia-lead", "Trade only when the Asia move is large (|z|>1): costs matter, conviction filter")
def _(): return intraday(np.sign(A).where(A.abs() > 1, 0), "MU")

@cand("asia_oc_sk_MU", "asia-lead", "SK hynix alone: the pure-play DRAM peer, long/short MU")
def _(): return intraday(np.sign(A_sk), "MU")

@cand("asia_oc_basket", "asia-lead", "Slower-reacting US storage names (WDC, STX) may absorb Asia news less at the open than MU")
def _(): return basket(lambda t: intraday(np.sign(A), t))

@cand("asia_unabsorbed_MU", "asia-lead", "Trade the gap shortfall: Asia-implied gap minus MU's actual gap (what the open failed to price)")
def _():
    b = beta_roll(GAP["MU"].reindex(US), A)
    return intraday(np.sign(b * A - GAP["MU"].reindex(US)), "MU")

# ---------------- US-only (QuantConnect-feasible) ----------------
@cand("gap_continue_MU", "us-gap", "Large gaps in MU continue intraday (gap-and-go)")
def _(): return intraday(np.sign(GAP["MU"].reindex(US)).where(GAP["MU"].reindex(US).abs() > 0.01, 0), "MU")

@cand("gap_fade_MU", "us-gap", "Large gaps in MU overreact and fade intraday")
def _(): return intraday(-np.sign(GAP["MU"].reindex(US)).where(GAP["MU"].reindex(US).abs() > 0.01, 0), "MU")

@cand("gap_basket_continue", "us-gap", "Memory basket gap (MU, WDC, STX) continues in each name: theme-wide gap is information")
def _():
    g = GAP[BASKET].reindex(US).mean(axis=1)
    return basket(lambda t: intraday(np.sign(g).where(g.abs() > 0.01, 0), t))

@cand("laggard_gap", "us-gap", "WDC/STX gap less than MU's: the laggards catch up intraday toward the leader")
def _():
    g = GAP.reindex(US)
    parts = [intraday(np.sign(g["MU"] - g[t]).where((g["MU"] - g[t]).abs() > 0.01, 0), t) for t in ("WDC", "STX")]
    return pd.concat(parts, axis=1).mean(axis=1)

@cand("overnight_hold_MU", "us-gap", "Own the overnight only: MU earns its premium close->open (institutional flow)")
def _(): return (GAP["MU"].reindex(US) - 2 * COST).dropna()

@cand("intraday_only_MU", "us-gap", "Own the intraday only (mirror): premium open->close")
def _(): return (OC["MU"].reindex(US) - 2 * COST).dropna()

# ---------------- cross-name relative value among US memory names ----------------
@cand("peer_rev_5d", "us-relative", "5-day reversal within the memory theme: laggards vs leaders vs the theme average, daily hold")
def _():
    r5 = C[["MU", "WDC", "STX"]].pct_change(5).reindex(US)
    dev = r5.sub(r5.mean(axis=1), axis=0)
    w = (-dev).div(dev.abs().sum(axis=1), axis=0).fillna(0)
    return pd.concat([daily_hold(w[t], t) for t in w.columns], axis=1).sum(axis=1)

@cand("peer_mom_21d", "us-relative", "21-day relative momentum within the theme (leader keeps leading)")
def _():
    r = C[["MU", "WDC", "STX"]].pct_change(21).reindex(US)
    dev = r.sub(r.mean(axis=1), axis=0)
    w = dev.div(dev.abs().sum(axis=1), axis=0).fillna(0)
    return pd.concat([daily_hold(w[t], t) for t in w.columns], axis=1).sum(axis=1)

# ---------------- theme timing (own the theme only in good regimes) ----------------
@cand("MU_trend100", "timing", "Hold MU only above its 100-day average: cyclicals trend")
def _(): return daily_hold((C["MU"] > C["MU"].rolling(100).mean()).astype(float), "MU")

@cand("theme_breadth", "timing", "Hold MU when most of the theme (SKhynix, Samsung, Nanya, Winbond, MU, WDC, STX) is above its 50d average")
def _():
    names = ["SKhynix", "Samsung", "Nanya", "Winbond", "MU", "WDC", "STX"]
    br = (C[names] > C[names].rolling(50).mean()).mean(axis=1).reindex(US)
    return daily_hold((br >= 0.6).astype(float), "MU")

@cand("MU_volscaled", "timing", "Hold MU scaled to 40% target vol: it's a 48%-vol cyclical")
def _():
    v = R["MU"].rolling(30).std() * np.sqrt(252)
    return daily_hold((0.40 / v).clip(0, 1.5).shift(0), "MU")

@cand("MU_buyhold", "benchmark", "Buy and hold MU (benchmark, not a candidate)")
def _(): return daily_hold(pd.Series(1.0, index=US), "MU")

@cand("theme_buyhold", "benchmark", "Equal-weight buy-and-hold MU/WDC/STX (benchmark)")
def _(): return basket(lambda t: daily_hold(pd.Series(1.0, index=US), t))
