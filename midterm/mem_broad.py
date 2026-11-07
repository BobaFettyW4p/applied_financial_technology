"""Broad generality test, declared before running. Same rule on a pre-declared list of AI-chain stocks:
hold the stock while above its own 100-day average, otherwise SPY (2 bps per leg). Groups are equal-weight.
Primary question: does the rule beat buy-and-hold on the same names, in Sharpe and drawdown? 7 group-level trials (38 total).
Per-name numbers are descriptive only. Discovery 2011-2020, then ONE hold-out look at the 7 groups."""
import json
import numpy as np
import pandas as pd

COST, DISC_END = 2e-4, "2020-12-31"
closeA = pd.read_parquet("data/close.parquet")
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna()
US = spy.index
RS = spy.pct_change()

GROUPS = {
    "storage_hw": ["NTAP", "DELL", "HPE", "SMCI"],
    "semi_equip": ["AMAT", "LRCX", "KLAC", "ONTO", "ENTG", "MKSI", "TER"],
    "ai_chips": ["NVDA", "AVGO", "AMD", "MRVL", "ANET"],
    "other_semis": ["TXN", "ADI", "MCHP", "ON", "NXPI", "MPWR", "QCOM", "INTC"],
    "power_dc": ["VRT", "CEG", "VST", "NRG", "GEV", "ETN"],
    "cloud_bigtech": ["ORCL", "MSFT", "AMZN", "GOOGL"],
    "memory_ref": ["MU", "WDC", "STX"],
}

def name_returns(t):
    c = closeA[t].dropna().reindex(US).ffill()
    ma = c.rolling(100).mean()
    ok = ma.notna()
    on = (c > ma).astype(float).shift(1)
    r = c.pct_change()
    strat = on * r + (1 - on) * RS - COST * (on.diff().abs() * 2)      # a switch trades two legs
    return pd.DataFrame({"strat": strat, "bh": r}).where(ok.shift(1).fillna(False))

PN = {t: name_returns(t) for ts in GROUPS.values() for t in ts if t in closeA}

def stat(r, a, b):
    r = r.loc[a:b].dropna()
    if len(r) < 500: return None
    nav = (1 + r).cumprod()
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), cagr=nav.iloc[-1] ** (252 / len(r)) - 1, dd=(nav / nav.cummax() - 1).min(), n=len(r))

W = {"disc": ("2011-01-01", DISC_END), "hold": ("2021-01-01", "2026-11-02")}
def run(window):
    a, b = W[window]; out = []
    for g, ts in GROUPS.items():
        ts = [t for t in ts if t in PN and stat(PN[t]["strat"], a, b)]
        if not ts: continue
        s = pd.concat([PN[t]["strat"] for t in ts], axis=1).mean(axis=1); h = pd.concat([PN[t]["bh"] for t in ts], axis=1).mean(axis=1)
        S, H, P = stat(s, a, b), stat(h, a, b), stat(RS, a, b)
        out.append(dict(group=g, n_names=len(ts), s_sharpe=S["sharpe"], bh_sharpe=H["sharpe"], spy_sharpe=P["sharpe"],
                        s_cagr=S["cagr"], bh_cagr=H["cagr"], s_dd=S["dd"], bh_dd=H["dd"]))
    return pd.DataFrame(out).set_index("group")

def per_name(window):
    a, b = W[window]; rows = []
    for t, d in PN.items():
        S, H = stat(d["strat"], a, b), stat(d["bh"], a, b)
        if S and H: rows.append(dict(name=t, d_sharpe=S["sharpe"] - H["sharpe"], d_dd=S["dd"] - H["dd"], d_cagr=S["cagr"] - H["cagr"]))
    return pd.DataFrame(rows).set_index("name")

fmt = lambda df: df.round(2).to_string()
d = run("disc"); print("DISCOVERY 2011-2020 (group level; strategy = trend + SPY fallback)\n", fmt(d))
pn = per_name("disc")
print(f"\nPer name (descriptive), strategy minus buy&hold: n={len(pn)}  Sharpe better in {int((pn.d_sharpe>0).sum())}/{len(pn)}  "
      f"mean dSharpe {pn.d_sharpe.mean():+.2f}  maxDD shallower in {int((pn.d_dd>0).sum())}/{len(pn)}  mean dDD {pn.d_dd.mean():+.2f}  mean dCAGR {pn.d_cagr.mean():+.1%}")
h = run("hold"); print("\nHOLD-OUT 2021-26 (one look, all groups declared)\n", fmt(h))
pn2 = per_name("hold")
print(f"\nPer name hold-out: n={len(pn2)}  Sharpe better in {int((pn2.d_sharpe>0).sum())}/{len(pn2)}  mean dSharpe {pn2.d_sharpe.mean():+.2f}  "
      f"DD shallower in {int((pn2.d_dd>0).sum())}/{len(pn2)}  mean dDD {pn2.d_dd.mean():+.2f}  mean dCAGR {pn2.d_cagr.mean():+.1%}")
json.dump({"disc": d.round(4).to_dict("index"), "hold": h.round(4).to_dict("index")}, open("mem_broad_results.json", "w"), indent=1)
pn.join(pn2, lsuffix="_disc", rsuffix="_hold").round(3).to_csv("mem_broad_per_name.csv")
