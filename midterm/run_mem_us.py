import json
import pandas as pd
from mem_lab import *
import mem_combo_us as M

rets = pd.read_pickle("mem_rets.pkl")
for name, fam, thesis, fn in M.K3:
    r = fn(); rets[name] = r; row = log(name, fam, thesis, r)
    print(f"{name:32s} Sharpe {row['sharpe']:+.2f} ann {row['ann_ret']:+.3f} t {row['t']:+.2f} DD {row['max_dd']:.2f} active {row['active_frac']:.2f}")
pd.to_pickle(rets, "mem_rets.pkl")
tr = pd.read_csv(LOG).set_index("name")
best = tr[tr.family == "combo-us"].sharpe.idxmax()
print("\nPre-declared rule: highest discovery Sharpe among US variants gets one hold-out look ->", best)
looks = holdout({best: rets[best], "theme_buyhold": rets["theme_buyhold"]})
old = json.load(open(LOOKS))
for n, d in looks.items():
    print(f"{n:32s} HOLD Sharpe {d['sharpe']:+.2f} ann {d['ann_ret']:+.3f} t {d['t']:+.2f} DD {d['max_dd']:.2f}")
