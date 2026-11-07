"""Long-only screen: every batch-1/2 signal in two forms (top quintile; drop bottom quintile) plus new
long-only-native ideas. Discovery only, then one hold-out look at the best by alpha t."""
import numpy as np
import pandas as pd

import lab, lab_lo
import signals as B1
import signals2 as B2
import signals_lo as LO

cands = [(n, fn) for n, _, _, fn in B1.S] + [(n, fn) for n, _, _, fn in B2.S2] + [(n, fn) for n, _, fn in LO.S]
rows = []
for name, fn in cands:
    sig = fn()
    for mode in ("top", "excl"):
        rows.append(lab_lo.log_trial(name, mode, sig))
res = pd.DataFrame(rows)
n = len(res)
thr = lab_lo.noise_threshold(n)
res["abs_t"] = res.alpha_t.abs()
print(f"{n} trials; noise 95th-pct best |alpha t| = {thr:.2f}")
print(f"benchmark (EW universe, disc) Sharpe {res.bench_sharpe.iloc[0]:.2f}\n")
cols = ["name", "alpha_ann", "alpha_t", "excess_t", "ir", "beta", "sharpe", "turnover"]
print(res.sort_values("alpha_t", ascending=False)[cols].head(12).round(3).to_string(index=False))
print("\nPass noise bar:", res[res.abs_t > thr].name.tolist())

best = res.sort_values("alpha_t", ascending=False).iloc[0]
nm, mode = best["name"].split("|")
sig = next(fn for k, fn in cands if k == nm)()
h = lab_lo.holdout(nm, mode, sig)
print(f"\nHold-out look (best discovery alpha t): {nm}|{mode}")
print({k: round(float(v), 3) for k, v in h.items()})
