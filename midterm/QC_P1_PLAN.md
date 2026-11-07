# QuantConnect confirmation: `algorithms/p1_regime_basket.py` (P1), AI-era window

**What P1 is.** Long only, always fully invested. Every day 5 minutes before the close: if at least 2 of 3 regime signals are true (equal-weight 18-name basket above its
50d SMA; above its 100d SMA; more than half the names above their own 50d SMA) hold the 18 names equal weight, otherwise hold 100% SPY. Universe: MU WDC STX SNDK |
NVDA AVGO AMD | AMZN GOOGL MSFT META ORCL IBM | DELL ANET VRT EQIX CEG (a name trades after 200 days of history).
Window: **2022-11-22 (ChatGPT launch)** to the latest QC data (about 2026-08-07), the algorithm's default.

**How it was found (be upfront).** It came out of round 9 (`mem_ls9.py`) as the plain-gate baseline of the overnight-split family; the overnight split itself added nothing
(P2 1.93 vs P1 1.86 Sharpe, inside the +/-0.6 sampling error), so P1 is the simplest of the three that passed. Shorting the basket (P4, O3, the G-family) did worse than
rotating to SPY. About 87 trials sit behind it; the 50/100-day windows were tuned after seeing 2022; the universe was chosen with hindsight; the pre-AI window was used
several times, so it is a sanity check, not clean out-of-sample.

## Offline checks (done)
* **Parity** (`p1_check.py`): the algorithm's own signal function reproduces the research P1 series, daily-return correlation 0.9999 (Sharpe 2.01, CAGR 62.7%, max DD -26%,
  2022-11-23 to 2026-08-07; regime up on 83% of days). These figures are to the QC data end, so they differ from the 1.86 / 56% quoted to Oct 29.
* **Order counts** (AI-era window): band 0% -> 8,366; 1% -> 1,829; **2% (default) -> 1,257**; 3% -> 1,079, with the same Sharpe within noise. Far under the 10,000 cap.
  Pre-AI window 2011-01-03 to 2022-11-21 at 2%: about 3,400 orders (Sharpe 0.96, CAGR 20%, DD -36% offline), also under the cap.

## QC runs (edit only the `OVERRIDES` line at the top of the file; record every run)

| # | `OVERRIDES =` | Purpose |
|---|---|---|
| R1 | `{}` | main result |
| R2 | `{"slippage_bps": 10}` | cost stress |
| R3 | `{"band": 0.01}` | does the band matter? |
| R4 | `{"start_date": "2022-11-22", "end_date": "2024-06-30"}` | first half |
| R5 | `{"start_date": "2024-07-01"}` | second half |
| R6 | `{"start_date": "2011-01-03", "end_date": "2022-11-21"}` | pre-AI sanity check (does the gate protect in older bears: 2018, 2022?) |

## Pre-declared rules (written before any QC run)
1. **Port sanity (R1).** Reaches the end date, total orders < 10,000, CAGR between 45% and 70%, max drawdown shallower than 32%, beta between 1.1 and 1.6.
   (QuantConnect's Sharpe subtracts the risk-free rate, so expect it about 0.15-0.4 below the offline 2.0; compare QC to QC.)
2. **Costs (R2).** CAGR >= 40%, max drawdown shallower than 32%, Sharpe >= 1.2.
3. **Band (R3).** Sharpe within 0.25 of R1; otherwise keep 2% and say so.
4. **Halves (R4, R5).** Informational: report each half's CAGR next to SPY's for the same dates.
5. **Pre-AI (R6).** Informational but disclosed either way: offline expectation Sharpe about 0.96, max DD about -36%, 2022 about -23%. If QC shows a max drawdown deeper than
   45% or a 2022 loss deeper than -32% (buy-and-hold's), P1 does not protect and the protection claim is dropped.
6. **Overall.** R1-R3 pass -> usable as a submission candidate with the disclosures above (beta ~1.4, trails plain buy-and-hold in the up-market, hindsight universe,
   many trials). R1 fails sanity -> fix the port first.

## How to run
Paste `p1_regime_basket.py` into a new QC project, run R1-R6 by editing only the `OVERRIDES` line, drop each result JSON into `algorithms/` and ask Claude to read them.

---

## QC results (R1-R6 all completed to their end dates; raw numbers in `qc_p1_results_raw.csv`)

| Run | Window | CAGR | Sharpe* | Max DD | Beta | Alpha | PSR | Orders | SPY CAGR (same dates) |
|---|---|---|---|---|---|---|---|---|---|
| R1 default | 2022-11-22 to 2026-08-07 | 62.9% | 1.78 | 27.8% | 1.36 | 0.247 | 84.7% | 1,200 | 21.5% |
| R2 +10 bps slippage | same | 58.4% | 1.65 | 28.2% | 1.37 | 0.219 | 78.8% | 1,202 | 21.5% |
| R3 band 1% | same | 61.6% | 1.76 | 27.8% | 1.36 | 0.239 | 83.7% | 1,522 | 21.5% |
| R4 first half | to 2024-06-30 | 69.2% | 2.20 | 11.9% | 1.42 | 0.255 | 88.4% | 392 | 24.3% |
| R5 second half | from 2024-07-01 | 58.0% | 1.55 | 27.7% | 1.33 | 0.238 | 67.5% | 831 | 19.5% |
| R6 pre-AI | 2011-01-03 to 2022-11-21 | 19.7% | 0.78 | 35.7% | 1.09 | 0.050 | 12.8% | 3,324 | 12.2% |

*QC Sharpe subtracts the risk-free rate. R1 calendar years: 2022 (stub) -5%, 2023 +73%, 2024 +49%, 2025 +52%, 2026 (to Aug) +64% vs SPY -3%, +26%, +25%, +18%, +13%.
R6 calendar years: 2011 -5% (SPY +2%), 2012 +21 (+14), 2013 +58 (+34), 2014 +20 (+15), 2015 -2 (+1), 2016 +38 (+11), 2017 +35 (+22), 2018 -2 (-5), 2019 +46 (+32), 2020 +33 (+18), 2021 +46 (+30), 2022 -23 (-16).

## Rule verdicts
1. **Port sanity (R1): PASS** (CAGR 62.9%, DD 27.8%, beta 1.36, 1,200 orders, reached the end date; offline expected ~63% / -26%).
2. **Costs (R2): PASS.** CAGR 58.4% (>= 40%), DD 28.2% (< 32%), Sharpe 1.65 (>= 1.2). +10 bps slippage cost 4.5 points of CAGR.
3. **Band (R3): PASS.** Sharpe 1.76 vs 1.78, a gap of 0.03 (< 0.25); keep the 2% band (about 320 fewer orders).
4. **Halves (informational).** First half 69% CAGR / Sharpe 2.20 / DD 11.9%; second half 58% / 1.55 / 27.7%. Both far above SPY (24% and 20%). The whole 27.8% drawdown happened in the second half.
5. **Pre-AI (R6): PASS the protection test, with caveats.** Max DD 35.7% (limit 45%) and 2022 -23% (limit -32%, buy-and-hold). Matches the offline expectation (Sharpe 0.96 offline vs 0.78 QC after the
   risk-free rate, DD -36%). But PSR is only 12.8%: over 2011-2022 it is not statistically separable from SPY, alpha 0.05, and the 2022 loss (-23%) was worse than SPY's (-16%).
   The gate protected relative to the AI basket (-32%), not relative to the market.
6. **Overall: R1-R3 pass, so P1 is a usable submission candidate** with the disclosures in the next section.

## What to say about P1 (on camera)
* It is the AI trade with a trend gate: long the 18 names about 83% of days, SPY the rest, no shorts, beta 1.1 to 1.4. It beat SPY by about 40 points a year over the AI era and by 7 points a year
  over 2011-22 (19.7% vs 12.2%), but with SPY-beating drawdowns only versus the plain AI basket, not versus SPY.
* The strong AI-era numbers (PSR 85%) are mostly the AI bull market; the 12-year check (PSR 13%) is the sober one.
* What was tuned: the 50/100-day windows were chosen after seeing 2022; about 87 trials; hindsight universe; the pre-AI window was used several times (so R6 is a sanity check).
* Shorting variants (O3, P4, G-family, F4's net-short sleeve) did worse than rotating to SPY, so the final rule does not short.
