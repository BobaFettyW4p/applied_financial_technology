"""Candidate signals: (name, family, thesis, builder). Each builder returns a month-end frame; higher = long."""
import numpy as np
import pandas as pd

from lab import D, ME, close, volume, monthly

open_, high, low = D["open"], D["high"], D["low"]
ret = close.pct_change()
mkt = ret.mean(axis=1)
logp = np.log(close)


def _roll_beta(r, m, w=126):
    cov = r.rolling(w, min_periods=80).cov(m)
    return cov.div(m.rolling(w, min_periods=80).var(), axis=0)


def _resid(r, m, w=126):
    b = _roll_beta(r, m, w)
    return r.sub(b.mul(m, axis=0))


S = []
def sig(name, family, thesis):
    def deco(fn):
        S.append((name, family, thesis, fn)); return fn
    return deco


@sig("mom_12_1", "momentum", "Winners keep winning over 3-12 months (Jegadeesh-Titman)")
def _(): return monthly(close.shift(21) / close.shift(252) - 1)

@sig("mom_6_1", "momentum", "Intermediate momentum, skipping the reversal month")
def _(): return monthly(close.shift(21) / close.shift(126) - 1)

@sig("resid_mom_12_1", "momentum", "Momentum in market-residual returns is less crash-prone and less beta-driven")
def _(): return monthly(_resid(ret, mkt).rolling(231).sum().shift(21))

@sig("high_52w", "momentum", "Anchoring: stocks near their 52-week high keep rising (George-Hwang)")
def _(): return monthly(close / close.rolling(252).max())

@sig("trend_200d", "momentum", "Price above long moving average signals persistent trend")
def _(): return monthly(close / close.rolling(200).mean() - 1)

@sig("rev_1m", "reversal", "Liquidity-driven 1-month overreaction reverses")
def _(): return monthly(-(close / close.shift(21) - 1))

@sig("rev_1w", "reversal", "Weekly overreaction reverses faster than monthly")
def _(): return monthly(-(close / close.shift(5) - 1))

@sig("rev_resid_1m", "reversal", "Reversal in market-residual returns isolates stock-specific overreaction")
def _(): return monthly(-_resid(ret, mkt).rolling(21).sum())

@sig("rev_volume_cond", "reversal", "Reversal is stronger after high-volume drops (liquidity shock, Campbell-Grossman-Wang)")
def _():
    rv = (volume / volume.rolling(63).mean()).rolling(5).mean()
    return monthly(-(close / close.shift(21) - 1) * rv.rank(axis=1, pct=True))

@sig("low_vol", "risk", "Low-risk anomaly: leverage-constrained investors overpay for volatile stocks")
def _(): return monthly(-ret.rolling(126, min_periods=80).std())

@sig("low_beta", "risk", "Betting-against-beta (Frazzini-Pedersen)")
def _(): return monthly(-_roll_beta(ret, mkt, 252))

@sig("low_idio_vol", "risk", "Idiosyncratic volatility puzzle (Ang et al.)")
def _(): return monthly(-_resid(ret, mkt).rolling(63, min_periods=40).std())

@sig("max_effect", "risk", "Lottery demand: stocks with extreme recent up-days are overpriced (Bali et al.)")
def _(): return monthly(-ret.rolling(21).max())

@sig("skew", "risk", "Positive return skewness is overpriced; prefer negative-skew-averse picks")
def _(): return monthly(-ret.rolling(126, min_periods=80).skew())

@sig("downside_beta", "risk", "Beta measured only on down-market days is what investors actually fear")
def _():
    m = mkt.where(mkt < 0)
    c = (ret.mul(m, axis=0)).rolling(252, min_periods=60).mean()
    return monthly(-c.div((m ** 2).rolling(252, min_periods=60).mean(), axis=0))

@sig("vol_of_vol", "risk", "Stocks with unstable risk are riskier than trailing vol shows")
def _(): return monthly(-ret.abs().rolling(21).std())

@sig("amihud_illiq", "liquidity", "Illiquid stocks earn a premium (Amihud)")
def _(): return monthly((ret.abs() / (close * volume)).rolling(63, min_periods=40).mean())

@sig("size_small", "liquidity", "Smaller (lower dollar-volume) names earn more within the top 1000")
def _(): return monthly(-np.log((close * volume).rolling(63, min_periods=40).mean()))

@sig("volume_surge", "liquidity", "Attention shocks: abnormal volume predicts next-month returns (Gervais et al.)")
def _(): return monthly(volume.rolling(5).mean() / volume.rolling(126, min_periods=80).mean())

@sig("overnight_drift", "microstructure", "Overnight returns reflect informed/institutional demand and persist (Lou-Polk-Skouras)")
def _(): return monthly(np.log(open_ / close.shift(1)).rolling(126, min_periods=80).sum())

@sig("intraday_reversal", "microstructure", "Intraday returns reflect retail noise and mean-revert")
def _(): return monthly(-np.log(close / open_).rolling(63, min_periods=40).sum())

@sig("range_pct", "microstructure", "Wide intraday ranges signal disagreement/uncertainty (Garman-Klass-like vol)")
def _(): return monthly(-((high - low) / close).rolling(21).mean())

@sig("trend_consistency", "behavior", "Gradual information diffusion: many small up-days beat few big ones (Da-Gurun-Warachka)")
def _():
    sgn = np.sign(ret)
    frac = sgn.rolling(126, min_periods=80).mean()
    return monthly(frac * np.sign(close / close.shift(126) - 1))

@sig("seasonality_same_month", "seasonal", "Stocks repeat their own calendar-month returns (Heston-Sadka)")
def _():
    m = close.loc[ME].pct_change()
    return m.shift(11)

@sig("seasonality_annual_avg", "seasonal", "Average return in the same calendar month over prior years")
def _():
    m = close.loc[ME].pct_change()
    parts = [m.shift(12 * k) for k in range(1, 6)]
    return sum(parts) / 5

@sig("path_efficiency", "behavior", "Smooth, efficient price paths vs choppy ones carry different continuation")
def _():
    net = (logp - logp.shift(63)).abs()
    path = np.log(close / close.shift(1)).abs().rolling(63).sum()
    return monthly(net / path * np.sign(logp - logp.shift(63)))

@sig("gap_reversal", "microstructure", "Overnight gaps on no news fill during the day; fade the last month's gap sum")
def _(): return monthly(-np.log(open_ / close.shift(1)).rolling(21).sum())

@sig("vol_adj_mom", "momentum", "Momentum scaled by volatility is cleaner (Sharpe-style momentum)")
def _():
    m = close.shift(21) / close.shift(252) - 1
    return monthly(m / ret.rolling(252, min_periods=150).std())
