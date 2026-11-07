import pandas as pd
from mem_lab import *
import mem_candidates as MC

rets = {}
for name, fam, thesis, fn in MC.K:
    r = fn(); rets[name] = r; row = log(name, fam, thesis, r)
    print(f"{name:22s} {fam:11s} Sharpe {row['sharpe']:+.2f} ann {row['ann_ret']:+.3f} t {row['t']:+.2f} DD {row['max_dd']:.2f} active {row['active_frac']:.2f} hit {row['hit']:.2f}")
pd.to_pickle(rets, "mem_rets.pkl")
