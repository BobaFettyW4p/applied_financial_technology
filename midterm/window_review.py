"""Re-read every candidate on the AI-era window 2022-11-22 (ChatGPT launch) to latest. DESCRIPTIVE ONLY: all of these rules were designed while looking at
2021+ data, which contains this window, so it is not fresh out-of-sample. Also gives sub-window splits and the sampling error of a Sharpe over ~4 years."""
import numpy as np
import pandas as pd

START = "2022-11-22"
src = open("mem_ls6.py").read().split("DISC, HOLD =")[0]; ns = {}; exec(src, ns)
RS, EW, TR6, P, R, avail = ns["RS"], ns["EW"], ns["TR"], ns["P"], ns["R"], ns["avail"]
r3 = pd.read_pickle("mem_ls3_rets.pkl"); r4 = pd.read_pickle("mem_ls4_rets.pkl"); r5 = pd.read_pickle("mem_ls5_rets.pkl")

# old six-stock memory basket (trend 100d else SPY), same cost model
close = pd.read_parquet("data/close.parquet"); US = RS.index
SIX = ["MU", "WDC", "STX", "LRCX", "AMAT", "KLAC"]
c = close[SIX].reindex(US).ffill(); on = (c > c.rolling(100).mean()).shift(1).fillna(False).astype(float)
slot = on * c.pct_change() + (1 - on) * RS.values[:, None] - 2e-4 * on.diff().abs() * 2
basket6 = slot.mean(axis=1).dropna()

CAND = {"SPY": RS, "EW buy&hold 18": EW, "Old six-stock memory basket": basket6,
        "F4 fast regime + spread": TR6["F4 fast + spread"][0], "F2 fast regime": TR6["F2 graded fast"][0],
        "G4 slow regime + spread": r5["G4 G2 + mem/hyper spread"], "G2 slow regime": r5["G2 graded"], "G1 regime-only": r5["G1 regime-only"],
        "N2 spread (beta-hedged)": r3["N2 vol-targeted"], "C1 momentum L/S (beta-hedged)": r4["C1 score-weighted"]}

def st(r, a, b=None):
    r = r.loc[a:b].dropna(); nav = (1 + r).cumprod(); s = RS.reindex(r.index).fillna(0)
    return dict(sharpe=r.mean() / r.std() * np.sqrt(252), cagr=nav.iloc[-1] ** (252 / len(r)) - 1, dd=(nav / nav.cummax() - 1).min(),
                beta=np.cov(r, s)[0, 1] / s.var(), n=len(r), yrs=len(r) / 252)

mid = "2024-06-30"
rows = []
for k, r in CAND.items():
    a, b, c_ = st(r, START), st(r, START, mid), st(r, "2024-07-01")
    rows.append(dict(rule=k, sharpe=a["sharpe"], cagr=a["cagr"], dd=a["dd"], beta=a["beta"], sh_first=b["sharpe"], sh_second=c_["sharpe"]))
T = pd.DataFrame(rows).set_index("rule")
yrs = st(RS, START)["yrs"]
print(f"WINDOW {START} to latest: {yrs:.1f} years. Sharpe sampling error over this window ~ +/- {np.sqrt((1 + 0.5 * 0.9 ** 2) / yrs):.2f} (1 s.e.)")
print("   sub-windows: first = 2022-11-22..2024-06-30, second = 2024-07-01..latest\n")
print(T.round(2).to_string())
print("\ncalendar-year returns")
Y = pd.DataFrame({k: r.loc[START:].groupby(r.loc[START:].index.year).apply(lambda x: (1 + x).prod() - 1) for k, r in CAND.items()})
print(Y.round(3).T.to_string())
