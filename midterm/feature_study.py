"""Fama-MacBeth feature study, DISCOVERY ONLY (2021-01-01 to latest). Descriptive; no trading rule here.
Each date (every 5 trading days) cross-sectional z-score each feature across the 18 names, regress the next-H-day beta-adjusted excess return
(stock - beta*SPY, trailing 120d beta, known at t) on the z-scores. Report the time-average slope in % per 1 sd and its t-stat (non-overlapping
cross-sections for H=5; every 4th for H=20 to avoid overlap). 10 distinct features x 2 horizons = 20 tests (gap features duplicate the reversal ones; shown but dropped): expect ~1 false |t|>2 by chance; trust |t|>3
or features that agree across horizons / sub-periods. The 2011-2020 window is not used."""
import numpy as np
import pandas as pd

START = "2021-01-01"
close = pd.read_parquet("data/close.parquet")
spy = pd.read_parquet("data/mem_close.parquet")["SPY"].dropna(); US = spy.index; RS = spy.pct_change()
TH = {"memory": ["MU", "WDC", "STX", "SNDK"], "chips": ["NVDA", "AVGO", "AMD"], "hyper": ["AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM"],
      "infra": ["DELL", "ANET", "VRT", "EQIX", "CEG"]}
UNI = [t for v in TH.values() for t in v]; theme_of = {t: g for g, v in TH.items() for t in v}
P = close[UNI].reindex(US).ffill(); R = P.pct_change()
beta = R.rolling(120).cov(RS).div(RS.rolling(120).var(), axis=0)
E = R.sub(beta.shift(1).mul(RS, axis=0))                               # beta-adjusted excess daily return
cum = lambda x, n: (1 + x).rolling(n).apply(np.prod, raw=True) - 1
spy_n = {n: cum(RS, n) for n in (5, 21, 63, 126)}
hyp_r = R[TH["hyper"]].mean(axis=1)
hyp_n = {n: cum(hyp_r, n) for n in (5, 21)}
theme_r = {g: R[v].mean(axis=1) for g, v in TH.items()}
F = {}
F["mom126"] = P.pct_change(126).sub(spy_n[126], axis=0)
F["mom63"] = P.pct_change(63).sub(spy_n[63], axis=0)
F["rev5"] = -P.pct_change(5)                                           # sign flipped: + means "fade last week"
F["rev21"] = -P.pct_change(21)
F["dist100"] = P / P.rolling(100).mean() - 1
F["off_high"] = P / P.rolling(252).max() - 1
F["lowvol"] = -R.rolling(60).std()
F["lowbeta"] = -beta
F["mom63_vs_theme"] = pd.DataFrame({t: F["mom63"][t] - F["mom63"][TH[theme_of[t]]].mean(axis=1) for t in UNI})
F["theme_mom63"] = pd.DataFrame({t: cum(theme_r[theme_of[t]], 63) - spy_n[63] for t in UNI})
F["gap5_vs_hyper"] = pd.DataFrame({t: -(P[t].pct_change(5) - hyp_n[5]) for t in UNI})       # lagging the customer basket this week -> catch up?
F["gap21_vs_hyper"] = pd.DataFrame({t: -(P[t].pct_change(21) - hyp_n[21]) for t in UNI})
z = lambda df: df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1).replace(0, np.nan), axis=0)
Z = {k: z(v.shift(1)) for k, v in F.items()}                           # features known at prior close

def fm(H, step):
    """univariate Fama-MacBeth: one feature at a time (features are collinear, so joint slopes are meaningless)."""
    fwd = E.rolling(H).sum().shift(-H)
    dates = [d for d in US[::step] if d >= pd.Timestamp(START)]
    rows = []
    for d in dates:
        y = fwd.loc[d]; r = {}
        for k in Z:
            x = Z[k].loc[d]; m = y.notna() & x.notna()
            r[k] = np.polyfit(x[m], y[m], 1)[0] if m.sum() >= 12 else np.nan
        rows.append(r)
    B = pd.DataFrame(rows).dropna(how="all")
    return B.mean() * 100, B.mean() / (B.std() / np.sqrt(B.count())), len(B), B

res = {}
for H, step in ((5, 5), (20, 20)):
    m, t, n, B = fm(H, step); res[H] = (m, t, n, B)
    print(f"H={H} days: {n} cross-sections")
out = pd.DataFrame({"slope5%": res[5][0], "t5": res[5][1], "slope20%": res[20][0], "t20": res[20][1]}).round(2)
out["same sign"] = np.sign(out["slope5%"]) == np.sign(out["slope20%"])
print("\nUNIVARIATE FM slopes (% next-H-day excess return per +1 sd of feature)\n" + out.drop(["gap5_vs_hyper", "gap21_vs_hyper"]).reindex(out.drop(["gap5_vs_hyper", "gap21_vs_hyper"])["t5"].abs().sort_values(ascending=False).index).to_string())
B5 = res[5][3]; h = len(B5) // 2
st = pd.DataFrame({"t_first_half": B5.iloc[:h].mean() / (B5.iloc[:h].std() / np.sqrt(h)), "t_second_half": B5.iloc[h:].mean() / (B5.iloc[h:].std() / np.sqrt(len(B5) - h))}).round(2)
print("\n5-day slope t-stat by half of the discovery sample (consistency check)\n" + st.drop(["gap5_vs_hyper", "gap21_vs_hyper"]).to_string())
