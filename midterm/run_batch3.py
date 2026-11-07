"""Screen the pre-declared batch-3 grid (discovery only), then give the single best one a one-shot hold-out look."""
import numpy as np
import pandas as pd

import lab
from signals3 import FORM, S3, SCALED

rows = []
for name, fam, thesis, fn in S3:
    sig = fn()
    r = lab.log_trial(name, fam, thesis, sig)
    ls, _ = lab.ls_returns(sig)
    d = ls.loc[:lab.DISC_END]; d = d[d != 0]
    half = len(d) // 2
    r["sharpe_h1"], r["sharpe_h2"] = lab._sharpe(d.iloc[:half]), lab._sharpe(d.iloc[half:])
    rows.append(r | dict(name=name))
res = pd.DataFrame(rows)
res["abs_t"] = res.ic_t.abs()

scaled = []
for name, sig, scale in SCALED:
    ls, to = lab.ls_returns(sig)
    x = (ls * scale.reindex(ls.index)).loc[:lab.DISC_END]; x = x[x != 0]
    scaled.append(dict(name=name, sharpe=lab._sharpe(x), ann_ret=x.mean() * 12, ls_t=lab._tstat(x), months=len(x)))
scaled = pd.DataFrame(scaled)
scaled.to_csv(lab.HERE / "scaled_trials.csv", index=False)

n_total = len(pd.read_csv(lab.LOG)) + 7 + len(scaled)
thr = lab.noise_threshold(n_total)
print(f"{len(S3)} gated + {len(scaled)} scaled trials; {n_total} total so far; noise 95th-pct best |IC t| = {thr:.2f}\n")
cols = ["name", "ic", "ic_t", "sharpe", "sharpe_h1", "sharpe_h2", "ann_ret", "turnover", "months"]
print(res.sort_values("abs_t", ascending=False)[cols].head(12).round(3).to_string(index=False))
print("\nDispersion-scaled always-on:\n", scaled.round(3).to_string(index=False))
print("\nPass noise bar:", res[res.abs_t > thr].name.tolist())

best = res.sort_values("ic_t", ascending=False).iloc[0]
sig = next(fn for n, _, _, fn in S3 if n == best["name"])()
h = lab.holdout(best["name"], sig)
print(f"\nPre-declared rule: best discovery IC t -> one hold-out look: {best['name']}")
print({k: round(float(v), 3) for k, v in h.items()})
