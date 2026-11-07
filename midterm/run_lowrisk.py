"""Pre-declared joint test of the low-risk family (top quintile, equal weight), declared before the look:
members = low_vol, low_beta, low_idio_vol, downside_beta, all_defensive; verdict metric = family-average
return stream vs the equal-weight universe. One joint hold-out look, counted as 5 extra trials (109 total)."""
import json

import numpy as np
import pandas as pd

import lab, lab_lo
import signals as B1
import signals_lo as LO

MEMBERS = {n: fn for n, _, _, fn in B1.S if n in ("low_vol", "low_beta", "low_idio_vol", "downside_beta")}
MEMBERS["all_defensive"] = next(fn for n, _, fn in LO.S if n == "all_defensive")

streams = {}
for n, fn in MEMBERS.items():
    p, b, _ = lab_lo.lo_returns(fn(), "top")
    streams[n] = p
fam = pd.DataFrame(streams).mean(axis=1)
bench = b


def block_boot_sharpe_diff(a, b, block=6, reps=5000, seed=0):
    rng = np.random.default_rng(seed)
    a, b = a.values, b.values
    n = len(a); k = int(np.ceil(n / block)); out = []
    for _ in range(reps):
        idx = np.concatenate([np.arange(s, s + block) % n for s in rng.integers(0, n, k)])[:n]
        sa, sb = a[idx], b[idx]
        out.append(sa.mean() / sa.std(ddof=1) * np.sqrt(12) - sb.mean() / sb.std(ddof=1) * np.sqrt(12))
    return np.percentile(out, [5, 50, 95]), float(np.mean(np.array(out) <= 0))


def summarize(p, b):
    ex = p - b
    X = np.column_stack([np.ones(len(b)), b.values])
    c, *_ = np.linalg.lstsq(X, p.values, rcond=None)
    res = p.values - X @ c
    se = np.sqrt(res.var(ddof=2) * np.linalg.inv(X.T @ X)[0, 0])
    nav = (1 + p).cumprod(); nb = (1 + b).cumprod()
    return dict(sharpe=lab._sharpe(p), bench_sharpe=lab._sharpe(b), alpha_ann=c[0] * 12, alpha_t=c[0] / se, beta=c[1],
                excess_ann=ex.mean() * 12, ann_ret=p.mean() * 12, bench_ann=b.mean() * 12,
                max_dd=(nav / nav.cummax() - 1).min(), bench_dd=(nb / nb.cummax() - 1).min(), months=len(p))

out = {}
for label, sl in (("discovery", slice(None, lab.DISC_END)), ("HOLD-OUT", slice(lab.DISC_END, None))):
    p, b = fam.loc[sl].dropna(), bench.loc[sl].dropna()
    s = summarize(p, b)
    ci, p0 = block_boot_sharpe_diff(p, b)
    s["sharpe_diff_90ci"] = [round(float(x), 2) for x in ci]; s["p_diff_le_0"] = round(p0, 3)
    out[label] = s
    print(label, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items()}))

print("\nHold-out by member:")
for n in MEMBERS:
    e = lab_lo.evaluate(MEMBERS[n](), "top", window="hold")
    print(f"  {n:15s} Sharpe {e['sharpe']:.2f} (bench {e['bench_sharpe']:.2f})  alpha_t {e['alpha_t']:+.2f}  beta {e['beta']:.2f}")
    out[f"member:{n}"] = {k: float(v) for k, v in e.items()}

p = lab.HERE / "holdout_looks.json"
looks = json.loads(p.read_text()) if p.exists() else {}
looks["LOWRISK_FAMILY_JOINT"] = {k: v for k, v in out["HOLD-OUT"].items()}
p.write_text(json.dumps(looks, indent=1))
