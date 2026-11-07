# QuantConnect confirmation: `algorithms/f4_regime_spread.py` (F4), AI-era window

**Testing window (changed).** The thesis is the AI trade and its surrounding technologies, so the window now starts at the ChatGPT launch,
**2022-11-22**, and runs to the latest QC data (about Aug 2026), roughly 3.9 years. This is the algorithm's new default `start_date`.

**What F4 is.** Two 50% sleeves, always in single stocks: (1) graded bull/bear regime on the equal-weight 18-name basket, net long in uptrends and
net short in downtrends; (2) vol-targeted memory-vs-hyperscaler spread with a SPY beta overlay. Details in the file's docstring.

## What the first QC run showed (file `Dancing Fluorescent Yellow Pelican.json`)
It was a 2011 start with the old 1% order band and **hit QuantConnect's 10,000-order cap on 2022-02-02**, so it covers only 2011-01 to 2022-02,
not the full period (CAGR 4.4%, Sharpe 0.23, max DD 26.9%, fees $125k, ~900 orders a year). Two consequences:
the earlier-era result is weak, consistent with the exploratory 2011-20 peek (Sharpe 0.61 vs SPY 0.84), and the order count had to come down.
Offline order simulation for the new window: band 1% -> ~4,800 orders, **band 2% -> ~3,100**, 3% -> ~1,650 (results about the same; Sharpe differences
across bands are noise). Default band is now 2%. The run also never traded CEG or SNDK because it stopped before they had 200 days of history.

## How F4 looks on the AI-era window (offline research numbers, 2022-11-22 to latest local data; descriptive, not a fresh test)
All rules were designed while looking at 2021+ data, which contains this window, so none of this is out-of-sample. A Sharpe over 3.9 years carries
about +/-0.6 of sampling error, so differences of 0.3-0.5 between rules are within noise.

| | Sharpe | CAGR | Max DD | beta |
|---|---|---|---|---|
| SPY | 1.26 | 19% | -19% | 1.00 |
| EW buy-and-hold of the 18 (hindsight universe) | 1.94 | 70% | -34% | 1.61 |
| Old six-stock memory basket (trend, SPY fallback) | 1.46 | 62% | -44% | 1.58 |
| **F4** (fast regime + spread) | 1.22 | 20% | -17% | 0.10 |
| G4 (slow regime + spread) | 1.69 | 31% | -16% | 0.20 |
| F2 fast regime alone | 0.82 | 20% | -29% | 0.17 |
| N2 spread alone | 1.12 | 18% | -15% | 0.02 |
| C1 momentum long/short | 0.73 | 24% | -54% | 0.22 |

Plain reading: in an AI bull market the protective rules give up most of the upside. F4 has SPY-like Sharpe, about a third of the basket's return and
a much shallower drawdown. It earns its keep only if a bear arrives; the window contains no real bear (2022 had its low just before the start).
F4 vs G4: G4 looks better here but the two differ only in regime speed, a difference inside the sampling error; F4 stays the build because it was
the faster, pre-chosen version, not because it is better in this window.

## QC runs (edit parameters in the panel; record every run, including bad ones)

| # | Parameters | Purpose |
|---|---|---|
| Q1 | defaults (2022-11-22 to latest, band 2%) | main result |
| Q2 | `slippage_bps=10` | cost stress |
| Q3 | `band=0.01` | does the band matter? (expect ~4,800 orders, under the cap) |
| Q4 | `start_date=2022-11-22, end_date=2024-06-30` | first half |
| Q5 | `start_date=2024-07-01` | second half |

## Pre-declared rules (written before any QC run)
1. **Port sanity (Q1).** Max drawdown shallower than 25%, |beta| < 0.35 and no order-cap truncation (total orders < 10,000, run reaches the end date).
   Offline expectation: CAGR about 20-27%, Sharpe about 1.1-1.5; if CAGR is outside 12-32% the gap is fills/data, investigate before reporting.
2. **Costs (Q2).** Sharpe >= 0.8 at 10 bps slippage.
3. **Band (Q3).** Sharpe within 0.25 of Q1 (the sampling error makes tighter comparisons meaningless); otherwise keep 2% and say so.
4. **Halves (Q4, Q5).** Informational. Report both Sharpes; a split of the sort seen offline (first half stronger) is expected and is not a failure.
5. **Overall.** Q1 and Q2 pass -> usable as a submission candidate, with the disclosures above (hindsight universe, ~75 trials, window not out-of-sample,
   trails the plain AI basket in an up-market). Q1 fails sanity -> fix the port first.

## How to run
New QC project, paste `f4_regime_spread.py`, run Q1-Q5, and drop each result JSON into `algorithms/` for Claude to read.

---

## QC results (all five runs completed to their end dates; raw numbers in `qc_f4_results.csv`)

| Run | CAGR | Sharpe* | Max DD | Beta | Alpha | Orders | Fees | SPY CAGR (same dates) |
|---|---|---|---|---|---|---|---|---|
| Q1 default (2022-11-22 to 2026-08-07, band 2%) | 25.7% | 0.985 | 15.7% | 0.11 | 0.124 | 2,635 | $4,940 | 21.5% |
| Q2 +10 bps slippage | 23.3% | 0.868 | 16.1% | 0.11 | 0.108 | 2,636 | $4,856 | 21.5% |
| Q3 band 1% | 24.1% | 0.913 | 15.8% | 0.10 | 0.114 | 3,348 | $5,612 | 21.5% |
| Q4 first half (to 2024-06-30) | 21.3% | 0.874 | 9.9% | 0.56 | 0.036 | 944 | $2,531 | 24.3% |
| Q5 second half (from 2024-07-01) | 29.1% | 1.065 | 15.7% | -0.10 | 0.173 | 1,742 | $2,173 | 19.5% |

*QuantConnect's Sharpe subtracts the risk-free rate, so it is lower than the offline Sharpe (which does not); compare QC to QC.
Q1 calendar years: 2022 (from Nov 22) -2.8%, 2023 +26.9%, 2024 +9.2%, 2025 +37.5%, 2026 (to Aug) +26.3%.

## Rule verdicts
1. **Port sanity (Q1): PASS.** Max DD 15.7% (< 25%), beta 0.11 (< 0.35), 2,635 orders (no cap truncation), runs to the end date, CAGR 25.7% inside 12-32%.
   CEG and SNDK now trade (they did not in the truncated first run).
2. **Costs (Q2): PASS.** Sharpe 0.868 at +10 bps (>= 0.8); CAGR falls 2.4 points.
3. **Band (Q3): PASS.** Sharpe 0.913 vs 0.985, a gap of 0.07 (< 0.25); keep the 2% band (about 700 fewer orders).
4. **Halves (informational).** Second half (Sharpe 1.07, beta -0.10) was stronger than the first (0.87, beta 0.56). Offline had it the other way round
   (first half stronger), which is the sampling-error warning in action. The first half carried a long-biased beta because the regime was net long.
5. **Overall: usable as a submission candidate.**

## What it does and does not show (say this on camera)
* It beat SPY on CAGR (25.7% vs 21.5%) with a beta of 0.11, alpha 0.124 and a 15.7% drawdown, but **PSR is only 38.7%** (information ratio 0.18): over 3.9 years
  this is not statistically distinguishable from SPY, which matches the +/-0.6 Sharpe sampling error.
* It lagged the plain AI trade: the offline equal-weight basket made ~70% a year and the old memory basket ~62% in the same window. F4 gives up most of the
  upside for protection that this window never needed (no bear after 2022-11-22).
* It FAILED the earlier discovery rule (2022 had to be positive). The universe was picked with hindsight, ~75 trials sit behind it, and the window is not
  out-of-sample for rule design.
