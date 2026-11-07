"""Relationship research, DISCOVERY ONLY = 2021-01-01 to latest. 2011-2020 is now the hold-out and is NOT touched here.
Universe (software/distribution bucket removed): 18 names. Descriptive statistics only; nothing here is a trading result.
Tests are many, so we report how many pass |t|>3 against the ~expected false positives, and prefer group-level (few) tests.
  A. Group lead-lag: does group X's SPY-residual return on day t-k predict group Y's on day t? (k=1..5, also weekly)
  B. Pair lead-lag (306 ordered pairs, lag 1 daily, SPY-residual) with a multiple-testing count.
  C. Pair ratio mean reversion: z of log(Pi/Pj) vs its 60d mean; slope of next-20d ratio change on z (pairs sharing a theme)."""
import itertools
import numpy as np
import pandas as pd

START = "2021-01-01"
close = pd.read_parquet("data/close.parquet")
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna(); US = spy.index
G = {"memory": ["MU", "WDC", "STX", "SNDK"], "chips": ["NVDA", "AVGO", "AMD"], "hyperscale": ["AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM"],
     "infra": ["DELL", "ANET", "VRT", "EQIX", "CEG"]}
UNI = [t for g in G.values() for t in g]
P = close[UNI].reindex(US).ffill().loc[START:]
Rs = spy.pct_change().loc[START:]
R = P.pct_change()
beta = R.apply(lambda s: np.cov(s.dropna(), Rs.reindex(s.dropna().index))[0, 1] / Rs.reindex(s.dropna().index).var())
RES = R.sub(Rs.to_frame().values * beta.values, axis=1)          # residual vs full-sample beta (descriptive; fine for research)

def grp(df, names): return df[names].mean(axis=1)
GR = pd.DataFrame({g: grp(RES, ts) for g, ts in G.items()})

def lead_lag(x, y, k):
    d = pd.concat([x.shift(k), y], axis=1).dropna()
    n = len(d); c = d.corr().iloc[0, 1]
    return c, c * np.sqrt(n - 2) / np.sqrt(max(1e-9, 1 - c * c)), n

print(f"discovery sample {P.index[0].date()} to {P.index[-1].date()}  ({len(P)} days)\n")
print("A. GROUP LEAD-LAG (daily, SPY-residual)  leader -> follower, lag k: corr (t)")
rows = []
for a, b in itertools.permutations(G, 2):
    for k in (1, 2, 3, 5):
        c, t, n = lead_lag(GR[a], GR[b], k); rows.append((a, b, k, c, t))
A = pd.DataFrame(rows, columns=["lead", "follow", "lag", "corr", "t"])
print(A.reindex(A.t.abs().sort_values(ascending=False).index).head(12).round(3).to_string(index=False))
print(f"  ({len(A)} tests; |t|>2 count {int((A.t.abs()>2).sum())}, expect ~{0.05*len(A):.0f} by chance)")
print("  weekly (5-day non-overlapping) lag-1:")
W = (1 + GR).resample("W-FRI").prod() - 1
wr = []
for a, b in itertools.permutations(G, 2):
    d = pd.concat([W[a].shift(1), W[b]], axis=1).dropna(); c = d.corr().iloc[0, 1]; wr.append((a, b, c, c * np.sqrt(len(d) - 2)))
print(pd.DataFrame(wr, columns=["lead", "follow", "corr", "t"]).sort_values("t", key=abs, ascending=False).head(6).round(3).to_string(index=False))

print("\nB. PAIR LEAD-LAG lag-1 daily SPY-residual (306 ordered pairs, need >=500 obs)")
rows = []
for a, b in itertools.permutations(UNI, 2):
    c, t, n = lead_lag(RES[a], RES[b], 1)
    if n >= 500: rows.append((a, b, c, t, n))
B = pd.DataFrame(rows, columns=["lead", "follow", "corr", "t", "n"])
print(B.reindex(B.t.abs().sort_values(ascending=False).index).head(10).round(3).to_string(index=False))
print(f"  {len(B)} tests; |t|>3: {int((B.t.abs()>3).sum())} (expect ~{0.0027*len(B):.1f}); |t|>2: {int((B.t.abs()>2).sum())} (expect ~{0.0455*len(B):.0f})")
print("  mean corr overall:", round(B["corr"].mean(), 4), " share positive:", round((B["corr"] > 0).mean(), 2))

print("\nC. RATIO MEAN REVERSION: slope of next-20d change in log ratio on z (60d), pairs within theme + cross-theme memory pairs")
pairs = [p for g in G.values() for p in itertools.combinations(g, 2)] + [(m, c) for m in G["memory"] for c in G["chips"]] + [(m, h) for m in G["memory"] for h in G["hyperscale"]]
rows = []
for a, b in pairs:
    lr = np.log(P[a] / P[b]).dropna()
    if len(lr) < 400: continue
    z = (lr - lr.rolling(60).mean()) / lr.rolling(60).std()
    f = lr.shift(-20) - lr
    d = pd.concat([z, f], axis=1).dropna(); d = d.iloc[::20]       # non-overlapping 20d windows
    if len(d) < 25: continue
    x = d.iloc[:, 0]; y = d.iloc[:, 1]; slope = np.cov(x, y)[0, 1] / x.var()
    resid = y - y.mean() - slope * (x - x.mean()); se = np.sqrt(resid.var() / (len(d) * x.var()))
    rows.append((a, b, slope, slope / se, len(d)))
C = pd.DataFrame(rows, columns=["a", "b", "slope", "t", "n"])
print(C.reindex(C.t.abs().sort_values(ascending=False).index).head(8).round(3).to_string(index=False))
print(f"  {len(C)} pairs; negative slope (=mean-reverting) in {int((C.slope<0).sum())}; t<-2: {int((C.t<-2).sum())}; t>2 (trending ratio): {int((C.t>2).sum())}")
