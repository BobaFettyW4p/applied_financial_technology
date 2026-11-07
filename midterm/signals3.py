"""Batch 3: pre-declared grid around state-gated reversal.

Grid declared before running: 4 formations x 5 gates = 20 trials, 4 volume-conditioned
variants, 3 dispersion-scaled always-on variants. 27 trials, all counted toward the noise bar.
"""
import numpy as np
import pandas as pd

import lab
import signals as B1
from lab import ME, UNIV, close, volume
from signals2 import DISP, MVOL, MIDX, gate, high, rk, vsurge

ret, mkt = B1.ret, B1.mkt
resid = B1._resid(ret, mkt)

# alternative dispersion definitions (all known at month-end t)
DISP5 = (close / close.shift(5) - 1).loc[ME].where(UNIV).std(axis=1)
DISPRES = resid.rolling(21).sum().loc[ME].where(UNIV).std(axis=1)

FORM = {
    "r1m": B1.monthly(-(close / close.shift(21) - 1)),
    "r1w": B1.monthly(-(close / close.shift(5) - 1)),
    "res1m": B1.monthly(-resid.rolling(21).sum()),
    "res1w": B1.monthly(-resid.rolling(5).sum()),
}
GATE = {
    "disp21_hi": high(DISP, 0.5),
    "disp21_top3": high(DISP, 0.67),
    "disp5_hi": high(DISP5, 0.5),
    "dispres_hi": high(DISPRES, 0.5),
    "mvol_hi": high(MVOL, 0.5),
}
VGATE = {"r1m": FORM["r1m"], "r1w": FORM["r1w"], "res1m": FORM["res1m"], "res1w": FORM["res1w"]}

S3 = []
for f, fs in FORM.items():
    for g, on in GATE.items():
        S3.append((f"rev3_{f}_{g}", "reversal-gated", f"{f} reversal, held only when {g}", (lambda fs=fs, on=on: gate(fs, on))))
for f, fs in VGATE.items():
    S3.append((f"rev3_{f}_disp21_hi_lowvol", "reversal-gated+volume",
               f"{f} reversal on low-abnormal-volume moves only, when dispersion high",
               (lambda fs=fs: gate(fs, high(DISP, 0.5)).where(rk(vsurge) < 0.5))))

# dispersion-scaled always-on reversal: position size ∝ expanding percentile rank of dispersion
def _scale(x):
    return (x.expanding(12).rank(pct=True) * 2).clip(0, 2)
SCALED = [(f"rev3_{f}_dispscaled", fs, _scale(DISP)) for f, fs in FORM.items() if f != "res1w"]
