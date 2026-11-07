"""Exploration on DISCOVERY data only (2011-2020). Hold-out (2021+) is not touched here."""
import numpy as np
import pandas as pd

DATA = "data/mem_%s.parquet"
C, O = pd.read_parquet(DATA % "close"), pd.read_parquet(DATA % "open")
DISC = slice("2011-01-01", "2020-12-31")
R = C.pct_change(fill_method=None)

def ols_t(y, x):
    d = pd.concat([y, x], axis=1).dropna()
    X = np.column_stack([np.ones(len(d)), d.iloc[:, 1].values]); yy = d.iloc[:, 0].values
    b = np.linalg.lstsq(X, yy, rcond=None)[0]; e = yy - X @ b
    cov = np.linalg.inv(X.T @ X) @ (X.T * e ** 2) @ X @ np.linalg.inv(X.T @ X)   # HC0
    return b[1], b[1] / np.sqrt(cov[1, 1]), len(d), np.corrcoef(d.iloc[:, 0], d.iloc[:, 1])[0, 1]

print("== Daily return correlations, discovery (calendar-aligned) ==")
names = ["MU", "STX", "WDC", "SKhynix", "Samsung", "Nanya", "Winbond", "SMH", "SPY"]
print(R.loc[DISC, names].corr().round(2).to_string())
print("\n== Annualized vol, discovery ==")
print((R.loc[DISC, names].std() * np.sqrt(252)).round(2).to_string())

print("\n== Asia -> US lead-lag (Asia day-t return is known before US open on day t) ==")
gap = O / C.shift(1) - 1                      # US overnight (prev US close -> open)
oc = C / O - 1                                # US intraday (open -> close)
for asia in ("SKhynix", "Samsung", "Nanya", "Winbond"):
    for tgt in ("MU", "WDC", "STX"):
        for lab_, y in (("gap", gap[tgt]), ("open->close", oc[tgt]), ("close->close", R[tgt])):
            y = y.loc[DISC]; x = R[asia].loc[DISC]
            b, t, n, rho = ols_t(y, x)
            if lab_ == "open->close" or tgt == "MU":
                print(f"{asia:8s}->{tgt:4s} {lab_:12s} beta {b:+.3f} t {t:+.1f} corr {rho:+.2f} n {n}")

print("\n== Does Asia day-t return predict MU day t+1 (second-day drift)? ==")
for asia in ("SKhynix", "Samsung", "Nanya"):
    b, t, n, rho = ols_t(R["MU"].shift(-1).loc[DISC], R[asia].loc[DISC]); print(f"{asia}: beta {b:+.3f} t {t:+.1f}")
print("\n== MU's own daily autocorrelation, and 5d/21d (discovery) ==")
mu = R["MU"].loc[DISC].dropna()
print("lag1 %.3f" % mu.autocorr(1), " 5d-rev corr %.3f" % (C["MU"].pct_change(5).loc[DISC].corr(C["MU"].pct_change(5).shift(-5).loc[DISC])))
