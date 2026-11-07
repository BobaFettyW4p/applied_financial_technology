"""Screen batch-2 conditional signals and timing overlays on DISCOVERY data only."""
import numpy as np
import pandas as pd

import lab
import signals as B1
from signals2 import EW, S2, T

for name, fam, thesis, fn in S2:
    r = lab.log_trial(name, fam, thesis, fn())
    print(f"{name:24s} IC {r['ic']:+.3f} t {r['ic_t']:+.2f}  Sharpe {r['sharpe']:+.2f}  ann {r['ann_ret']:+.3f}  months {r['months']}")

# ---- timing overlays: evaluated against buy-and-hold EW universe, discovery only -----------
def stats(x):
    x = x.dropna(); x = x.loc[:lab.DISC_END]
    nav = (1 + x).cumprod()
    return dict(sharpe=lab._sharpe(x), ann_ret=x.mean() * 12, ann_vol=x.std() * np.sqrt(12), max_dd=(nav / nav.cummax() - 1).min())

base = stats(EW.iloc[:-1])
print(f"\nBuy&hold EW universe (disc): {({k: round(v, 3) for k, v in base.items()})}")
rows = []
for name, thesis, w in T:
    s = stats((w.shift(0) * EW).iloc[:-1])
    rows.append(dict(name=name, **s))
    print(f"{name:20s} Sharpe {s['sharpe']:.2f} ann {s['ann_ret']:+.3f} vol {s['ann_vol']:.3f} maxDD {s['max_dd']:.2f}")
pd.DataFrame(rows).to_csv(lab.HERE / "timing_trials.csv", index=False)

df = pd.read_csv(lab.LOG)
n = len(df) + len(T)
thr = lab.noise_threshold(n)
df["abs_t"] = df.ic_t.abs()
print(f"\n{n} total trials (signals + overlays); noise 95th-pct best |IC t| = {thr:.2f}")
print(df[df.name.isin([s[0] for s in S2])].sort_values("abs_t", ascending=False)[["name", "ic", "ic_t", "sharpe", "ann_ret", "turnover", "months"]].head(10).round(3).to_string(index=False))
print("pass noise bar:", df[df.abs_t > thr].name.tolist())
