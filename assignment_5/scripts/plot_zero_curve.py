"""Plot the fitted Treasury zero curve as a standalone SVG.

Fits the Nelson-Siegel-Svensson zero-coupon curve exactly as rich_cheap.py does
(duration-weighted price errors, on-the-run and first off-the-run issues
excluded) and plots the zero rate against years to maturity, with labeled
markers at the standard tenors. Standard library only.

Zero rates are continuously compounded by default (the model's native form);
--compounding semiannual converts them to bond-equivalent rates,
2 * (exp(z / 2) - 1), for comparison with quoted Treasury yields.

    python scripts/plot_zero_curve.py
    python scripts/plot_zero_curve.py --compounding semiannual
    python scripts/plot_zero_curve.py --output public/zero_curve.svg
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from xml.sax.saxutils import escape

from plot_yield_curve import DEFAULT_MIN_YEARS, HEIGHT, MARGIN, WIDTH, nice_ticks
from rich_cheap import (
    DEFAULT_PRICES, DEFAULT_REFERENCE, DEFAULT_TERMS_DIR, fit_curve, load_bonds, zero_rate,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "zero_curve.svg"
TENORS = (1, 2, 3, 5, 7, 10, 20, 30)
CURVE_COLOR = "#2563eb"


def to_percent(z: float, compounding: str) -> float:
    if compounding == "semiannual":
        return 200 * (math.exp(z / 2) - 1)
    return z * 100


def render_svg(params, x_lo: float, x_hi: float, price_date: str, compounding: str,
               n_fit: int, rmse_bp: float) -> str:
    plot_w = WIDTH - MARGIN["left"] - MARGIN["right"]
    plot_h = HEIGHT - MARGIN["top"] - MARGIN["bottom"]

    xs = [x_lo + (x_hi - x_lo) * i / 300 for i in range(301)]
    ys = [to_percent(zero_rate(x, params), compounding) for x in xs]
    tenors = [(t, to_percent(zero_rate(t, params), compounding))
              for t in TENORS if x_lo <= t <= x_hi]

    x_ticks = nice_ticks(0, x_hi, 5)
    y_ticks = nice_ticks(min(ys), max(ys), 0.25)
    x_min, x_max = x_ticks[0], x_ticks[-1]
    y_min, y_max = y_ticks[0], y_ticks[-1]

    def sx(x): return MARGIN["left"] + (x - x_min) / (x_max - x_min) * plot_w
    def sy(y): return MARGIN["top"] + (y_max - y) / (y_max - y_min) * plot_h

    comp_label = "semiannual (bond-equivalent)" if compounding == "semiannual" \
        else "continuously compounded"
    subtitle = (f"NSS fit to {n_fit} notes and bonds · {comp_label} · RMSE {rmse_bp:.1f} bp"
                + (f" · priced {price_date}" if price_date else ""))
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" font-family="system-ui, sans-serif" font-size="12">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<text x="{MARGIN["left"]}" y="28" font-size="18" font-weight="600" fill="#111827">'
        f'U.S. Treasury Zero Curve</text>',
        f'<text x="{MARGIN["left"]}" y="46" fill="#6b7280">{escape(subtitle)}</text>',
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
               f'text-anchor="middle" fill="#374151">Zero rate</text>')

    path = " ".join(f'{"M" if i == 0 else "L"}{sx(x):.1f},{sy(y):.1f}'
                    for i, (x, y) in enumerate(zip(xs, ys)))
    out.append(f'<path d="{path}" fill="none" stroke="{CURVE_COLOR}" stroke-width="2.5"/>')

    for t, z in tenors:
        cx, cy = sx(t), sy(z)
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="#ffffff" '
                   f'stroke="{CURVE_COLOR}" stroke-width="2"><title>{t}y: {z:.3f}%</title>'
                   f'</circle>')
        out.append(f'<text x="{cx + 8:.1f}" y="{cy + 18:.1f}" text-anchor="start" '
                   f'fill="#374151">{t}y {z:.2f}%</text>')

    out.append("</svg>")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--terms-dir", type=Path, default=DEFAULT_TERMS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-years", type=float, default=DEFAULT_MIN_YEARS,
                        help="drop securities maturing sooner than this (default: 0.5)")
    parser.add_argument("--include-otr", action="store_true",
                        help="keep on-the-run and first off-the-run issues in the fit")
    parser.add_argument("--compounding", choices=("continuous", "semiannual"),
                        default="continuous")
    args = parser.parse_args()

    bonds, price_date = load_bonds(args.prices, args.reference, args.terms_dir)
    bonds = [b for b in bonds if b["years"] >= args.min_years]
    fit_set = [b for b in bonds if args.include_otr or b["otr_rank"] not in (0, 1)]
    if not fit_set:
        raise SystemExit(f"No securities maturing in {args.min_years}+ years to fit")
    params, sse = fit_curve(fit_set)
    rmse_bp = math.sqrt(sse / len(fit_set)) * 1e4

    x_lo = min(b["years"] for b in fit_set)
    x_hi = max(b["years"] for b in bonds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_svg(params, x_lo, x_hi, price_date.isoformat(),
                                      args.compounding, len(fit_set), rmse_bp),
                           encoding="utf-8")
    print(f"Wrote {args.output} (fit on {len(fit_set)} of {len(bonds)} securities, "
          f"RMSE {rmse_bp:.2f} bp)")
    print("Zero rates: " + "  ".join(
        f"{t}y {to_percent(zero_rate(t, params), args.compounding):.3f}%" for t in TENORS))


if __name__ == "__main__":
    main()
