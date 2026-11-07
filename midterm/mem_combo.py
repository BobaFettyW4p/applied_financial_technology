"""Combination candidates, declared before running (8 trials). Positions are split into a night leg
(close t-1 -> open t) and a day leg (open t -> close t); costs are paid on every position change at each boundary."""
import numpy as np
import pandas as pd
from mem_lab import *

BASKET = ["MU", "WDC", "STX"]
TREND = {t: (C[t] > C[t].rolling(100).mean()).astype(float) for t in BASKET}
names = ["SKhynix", "Samsung", "Nanya", "Winbond", "MU", "WDC", "STX"]
BREADTH = ((C[names] > C[names].rolling(50).mean()).mean(axis=1) >= 0.6).astype(float)   # theme state at close
VOL = R[BASKET].mean(axis=1).rolling(30).std() * np.sqrt(252)
SCALE = (0.35 / VOL).clip(0, 1.5)

def legs(night, day, tgt, scale=None):
    """night[t], day[t]: position held over night_t / day_t (both decided with info up to close t-1 via shift(1) of state)."""
    n, d = night.reindex(US).fillna(0), day.reindex(US).fillna(0)
    if scale is not None:
        s = scale.shift(1).reindex(US).fillna(0); n, d = n * s, d * s
    gross = n * GAP[tgt] + d * OC[tgt]
    seq = pd.concat([n, d], axis=1).values.reshape(-1)                       # n0,d0,n1,d1,...
    chg = np.abs(np.diff(np.concatenate([[0.0], seq])))
    cost = pd.Series(chg.reshape(-1, 2).sum(axis=1) * COST, index=US)
    return (gross - cost).dropna()

one = lambda: pd.Series(1.0, index=US)
sh = lambda x: x.shift(1)                      # state known at the prior close
def avg(fn): return pd.concat([fn(t) for t in BASKET], axis=1).mean(axis=1)

K2 = []
def cand(name, thesis):
    def deco(fn): K2.append((name, "combo", thesis, fn)); return fn
    return deco

@cand("night_x_trend_MU", "Own MU overnight only while its trend is up")
def _(): return legs(sh(TREND["MU"]), 0 * one(), "MU")

@cand("night_x_breadth_MU", "Own MU overnight only while the memory theme is healthy")
def _(): return legs(sh(BREADTH), 0 * one(), "MU")

@cand("night_always_day_breadth_MU", "Overnight leg always on; add the intraday leg only when the theme is healthy")
def _(): return legs(one(), sh(BREADTH), "MU")

@cand("night_basket", "Does the overnight effect generalize to WDC and STX? (equal-weight, ungated)")
def _(): return avg(lambda t: legs(one(), 0 * one(), t))

@cand("night_x_trend_basket", "Basket overnight, each name gated by its own trend")
def _(): return avg(lambda t: legs(sh(TREND[t]), 0 * one(), t))

@cand("night_always_day_breadth_basket", "Basket: overnight always, intraday only in healthy-theme regimes")
def _(): return avg(lambda t: legs(one(), sh(BREADTH), t))

@cand("night_always_day_breadth_basket_vt", "Same as above, scaled to 35% target vol (cap 1.5x)")
def _(): return avg(lambda t: legs(one(), sh(BREADTH), t, SCALE))

@cand("full_x_trend_x_breadth_basket", "Hold full-time only when own trend up AND theme healthy, else nothing")
def _(): return avg(lambda t: legs(sh(TREND[t] * BREADTH), sh(TREND[t] * BREADTH), t))
