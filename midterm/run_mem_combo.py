import pandas as pd
from mem_lab import *
import mem_combo as MC

rets = pd.read_pickle("mem_rets.pkl")
for name, fam, thesis, fn in MC.K2:
    r = fn(); rets[name] = r; row = log(name, fam, thesis, r)
    print(f"{name:38s} Sharpe {row['sharpe']:+.2f} ann {row['ann_ret']:+.3f} t {row['t']:+.2f} DD {row['max_dd']:.2f} active {row['active_frac']:.2f}")
pd.to_pickle(rets, "mem_rets.pkl")
tr = pd.read_csv(LOG); print("\ntotal trials logged:", len(tr[tr.family != 'benchmark']))
