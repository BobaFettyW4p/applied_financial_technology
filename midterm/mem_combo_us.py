"""US-only basket variants (QuantConnect-feasible), declared before running: 4 trials (29 total).
Breadth = share of {MU, WDC, STX, SMH} above their 50-day average (>= 0.75, i.e. 3 of 4)."""
import pandas as pd
from mem_combo import *

US_NAMES = ["MU", "WDC", "STX", "SMH"]
US_BREADTH = ((C[US_NAMES] > C[US_NAMES].rolling(50).mean()).mean(axis=1) >= 0.75).astype(float)
SMH_TREND = (C["SMH"] > C["SMH"].rolling(100).mean()).astype(float)

K3 = []
def cand(name, thesis):
    def deco(fn): K3.append((name, "combo-us", thesis, fn)); return fn
    return deco

@cand("us_full_x_trend_x_breadth", "Hold each name full-time only when its own trend is up AND US memory/semis breadth is healthy")
def _(): return avg(lambda t: legs(sh(TREND[t] * US_BREADTH), sh(TREND[t] * US_BREADTH), t))

@cand("us_night_always_day_breadth", "Overnight leg always on; intraday leg only when US breadth is healthy")
def _(): return avg(lambda t: legs(one(), sh(US_BREADTH), t))

@cand("us_full_x_trend_x_smh", "Own trend up AND the semiconductor sector (SMH) in an uptrend; simpler single external gate")
def _(): return avg(lambda t: legs(sh(TREND[t] * SMH_TREND), sh(TREND[t] * SMH_TREND), t))

@cand("us_full_x_trend_x_breadth_vt", "First variant scaled to 35% target vol, cap 1.5x")
def _(): return avg(lambda t: legs(sh(TREND[t] * US_BREADTH), sh(TREND[t] * US_BREADTH), t, SCALE))
