"""Long-only evaluation: hold top-q (or everything except the bottom-q) equal-weight within the
universe, judged against the equal-weight universe. Months where a gated signal is off hold the benchmark."""
import json

import numpy as np
import pandas as pd
from scipy import stats as st

import lab
from lab import FWD, UNIV, DISC_END, COST_BPS

LOG = lab.HERE / "lo_trials.csv"
BENCH_W = UNIV.div(UNIV.sum(axis=1), axis=0).astype(float)
BENCH = (BENCH_W * FWD.fillna(0)).sum(axis=1)


def weights(sig: pd.DataFrame, mode: str = "top", q: float = 0.2) -> pd.DataFrame:
    s = sig.where(UNIV)
    r = s.rank(axis=1, pct=True)
    sel = (r > 1 - q) if mode == "top" else (r > q)
    w = sel.div(sel.sum(axis=1), axis=0)
    off = s.notna().sum(axis=1) <= 100
    w.loc[off] = BENCH_W.loc[off]
    return w.fillna(0.0)


def lo_returns(sig, mode="top", q=0.2):
    w = weights(sig, mode, q)
    gross = (w * FWD.fillna(0)).sum(axis=1)
    cost = w.diff().abs().sum(axis=1) * COST_BPS / 1e4
    cost_b = BENCH_W.diff().abs().sum(axis=1) * COST_BPS / 1e4
    net = (gross - cost).iloc[:-1]
    return net, (BENCH - cost_b).iloc[:-1], (w.diff().abs().sum(axis=1) / 2).iloc[:-1]


def evaluate(sig, mode="top", q=0.2, window="disc") -> dict:
    p, b, to = lo_returns(sig, mode, q)
    sl = slice(None, DISC_END) if window == "disc" else slice(DISC_END, None)
    p, b, to = p.loc[sl].dropna(), b.loc[sl].dropna(), to.loc[sl]
    ex = p - b
    X = np.column_stack([np.ones(len(b)), b.values])
    beta_hat, *_ = np.linalg.lstsq(X, p.values, rcond=None)
    resid = p.values - X @ beta_hat
    se = np.sqrt(resid.var(ddof=2) * np.linalg.inv(X.T @ X)[0, 0])
    return dict(excess_ann=ex.mean() * 12, te=ex.std() * np.sqrt(12), ir=lab._sharpe(ex),
                excess_t=lab._tstat(ex), alpha_ann=beta_hat[0] * 12, alpha_t=beta_hat[0] / se,
                beta=beta_hat[1], sharpe=lab._sharpe(p), bench_sharpe=lab._sharpe(b), turnover=to.mean(), months=len(p))


def log_trial(name, mode, sig) -> dict:
    row = dict(name=f"{name}|{mode}", **evaluate(sig, mode))
    df = pd.DataFrame([row])
    if LOG.exists():
        old = pd.read_csv(LOG); df = pd.concat([old[old.name != row["name"]], df])
    df.to_csv(LOG, index=False)
    return row


def holdout(name, mode, sig) -> dict:
    out = evaluate(sig, mode, window="hold")
    p = lab.HERE / "holdout_looks.json"
    looks = json.loads(p.read_text()) if p.exists() else {}
    looks[f"LO:{name}|{mode}"] = {k: float(v) for k, v in out.items()}
    p.write_text(json.dumps(looks, indent=1))
    return out


def noise_threshold(n_trials, n_shuffles=300, seed=1) -> float:
    """95th pct of the best |alpha t| over n_trials noise signals. Per-trial |t| is modelled as |N(0, s)|
    with s estimated from shuffles, so the bar keeps rising with n_trials (no sampling cap)."""
    rng = np.random.default_rng(seed)
    base = np.log(lab.dvol.loc[lab.ME])
    ts = []
    for _ in range(n_shuffles):
        noise = pd.DataFrame(rng.standard_normal(base.shape), index=base.index, columns=base.columns)
        ts.append(evaluate(noise, "top")["alpha_t"])
    s = float(np.std(ts))
    x = st.norm.ppf((1 + 0.95 ** (1 / n_trials)) / 2)     # P(max|t| < x) = (2Phi(x/s)-1)^n = 0.95
    return float(x * s)
