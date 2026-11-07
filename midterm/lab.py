"""Screening harness. Signals are evaluated on discovery data only; every trial is logged.

Conventions: signal[t, i] is known at close of month-end t; the return earned is the
next month-end's close-to-close return. Higher signal = expected higher return.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import data

HERE = Path(__file__).parent
LOG = HERE / "trials.csv"
DISC_END = "2018-12-31"          # discovery: 2011-2018, hold-out: 2019+
COST_BPS = 10                    # per unit of one-way turnover
N_UNIVERSE, MIN_PRICE = 1000, 5.0

D = data.load()
close, volume = D["close"], D["volume"]
dvol = (close * volume).rolling(63, min_periods=40).mean()
ME = close.groupby([close.index.year, close.index.month]).tail(1).index   # month-end trading days
ME = ME[ME >= "2010-12-01"]

# Universe: top 1000 by trailing 63-day dollar volume among the ~1500 names, price >= $5
_rank = dvol.loc[ME].rank(axis=1, ascending=False)
UNIV = (_rank <= N_UNIVERSE) & (close.loc[ME] >= MIN_PRICE)
FWD = close.loc[ME].pct_change().shift(-1)           # next-month return
FWD = FWD.where(UNIV)


def monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """Sample a daily signal frame at month-ends."""
    return daily.loc[ME]


def _tstat(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))) if len(x) > 3 and x.std() > 0 else np.nan


def ls_returns(sig: pd.DataFrame, q: float = 0.2, cost_bps: float = COST_BPS) -> tuple[pd.Series, pd.Series]:
    """Dollar-neutral top-q minus bottom-q, equal weight, monthly. Returns (net returns, turnover)."""
    s = sig.where(UNIV)
    r = s.rank(axis=1, pct=True)
    n = s.notna().sum(axis=1)
    long_ = (r > 1 - q)
    short = (r <= q)
    w = long_.div(long_.sum(axis=1), axis=0) - short.div(short.sum(axis=1), axis=0)
    w = w.where(n > 100, 0.0).fillna(0.0)
    gross = (w * FWD.fillna(0)).sum(axis=1)
    to = w.diff().abs().sum(axis=1) / 2          # one-way turnover per month (of 100% gross per side)
    net = gross - to * 2 * cost_bps / 1e4
    return net.iloc[:-1], to.iloc[:-1]


def ic_series(sig: pd.DataFrame) -> pd.Series:
    s = sig.where(UNIV).rank(axis=1)
    f = FWD.rank(axis=1)
    return s.corrwith(f, axis=1).iloc[:-1]


def _sharpe(r: pd.Series) -> float:
    return float(r.mean() / r.std(ddof=1) * np.sqrt(12)) if r.std() > 0 else np.nan


def evaluate(sig: pd.DataFrame, window: str = "disc") -> dict:
    ic, (ls, to) = ic_series(sig), ls_returns(sig)
    sl = (slice(None, DISC_END) if window == "disc" else slice(DISC_END, None))
    ic, ls, to = ic.loc[sl].dropna(), ls.loc[sl], to.loc[sl]
    ls = ls[ls != 0]
    return dict(ic=ic.mean(), ic_t=_tstat(ic), sharpe=_sharpe(ls), ann_ret=ls.mean() * 12,
                ann_vol=ls.std() * np.sqrt(12), ls_t=_tstat(ls), turnover=to.mean(), months=len(ls))


def log_trial(name: str, family: str, thesis: str, sig: pd.DataFrame) -> dict:
    """Evaluate on DISCOVERY only and append to the trial log. Never peeks at hold-out."""
    row = dict(name=name, family=family, thesis=thesis, **evaluate(sig, "disc"))
    df = pd.DataFrame([row])
    if LOG.exists():
        old = pd.read_csv(LOG)
        df = pd.concat([old[old.name != name], df])
    df.to_csv(LOG, index=False)
    return row


def holdout(name: str, sig: pd.DataFrame) -> dict:
    """One-shot hold-out look for a pre-selected survivor. Recorded so the number of looks is auditable."""
    out = evaluate(sig, "hold")
    p = HERE / "holdout_looks.json"
    looks = json.loads(p.read_text()) if p.exists() else {}
    looks[name] = {k: float(v) for k, v in out.items()}
    p.write_text(json.dumps(looks, indent=1))
    return out


def noise_threshold(n_trials: int, n_shuffles: int = 300, seed: int = 0) -> float:
    """95th pct of the best |discovery IC t| across n_trials pure-noise signals.
    Noise signals are cross-sectional shuffles of a real signal frame (keeps coverage and universe)."""
    rng = np.random.default_rng(seed)
    base = np.log(dvol.loc[ME])
    ts = []
    mask = UNIV.values
    for _ in range(n_shuffles):
        noise = pd.DataFrame(rng.standard_normal(base.shape), index=base.index, columns=base.columns)
        ts.append(abs(evaluate(noise.where(UNIV))["ic_t"]))
    ts = np.array(ts)
    best = [rng.choice(ts, n_trials).max() for _ in range(2000)]
    return float(np.quantile(best, 0.95))
