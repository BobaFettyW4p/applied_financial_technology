"""Research round 2 on the AI-era window (2022-11-22 to latest), DESCRIPTIVE ONLY. New families not yet tested on the 18-name universe:
  A. Overnight vs intraday: where does the AI premium accrue (close->open vs open->close), per group.
  B. Chain-pair ratio trend for ALL group pairs (memory, chips, hyper, infra): does the ratio's 50d/100d trend persist? (generalises N2)
  C. Cross-asset indicators (Korea/Taiwan ETFs, KRW/TWD/JPY, SMH/SPY, QQQ/SPY, Asian memory) -> next-5d return of the AI basket.
  D. Correlation regime: average pairwise 60d correlation of the 18 names -> next-20d basket return and drawdown.
Everything uses information available at the close of day t to predict t+1 onward. ~40 tests in total: expect ~2 false |t|>2 by chance. The window is ~3.9 years, so
nothing here is more than a hypothesis; promising items get declared and tested separately."""
import itertools
import numpy as np
import pandas as pd

START = "2022-11-22"
src = open("mem_ls6.py").read().split("DISC, HOLD =")[0]; ns = {}; exec(src, ns)
R, P, RS, EW, avail, UNI = ns["R"], ns["P"], ns["RS"], ns["EW"], ns["avail"], ns["UNI"]
G = {"memory": ["MU", "WDC", "STX", "SNDK"], "chips": ["NVDA", "AVGO", "AMD"], "hyper": ["AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM"],
     "infra": ["DELL", "ANET", "VRT", "EQIX", "CEG"]}
gret = {g: R[v].mean(axis=1) for g, v in G.items()}
mem_close = pd.read_parquet("data/mem_close.parquet"); US = RS.index
mc = mem_close.reindex(US).ffill()

def ann(r): r = r.dropna(); return r.mean() * 252, r.mean() / r.std() * np.sqrt(252)

# ---------------- A. overnight vs intraday ----------------
print("A. OVERNIGHT vs INTRADAY (equal-weight within group, 2022-11-22 to latest): annualised mean / Sharpe")
O = pd.read_parquet("data/open.parquet")[UNI].reindex(US); C = pd.read_parquet("data/close.parquet")[UNI].reindex(US)
on = (O / C.shift(1) - 1); intra = (C / O - 1); cc = C.pct_change()
rows = []
for g, v in {**G, "ALL 18": UNI, "SPY": None}.items():
    if v is None:
        so = pd.read_parquet("data/mem_open.parquet")["SPY"].reindex(US); sc = pd.read_parquet("data/mem_close.parquet")["SPY"].reindex(US)
        a, b, c = (so / sc.shift(1) - 1), (sc / so - 1), sc.pct_change()
    else:
        a, b, c = on[v].mean(axis=1), intra[v].mean(axis=1), cc[v].mean(axis=1)
    rows.append(dict(group=g, **{f"{n}_mean": ann(x.loc[START:])[0] for n, x in (("night", a), ("day", b), ("c2c", c))},
                     **{f"{n}_sh": ann(x.loc[START:])[1] for n, x in (("night", a), ("day", b), ("c2c", c))}))
print(pd.DataFrame(rows).set_index("group").round(2).to_string())

# ---------------- B. chain-pair ratio trend ----------------
print("\nB. CHAIN-PAIR RATIO TREND: long A / short B (equal-weight baskets) when ratio above its SMA, reverse below; daily, signal known at prior close")
rows = []
for a, b in itertools.permutations(G, 2):
    if list(G).index(a) > list(G).index(b): continue
    ratio = (1 + gret[a].fillna(0)).cumprod() / (1 + gret[b].fillna(0)).cumprod(); spread = (gret[a] - gret[b])
    out = dict(pair=f"{a}/{b}")
    for n in (50, 100):
        sig = np.where(ratio > ratio.rolling(n).mean(), 1.0, -1.0); sig = pd.Series(sig, index=US).shift(1)
        r = (sig * spread - 2e-4 * 2 * sig.diff().abs().fillna(0)).loc[START:].dropna()
        h1, h2 = r.loc[:"2024-06-30"], r.loc["2024-07-01":]
        out[f"sh{n}"] = r.mean() / r.std() * np.sqrt(252); out[f"sh{n}_1st"] = h1.mean() / h1.std() * np.sqrt(252); out[f"sh{n}_2nd"] = h2.mean() / h2.std() * np.sqrt(252)
        out[f"bh_{n}"] = (spread.loc[START:].mean() / spread.loc[START:].std() * np.sqrt(252)) if n == 50 else np.nan
    rows.append(out)
B = pd.DataFrame(rows).set_index("pair"); B["bh"] = B.pop("bh_50"); B = B.drop(columns="bh_100")
print(B.round(2).to_string())
print("   (bh = Sharpe of simply holding long A / short B over the window, i.e. what the trend rule has to beat)")

# ---------------- C. cross-asset indicators ----------------
print("\nC. CROSS-ASSET INDICATORS -> next-5d return of the EW 18-name basket and of the memory basket (non-overlapping weeks)")
ewret = (ns["w"] * R.fillna(0)).sum(axis=1)
y5 = {"AI basket": ewret, "memory": gret["memory"]}
ind = {}
for t in ("EWY", "EWT", "SMH", "QQQ", "Samsung", "SKhynix", "Nanya", "Winbond"):
    ind[f"{t} 20d mom"] = mc[t].pct_change(20)
for t in ("KRW", "TWD", "JPY"):
    ind[f"{t} 20d chg (USD per FX up = FX weaker)"] = mc[t].pct_change(20)
ind["SMH/SPY trend (>50d)"] = (mc["SMH"] / mc["SPY"] > (mc["SMH"] / mc["SPY"]).rolling(50).mean()).astype(float)
ind["QQQ/SPY trend (>50d)"] = (mc["QQQ"] / mc["SPY"] > (mc["QQQ"] / mc["SPY"]).rolling(50).mean()).astype(float)
ind["Asia memory 20d (avg SK/Samsung)"] = (mc["SKhynix"].pct_change(20) + mc["Samsung"].pct_change(20)) / 2
rows = []
wk = US[US >= pd.Timestamp(START)][::5]
for k, x in ind.items():
    row = dict(indicator=k)
    for yn, y in y5.items():
        fwd = (1 + y).rolling(5).apply(np.prod, raw=True).shift(-5) - 1
        d = pd.concat([x.reindex(wk), fwd.reindex(wk)], axis=1).dropna()
        c = d.corr().iloc[0, 1]; row[f"{yn} corr"] = c; row[f"{yn} t"] = c * np.sqrt(len(d) - 2) / np.sqrt(1 - c * c)
    row["n"] = len(d); rows.append(row)
print(pd.DataFrame(rows).set_index("indicator").round(2).to_string())

# ---------------- D. correlation regime ----------------
print("\nD. CORRELATION REGIME: average pairwise 60d correlation of the 18 names vs next-20d EW basket return / worst drawdown")
avg_corr = pd.Series({d: (lambda m: (m.values[np.triu_indices_from(m.values, 1)]).mean())(R.loc[:d].iloc[-60:].dropna(axis=1, how="any").corr()) for d in US[US >= pd.Timestamp(START)]})
nav = (1 + ewret.fillna(0)).cumprod()
f20 = nav.shift(-20) / nav - 1
dd20 = pd.Series({d: (nav.loc[d:].iloc[:21] / nav.loc[d:].iloc[:21].cummax() - 1).min() for d in avg_corr.index})
d = pd.concat([avg_corr, f20.reindex(avg_corr.index), dd20], axis=1, keys=["corr", "f20", "dd20"]).dropna().iloc[::20]
d["bucket"] = pd.qcut(d["corr"], 3, labels=["low corr", "mid", "high corr"])
print(d.groupby("bucket", observed=True).agg(n=("f20", "size"), corr=("corr", "mean"), mean_f20=("f20", "mean"), worst_dd=("dd20", "mean")).round(3).to_string())
c = d[["corr", "f20"]].corr().iloc[0, 1]; print(f"   corr(avg corr, next-20d return) = {c:+.2f}, t = {c*np.sqrt(len(d)-2)/np.sqrt(1-c*c):+.2f}  (n={len(d)}, non-overlapping)")
print("   current avg corr:", round(float(avg_corr.iloc[-1]), 2), " window median:", round(float(avg_corr.median()), 2))
