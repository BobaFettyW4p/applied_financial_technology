"""Pre-declared (before looking): primary = highest discovery Sharpe among combos; diversified alternative = highest among
basket combos. These two (and benchmarks for context) get ONE hold-out look. Bonferroni bar for 25 trials: |t| > 3.09."""
import json
import pandas as pd
from mem_lab import *

rets = pd.read_pickle("mem_rets.pkl"); tr = pd.read_csv(LOG).set_index("name")
combos = tr[tr.family == "combo"]
primary = combos.sharpe.idxmax()
alt = combos[combos.index.str.contains("basket")].sharpe.idxmax()
print("primary:", primary, "| diversified alternative:", alt)
looks = holdout({n: rets[n] for n in [primary, alt, "MU_buyhold", "theme_buyhold"]})
old = json.load(open(LOOKS)); 
for n, d in looks.items():
    print(f"{n:34s} HOLD Sharpe {d['sharpe']:+.2f} ann {d['ann_ret']:+.3f} t {d['t']:+.2f} DD {d['max_dd']:.2f}")
# context: full-period and yearly returns for the primary
r = rets[primary]
print("\nCalendar-year returns (primary vs MU buy&hold):")
yr = lambda x: (1 + x).groupby(x.index.year).prod() - 1
print(pd.DataFrame({"primary": yr(r), "MU_hold": yr(rets["MU_buyhold"])}).round(3).T.to_string())
