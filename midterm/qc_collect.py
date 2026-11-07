"""Read QC result JSONs, map files to sweep runs (by modification order, verified against dates/symbols), fill qc_sweep_results.csv."""
import json, os, re
import pandas as pd

A = "algorithms"
files = sorted([f for f in os.listdir(A) if f.endswith(".json")], key=lambda f: os.path.getmtime(f"{A}/{f}"))
base = ["Ugly Red Scorpion.json"]                         # run 1, earlier
orderd = [f for f in files if f not in base + ["Virtual Fluorescent Orange Lion.json"]]
plan = pd.read_csv("qc_sweep_results.csv")
runs = plan.run.tolist()[1:]                              # 2..18
assert len(orderd) == len(runs), (len(orderd), len(runs))

def num(x):
    return float(re.sub(r"[^0-9.\-]", "", x)) if isinstance(x, str) and re.search(r"\d", x) else None

rows = []
for r, f in zip(runs, orderd):
    d = json.load(open(f"{A}/{f}"))
    st = d["statistics"]; cfg = d["algorithmConfiguration"]
    syms = sorted({o["symbol"]["value"] if isinstance(o.get("symbol"), dict) else str(o.get("symbol")) for o in d["orders"].values()}) if isinstance(d["orders"], dict) else sorted({str(o["symbol"]["value"]) for o in d["orders"]})
    rows.append(dict(run=r, file=f, start=cfg["startDate"][:10], end=cfg["endDate"][:10], syms=",".join(syms),
                     cagr=num(st["Compounding Annual Return"]) / 100, sharpe=num(st["Sharpe Ratio"]), sortino=num(st["Sortino Ratio"]),
                     max_dd=num(st["Drawdown"]) / 100, orders=int(num(st["Total Orders"])), fees=num(st["Total Fees"]),
                     psr=num(st["Probabilistic Sharpe Ratio"]) / 100, beta=num(st["Beta"]), alpha=num(st["Alpha"])))
out = pd.DataFrame(rows)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(out.drop(columns=["file"]).to_string(index=False))
out.to_csv("qc_sweep_raw.csv", index=False)
