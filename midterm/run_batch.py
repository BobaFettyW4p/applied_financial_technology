"""Run every registered signal through the discovery screen, log it, print the noise-adjusted ranking."""
import pandas as pd

import lab
from signals import S

for name, fam, thesis, fn in S:
    r = lab.log_trial(name, fam, thesis, fn())
    print(f"{name:26s} IC {r['ic']:+.3f} t {r['ic_t']:+.2f}  Sharpe {r['sharpe']:+.2f}  TO {r['turnover']:.2f}")

df = pd.read_csv(lab.LOG)
thr = lab.noise_threshold(len(df))
print(f"\n{len(df)} trials; noise 95th-pct best |IC t| = {thr:.2f}")
df["abs_t"] = df.ic_t.abs()
print(df.sort_values("abs_t", ascending=False)[["name", "family", "ic", "ic_t", "sharpe", "ann_ret", "turnover"]].head(12).round(3).to_string(index=False))
print("pass noise bar:", df[df.abs_t > thr].name.tolist())
