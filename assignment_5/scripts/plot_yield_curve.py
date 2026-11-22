"""Plot the Treasury yield curve as a standalone SVG.

Reads data/processed/treasury_prices.csv (written by prepare_data.py), solves
each security's yield to maturity from its dirty price, and plots yield against
years to maturity: one dot per security, colored by Note/Bond, a fitted
Nelson-Siegel-Svensson curve, and a dashed median-yield line through maturity
buckets. Standard library only, so it runs anywhere prepare_data.py does and
the SVG can be served as-is.

NSS fit: y(t) = b0 + b1*L1(t) + b2*C1(t) + b3*C2(t), with
    L1 = (1 - e^(-t/tau1)) / (t/tau1),  C1 = L1 - e^(-t/tau1),
    C2 = (1 - e^(-t/tau2)) / (t/tau2) - e^(-t/tau2).
For fixed (tau1, tau2) the betas are ordinary least squares, so the fit is a
log-spaced grid search over tau1 < tau2 followed by shrinking local refinement.
The fit is to coupon yields to maturity, not zero rates, which is a common
approximation for plotting the curve.

Yield convention (U.S. Treasury street convention): semiannual compounding,
fractional first period = days_to_next_coupon / coupon_period_days (actual/actual).
Securities in their final coupon period use the simple-interest formula.

Securities maturing less than --min-years (default 0.5) after settlement are
excluded. Prices are quoted in 1/32nds, and below ~6 months a single tick moves
yield by 9-32 bp, far above the fit error; from 6 months on, rounding noise
(~1.5 bp) is below the fit's RMSE and the fitted curve beyond 2y is unchanged.

    python scripts/plot_yield_curve.py
    python scripts/plot_yield_curve.py --output public/yield_curve.svg
    python scripts/plot_yield_curve.py --min-years 0   # include everything
"""

from __future__ import annotations

import argparse
import csv
import math
from datetime import date
from pathlib import Path
from statistics import median
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "treasury_prices.csv"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "yield_curve.svg"

WIDTH, HEIGHT = 900, 520
MARGIN = {"left": 70, "right": 30, "top": 60, "bottom": 60}
COLORS = {"Note": "#2563eb", "Bond": "#d97706", "nss": "#111827", "median": "#9ca3af"}
# Bucket edges in years; the curve point for each bucket is its median yield.
# Edges below --min-years are dropped automatically.
BUCKETS = [0, 0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 25, 31]
DEFAULT_MIN_YEARS = 0.5


def remaining_coupons(next_coupon: date, maturity: date) -> int:
    """Coupon payments from next_coupon through maturity, inclusive."""
    months = (maturity.year - next_coupon.year) * 12 + (maturity.month - next_coupon.month)
    return months // 6 + 1


def dirty_price_at(y: float, coupon: float, n: int, w: float) -> float:
    """Dirty price per 100 face at annual yield y (decimal)."""
    c = coupon / 2
    if n == 1:  # final coupon period: simple interest
        return (100 + c) / (1 + w * y / 2)
    v = 1 / (1 + y / 2)
    return sum(c * v ** (w + k) for k in range(n)) + 100 * v ** (w + n - 1)


def yield_to_maturity(dirty: float, coupon: float, n: int, w: float) -> float:
    """Solve for annual YTM (percent) by bisection; price is monotone in yield."""
    lo, hi = -0.05, 0.50
    for _ in range(200):
        mid = (lo + hi) / 2
        if dirty_price_at(mid, coupon, n, w) > dirty:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2 * 100


def load_points(path: Path, min_years: float = DEFAULT_MIN_YEARS):
    points, price_date = [], ""
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("dirty_price"):
                continue
            settle = date.fromisoformat(r["settlement_date"])
            maturity = date.fromisoformat(r["maturity"])
            n = remaining_coupons(date.fromisoformat(r["next_coupon_date"]), maturity)
            w = int(r["days_to_next_coupon"]) / int(r["coupon_period_days"])
            ytm = yield_to_maturity(float(r["dirty_price"]), float(r["coupon"]), n, w)
            years = (maturity - settle).days / 365.25
            if years < min_years:
                continue
            points.append((years, ytm, r["security_type"]))
            price_date = price_date or r.get("price_date", "")
    if not points:
        raise ValueError(f"No priced securities maturing in {min_years}+ years in {path}")
    return points, price_date


def bucket_curve(points, min_years: float = 0.0):
    edges = [min_years] + [e for e in BUCKETS if e > min_years]
    curve = []
    for lo, hi in zip(edges, edges[1:]):
        inside = [(x, y) for x, y, _ in points if lo <= x < hi]
        if inside:
            curve.append((median(x for x, _ in inside), median(y for _, y in inside)))
    return curve


def nss_loadings(t: float, tau1: float, tau2: float):
    def slope(tau):
        x = t / tau
        return (1 - math.exp(-x)) / x if x > 1e-9 else 1.0
    l1, l2 = slope(tau1), slope(tau2)
    return (1.0, l1, l1 - math.exp(-t / tau1), l2 - math.exp(-t / tau2))


def solve_linear(a, b):
    """Gaussian elimination with partial pivoting; None if singular."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return None
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def nss_betas(points, tau1: float, tau2: float):
    """OLS betas and sum of squared errors for fixed taus."""
    xtx = [[0.0] * 4 for _ in range(4)]
    xty = [0.0] * 4
    rows = [(nss_loadings(t, tau1, tau2), y) for t, y, _ in points]
    for f, y in rows:
        for i in range(4):
            xty[i] += f[i] * y
            for j in range(4):
                xtx[i][j] += f[i] * f[j]
    betas = solve_linear(xtx, xty)
    if betas is None:
        return None, math.inf
    sse = sum((y - sum(b * fi for b, fi in zip(betas, f))) ** 2 for f, y in rows)
    return betas, sse


def fit_nss(points):
    """Return (b0, b1, b2, b3, tau1, tau2) and RMSE in percentage points."""
    # tau2 >= 1.5 * tau1 keeps the two curvature terms distinguishable.
    grid = [0.1 * 1.15 ** i for i in range(42)]  # 0.1y .. ~30y
    best = (math.inf, None, None, None)
    for tau1 in grid:
        for tau2 in grid:
            if tau2 >= 1.5 * tau1:
                betas, sse = nss_betas(points, tau1, tau2)
                if sse < best[0]:
                    best = (sse, betas, tau1, tau2)
    sse, betas, tau1, tau2 = best
    step = 1.15
    for _ in range(30):  # refine around the best grid point
        step = step ** 0.5
        for t1 in (tau1 / step, tau1, tau1 * step):
            for t2 in (tau2 / step, tau2, tau2 * step):
                if t2 >= 1.5 * t1:
                    b, e = nss_betas(points, t1, t2)
                    if e < sse:
                        sse, betas, tau1, tau2 = e, b, t1, t2
    return (*betas, tau1, tau2), math.sqrt(sse / len(points))


def nss_yield(t: float, params) -> float:
    b0, b1, b2, b3, tau1, tau2 = params
    return sum(b * f for b, f in zip((b0, b1, b2, b3), nss_loadings(t, tau1, tau2)))


def nice_ticks(lo: float, hi: float, step: float):
    start = int(lo // step)
    stop = int(-(-hi // step))
    return [i * step for i in range(start, stop + 1)]


def render_svg(points, price_date: str, min_years: float = 0.0, nss_params=None) -> str:
    plot_w = WIDTH - MARGIN["left"] - MARGIN["right"]
    plot_h = HEIGHT - MARGIN["top"] - MARGIN["bottom"]

    x_ticks = nice_ticks(0, max(x for x, _, _ in points), 5)
    x_hi = max(x for x, _, _ in points)
    fit_xs = [min_years + (x_hi - min_years) * i / 300 for i in range(301)]
    fit_xs = [x for x in fit_xs if x > 0]
    fit_ys = [nss_yield(x, nss_params) for x in fit_xs] if nss_params else []
    ys = [y for _, y, _ in points] + fit_ys
    y_ticks = nice_ticks(min(ys), max(ys), 0.25)
    x_min, x_max = x_ticks[0], x_ticks[-1]
    y_min, y_max = y_ticks[0], y_ticks[-1]

    def sx(x): return MARGIN["left"] + (x - x_min) / (x_max - x_min) * plot_w
    def sy(y): return MARGIN["top"] + (y_max - y) / (y_max - y_min) * plot_h

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" font-family="system-ui, sans-serif" font-size="12">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<text x="{MARGIN["left"]}" y="28" font-size="18" font-weight="600" fill="#111827">'
        f'U.S. Treasury Yield Curve</text>',
        f'<text x="{MARGIN["left"]}" y="46" fill="#6b7280">Notes and bonds, yield to maturity'
        f'{escape(f" · maturities ≥ {min_years:g}y") if min_years > 0 else ""}'
        f'{escape(" · priced " + price_date) if price_date else ""}</text>',
    ]

    for t in y_ticks:
        y = sy(t)
        out.append(f'<line x1="{MARGIN["left"]}" x2="{WIDTH - MARGIN["right"]}" y1="{y:.1f}" '
                   f'y2="{y:.1f}" stroke="#e5e7eb"/>')
        out.append(f'<text x="{MARGIN["left"] - 8}" y="{y + 4:.1f}" text-anchor="end" '
                   f'fill="#6b7280">{t:.2f}%</text>')
    for t in x_ticks:
        x = sx(t)
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{MARGIN["top"]}" '
                   f'y2="{HEIGHT - MARGIN["bottom"]}" stroke="#f3f4f6"/>')
        out.append(f'<text x="{x:.1f}" y="{HEIGHT - MARGIN["bottom"] + 18}" '
                   f'text-anchor="middle" fill="#6b7280">{t:g}</text>')
    out.append(f'<text x="{MARGIN["left"] + plot_w / 2}" y="{HEIGHT - 16}" text-anchor="middle" '
               f'fill="#374151">Years to maturity</text>')
    out.append(f'<text transform="translate(18 {MARGIN["top"] + plot_h / 2}) rotate(-90)" '
               f'text-anchor="middle" fill="#374151">Yield to maturity</text>')

    for x, y, kind in points:
        out.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3" '
                   f'fill="{COLORS.get(kind, "#9ca3af")}" fill-opacity="0.55">'
                   f'<title>{escape(kind)}: {x:.2f}y, {y:.3f}%</title></circle>')

    def polyline(xy):
        return " ".join(f'{"M" if i == 0 else "L"}{sx(x):.1f},{sy(y):.1f}'
                        for i, (x, y) in enumerate(xy))

    curve = bucket_curve(points, min_years)
    out.append(f'<path d="{polyline(curve)}" fill="none" stroke="{COLORS["median"]}" '
               f'stroke-width="1.5" stroke-dasharray="5 4"/>')
    if nss_params:
        out.append(f'<path d="{polyline(zip(fit_xs, fit_ys))}" fill="none" '
                   f'stroke="{COLORS["nss"]}" stroke-width="2.5"/>')

    legend = [("Note", COLORS["Note"], "dot"), ("Bond", COLORS["Bond"], "dot")]
    if nss_params:
        legend.append(("NSS fit", COLORS["nss"], "line"))
    legend.append(("Bucket median", COLORS["median"], "dash"))
    # Right-align the legend, sizing each item from an approximate text width.
    widths = [24 + 7 * len(label) for label, _, _ in legend]
    x = WIDTH - MARGIN["right"] - sum(widths)
    for (label, color, mark), w in zip(legend, widths):
        if mark == "dot":
            out.append(f'<circle cx="{x}" cy="24" r="4" fill="{color}"/>')
        else:
            dash = ' stroke-dasharray="4 3"' if mark == "dash" else ""
            out.append(f'<line x1="{x - 7}" x2="{x + 7}" y1="24" y2="24" '
                       f'stroke="{color}" stroke-width="2"{dash}/>')
        out.append(f'<text x="{x + 12}" y="28" fill="#374151">{escape(label)}</text>')
        x += w

    out.append("</svg>")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-years", type=float, default=DEFAULT_MIN_YEARS,
                        help="exclude securities maturing sooner than this (default: 0.5)")
    args = parser.parse_args()

    points, price_date = load_points(args.input, args.min_years)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    params, rmse = fit_nss(points)
    args.output.write_text(render_svg(points, price_date, args.min_years, params),
                           encoding="utf-8")
    print(f"Wrote {args.output} ({len(points)} securities)")
    b0, b1, b2, b3, tau1, tau2 = params
    print(f"NSS fit: b0={b0:.4f} b1={b1:.4f} b2={b2:.4f} b3={b3:.4f} "
          f"tau1={tau1:.3f}y tau2={tau2:.3f}y  RMSE={rmse * 100:.1f} bp")


if __name__ == "__main__":
    main()
