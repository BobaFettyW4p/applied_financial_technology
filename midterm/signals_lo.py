"""Long-only-native ideas: avoid-the-losers composites and a core-satellite quality screen."""
import numpy as np

import signals as B1
from lab import close, volume, UNIV
from signals2 import rk, lowvol, lowbeta, mom, rev1w, h52, vsurge

ret = B1.ret
maxr = B1.monthly(-ret.rolling(21).max())
idio = B1.monthly(-B1._resid(ret, B1.mkt).rolling(63, min_periods=40).std())
dd = B1.monthly(close / close.rolling(252).max())

S = []
def sig(name, thesis):
    def deco(fn):
        S.append((name, thesis, fn)); return fn
    return deco

@sig("avoid_lottery", "Excluding lottery-like names (extreme recent up-days, high idio vol) removes the overpriced tail")
def _(): return rk(maxr) + rk(idio)

@sig("avoid_broken", "Exclude stocks that are deep below highs AND volatile: falling knives rarely recover quickly")
def _(): return rk(dd) + rk(lowvol)

@sig("avoid_laggards_lowvol", "Drop long-run losers (12-1 momentum) and high-risk names together")
def _(): return rk(mom) + rk(lowvol) + rk(maxr)

@sig("core_quality_trend", "Low beta, near highs, strong momentum: boring compounders")
def _(): return rk(lowbeta) + rk(h52) + rk(mom)

@sig("all_defensive", "Composite of every low-risk measure (low vol, beta, idio vol, max)")
def _(): return rk(lowvol) + rk(lowbeta) + rk(idio) + rk(maxr)

@sig("mom_lowvol_rev", "Momentum and low vol plus a short-term reversal tilt for entry timing")
def _(): return rk(mom) + rk(lowvol) + rk(rev1w)

@sig("liquid_winners", "Large dollar-volume names with positive momentum (capacity-friendly)")
def _(): return rk(np.log((close * volume).rolling(63, min_periods=40).mean()).loc[B1.ME]) + rk(mom)

@sig("quiet_uptrend", "Uptrend with below-average volume surge: orderly accumulation")
def _(): return rk(h52) + (1 - rk(vsurge))
