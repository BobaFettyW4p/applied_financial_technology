"""Batch 2: regime-conditional / interaction signals and market-timing overlays.

Regimes use only information known at month-end t (expanding medians, no look-ahead).
Gates are declared before looking at results; off-regime months hold no position.
"""
import numpy as np
import pandas as pd

import lab
from lab import ME, UNIV, close, volume, monthly
import signals as B1

ret, mkt = B1.ret, B1.mkt

# ---- regime state at each month-end -------------------------------------------------
r21 = (close / close.shift(21) - 1).loc[ME].where(UNIV)
DISP = r21.std(axis=1)                                         # cross-sectional dispersion
MVOL = (mkt.rolling(21).std() * np.sqrt(252)).loc[ME]          # market realized vol
MIDX = (1 + mkt.fillna(0)).cumprod()
MTREND = (MIDX.loc[ME] > MIDX.rolling(210).mean().loc[ME])     # EW index above 10m average
M24 = (MIDX / MIDX.shift(504) - 1).loc[ME]                     # trailing 24m market return
MDOWN1 = (MIDX / MIDX.shift(21) - 1).loc[ME] < 0
AVGCORR = (mkt.rolling(63).var() / ret.var().mean() if False else
           mkt.rolling(63).var().div((ret.rolling(63).var()).mean(axis=1))).loc[ME]  # ~ avg pairwise corr


def high(x, q=0.5): return x > x.expanding(12).quantile(q)
def low(x, q=0.5): return x <= x.expanding(12).quantile(q)


def gate(sig, on):
    s = sig.copy()
    s.loc[~on.reindex(s.index).fillna(False).astype(bool).values] = np.nan
    return s


def switch(a, b, on):
    s = a.copy()
    m = ~on.reindex(s.index).fillna(False).astype(bool).values
    s.loc[m] = b.loc[m]
    return s


def rk(x): return x.where(UNIV).rank(axis=1, pct=True)


rev1m = B1.monthly(-(close / close.shift(21) - 1))
rev1w = B1.monthly(-(close / close.shift(5) - 1))
mom = B1.monthly(close.shift(21) / close.shift(252) - 1)
resid_rev = B1.monthly(-B1._resid(ret, mkt).rolling(21).sum())
vsurge = B1.monthly(volume.rolling(5).mean() / volume.rolling(126, min_periods=80).mean())
lowvol = B1.monthly(-ret.rolling(126, min_periods=80).std())
lowbeta = B1.monthly(-B1._roll_beta(ret, mkt, 252))
ovn = B1.monthly(np.log(B1.open_ / close.shift(1)).rolling(126, min_periods=80).sum())
h52 = B1.monthly(close / close.rolling(252).max())

S2 = []
def sig(name, family, thesis):
    def deco(fn):
        S2.append((name, family, thesis, fn)); return fn
    return deco

# ---- state-gated reversal -----------------------------------------------------------
@sig("rev_high_disp", "conditional", "Reversal pays when cross-sectional dispersion is high: more mispricing to correct")
def _(): return gate(rev1m, high(DISP))

@sig("rev_after_mkt_down", "conditional", "Liquidity provision pays after market down months (inventory risk premium)")
def _(): return gate(rev1m, MDOWN1)

@sig("rev_high_mktvol", "conditional", "Reversal premium is compensation for liquidity risk; it widens when market vol is high")
def _(): return gate(rev1m, high(MVOL))

@sig("rev_low_corr", "conditional", "When average correlation is low, moves are stock-specific and mean-revert")
def _(): return gate(rev1w, low(AVGCORR))

# ---- information-conditioned reversal (price moves without volume revert) -------------
@sig("rev_no_news", "interaction", "Moves on low abnormal volume are noise and revert; moves on high volume are information (Chan 2003, Gervais)")
def _(): return rev1m.where(rk(vsurge) < 0.5)

@sig("rev_news_cont", "interaction", "Moves on high abnormal volume continue: go with the 1m move when volume surged")
def _(): return (-rev1m).where(rk(vsurge) > 0.5)

@sig("rev_x_noinfo_rank", "interaction", "Continuous version: reversal rank times (1 - volume-surge rank)")
def _(): return rk(rev1m) * (1 - rk(vsurge))

# ---- momentum with crash protection ----------------------------------------------------
@sig("mom_ex_rebound", "conditional", "Momentum crashes in bear-market rebounds (Daniel-Moskowitz): skip when 24m mkt return < 0 and mkt up last month")
def _(): return gate(mom, ~((M24 < 0) & ~MDOWN1))

@sig("mom_trend_only", "conditional", "Own momentum only when the market is in an uptrend")
def _(): return gate(mom, MTREND)

@sig("mom_x_lowvol", "interaction", "Momentum among low-vol stocks is steadier; winners that rose smoothly")
def _(): return rk(mom) * rk(lowvol)

@sig("mom_plus_rev_blend", "interaction", "Intermediate momentum and short-term reversal are orthogonal; blend ranks")
def _(): return rk(mom) + rk(rev1w)

@sig("mom_rev_regime_switch", "conditional", "Momentum in uptrends, reversal in downtrends (sign switch on market trend)")
def _(): return switch(mom, rev1m, MTREND)

# ---- state-dependent risk anomalies ---------------------------------------------------
@sig("beta_switch", "conditional", "Low beta when market trend is down (defensive), high beta when up (aggressive)")
def _(): return switch(-lowbeta, lowbeta, MTREND)

@sig("lowvol_high_mktvol", "conditional", "Low-vol outperforms specifically in high-vol markets")
def _(): return gate(lowvol, high(MVOL))

@sig("h52_x_ovn", "interaction", "Stocks near 52w highs with strong overnight (institutional) flow")
def _(): return rk(h52) + rk(ovn)

@sig("quality_trend", "interaction", "Smooth uptrend AND low vol: stable compounders (rank product)")
def _(): return rk(B1.monthly(close / close.rolling(200).mean() - 1)) * rk(lowvol)

# ---- timing overlays on the equal-weight universe (vs buy-and-hold) ---------------------
EW = lab.FWD.mean(axis=1)                     # next-month equal-weight universe return, indexed by t
def _vt(target=0.10, cap=1.5):
    return (target / MVOL).clip(0, cap)

T = []
def timing(name, thesis, w): T.append((name, thesis, w))
timing("vol_target_10", "Scale exposure inversely to trailing vol (Moreira-Muir); vol clusters, returns do not scale with it", _vt())
timing("vol_target_15", "Same, 15% target allowing leverage up to 1.5x", _vt(0.15))
timing("trend_10m", "Hold only when EW universe is above its 10-month average (Faber)", MTREND.astype(float))
timing("trend_x_voltarget", "Trend filter and vol targeting combined", MTREND.astype(float) * _vt())
timing("vol_regime_off", "Go to cash when market vol is above its expanding 80th percentile", (~high(MVOL, 0.8)).astype(float))
timing("dd_stop", "Cash when the EW index is >15% below its trailing 12-month high", ((MIDX / MIDX.rolling(252).max()).loc[ME] > 0.85).astype(float))
timing("low_corr_risk_on", "Full risk only when avg correlation is below median (diversifiable market)", low(AVGCORR).astype(float))
