"""Pre-declared rule (written before looking): every candidate with discovery |t| > 2.5 gets ONE joint hold-out look (2021+)."""
import pandas as pd
from mem_lab import *

rets = pd.read_pickle("mem_rets.pkl")
tr = pd.read_csv(LOG)
surv = tr[(tr.t.abs() > 2.5) & (tr.family != "benchmark")].name.tolist()
print("survivors:", surv)
pick = {n: rets[n] for n in surv + ["MU_buyhold", "theme_buyhold"]}
looks = holdout(pick)
for n, d in looks.items():
    disc = tr.set_index("name").loc[n]
    print(f"{n:20s} disc Sharpe {disc.sharpe:+.2f} t {disc.t:+.2f} | HOLD Sharpe {d['sharpe']:+.2f} ann {d['ann_ret']:+.3f} t {d['t']:+.2f} DD {d['max_dd']:.2f}")
