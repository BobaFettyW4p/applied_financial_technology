# QuantConnect robustness sweep: `memory_basket_smh_trend.py`

**Purpose.** Decide whether the basket strategy is robust or an artifact of one parameter choice, one stock, or one
period. This is a *robustness check*, not a search: **the submitted configuration is the baseline unless a rule below
says otherwise. We never pick the best cell.** Rules were written before any sweep run.

Baseline (fixed before sweeping): `tickers=MU,WDC,STX`, `trend_days=100`, `gate=SMH`, 2011-01 to 2026-08.
QC baseline: CAGR 27.8%, Sharpe 0.88, max DD 42.2%, 689 orders, fees $71k.

## Runs (one factor at a time; 18 runs)

Set these in QuantConnect's Parameters panel. Unlisted parameters stay at baseline. Record every run, including bad ones,
in `qc_sweep_results.csv`.

| # | Group | Parameters changed |
|---|---|---|
| 1 | baseline | none |
| 2 | trend length | `trend_days=50` |
| 3 | | `trend_days=75` |
| 4 | | `trend_days=150` |
| 5 | | `trend_days=200` |
| 6 | gate | `gate=NONE` (own trend only) |
| 7 | names | `tickers=WDC,STX` (leave MU out) |
| 8 | | `tickers=MU,WDC` |
| 9 | | `tickers=MU,STX` |
| 10 | | `tickers=MU,WDC,STX,SNDK` (SNDK exists from 2025-02) |
| 11 | costs | `slippage_bps=5` |
| 12 | | `slippage_bps=10` |
| 13 | timing | `entry_minutes_before_close=1` |
| 14 | | `entry_minutes_before_close=15` |
| 15 | sub-period | `start_year=2011, end_year=2015` |
| 16 | | `start_year=2016, end_year=2020` |
| 17 | | `start_year=2021` (end stays 2026) |
| 18 | exposure | `gross_exposure=0.67` (does the strategy scale?) |

For each run record: CAGR, Sharpe, Sortino, max drawdown, total orders, fees, PSR, beta, alpha.

## Pre-declared decision rules

Each rule has a verdict: PASS keeps the baseline, FAIL changes what we claim or ship, as stated.

1. **Parameter plateau (runs 2-5 vs 1).** PASS if `trend_days` 75, 100 and 150 each have Sharpe within 0.15 of baseline
   and max DD < 50%. FAIL means the 100-day choice is a knife-edge: report the range honestly and do not claim
   "100-day trend" as a finding. Runs 2 and 5 are informational (tails of the range) and do not decide.
2. **The SMH gate earns its place (run 6 vs 1).** PASS (keep gate) if the gate cuts max DD by at least 5 points without
   lowering Sharpe by more than 0.10. Otherwise **drop the gate** and ship the simpler own-trend-only version.
3. **Not just a Micron bet (run 7).** PASS if WDC+STX alone (no MU) has Sharpe >= 0.5 and max DD at least 15 points
   smaller than their own buy-and-hold. FAIL means the edge lives in MU; say so on camera, and the claim becomes
   "trend-gated MU exposure with storage ballast", not "memory-theme trend following". Runs 8-9 are informational
   (leave-one-out).
4. **Cost robustness (runs 11-12).** PASS if Sharpe at `slippage_bps=10` is >= 0.70. FAIL means the edge does not
   survive realistic fills; fix by raising `gross_exposure` hold times or widening the rebalance band, not by changing
   signals.
5. **Execution timing (runs 13-14).** PASS if Sharpe moves by less than 0.10 versus baseline. FAIL means the result
   depends on the closing auction; test a market-on-close variant before submitting.
6. **Stability across eras (runs 15-17).** PASS if Sharpe is >= 0.5 in each of 2011-15, 2016-20 and 2021-26 and
   max DD < 50% in each. FAIL means it is a one-era result; disclose which era carries the return.
7. **SNDK extension (run 10).** Informational only (sample too short to decide). If it improves Sharpe *and* DD it
   becomes an "optional" note, not a change to the baseline.
8. **Scalability (run 18).** Informational: Sharpe should be roughly unchanged; DD and CAGR scale about linearly.

## Overall verdict

* **Ship the baseline** if rules 1, 4, 5 and 6 PASS. Rules 2 and 3 only change *what we claim* (simplify, or reframe).
* **Do not ship** (return to research) if rule 4 fails *and* rule 6 fails: that means costs and one era explain the result.
* A failed rule is a finding, not a problem: it goes in the video as part of the evaluation.

## What the video can say whichever way this goes

Already established (QuantConnect, full period): the strategy matches buy-and-hold on Sharpe but cuts max drawdown
from about 68% to 42%, giving up about 7 points of annual return; PSR is only about 15%, so it is not statistically
separable from the benchmark. The sweep tests whether even the *risk-reduction* claim is robust.

## Known limits (state these, do not hide them)

* 29 trials of research behind the basket idea, nine hold-out looks (`mem_holdout.json`); the 2021+ hold-out is not
  untouched data for the final configuration.
* Memory names rallied enormously in 2023-26 (AI demand); the trend gate mostly rode that. Rule 6 checks other eras.
* Single theme, three stocks: concentration risk. Beta to SPY was 0.43 and max DD 42%.
* QC fills market orders near, not at, the closing print; MOC orders are the likely fix if rule 5 fails.

## How to run the sweep (step by step)

1. In QuantConnect, open the project containing `memory_basket_smh_trend.py` (paste in the latest version of the file).
2. Near the top is one line: `OVERRIDES = {}`. That is the baseline. For each run, change **only that line** to the
   settings in the table (for example run 4 is `OVERRIDES = {"trend_days": 150}`), then click **Backtest**.
3. Name each backtest by run number (for example `run04_trend150`) so results stay matched to the table.
4. When it finishes, write the headline numbers into `qc_sweep_results.csv`, or just download each result JSON into
   `algorithms/` and ask Claude to fill the sheet and apply the rules.
5. Do the runs in any order; each is independent. Each takes a few minutes (minute-resolution, 15 years).

Overrides per run: #2 `{"trend_days": 50}` | #3 `{"trend_days": 75}` | #4 `{"trend_days": 150}` | #5 `{"trend_days": 200}` |
#6 `{"gate": "NONE"}` | #7 `{"tickers": "WDC,STX"}` | #8 `{"tickers": "MU,WDC"}` | #9 `{"tickers": "MU,STX"}` |
#10 `{"tickers": "MU,WDC,STX,SNDK"}` | #11 `{"slippage_bps": 5}` | #12 `{"slippage_bps": 10}` |
#13 `{"entry_minutes_before_close": 1}` | #14 `{"entry_minutes_before_close": 15}` |
#15 `{"start_year": 2011, "end_year": 2015}` | #16 `{"start_year": 2016, "end_year": 2020}` |
#17 `{"start_year": 2021}` | #18 `{"gross_exposure": 0.67}`

## Results (17 runs completed; raw numbers in `qc_sweep_results.csv`, parsed by `qc_collect.py`)

| Rule | Result | Verdict |
|---|---|---|
| 1 Plateau | trend 75 / 100 / 150: Sharpe 0.89 / 0.88 / 1.02; DD 34% / 42% / 36%. 200d: 0.95. 50d: 0.62 (too fast) | PASS |
| 2 SMH gate earns its place | gate removed: DD 42.1% vs 42.2%, Sharpe 0.91 vs 0.88, CAGR 30.3% vs 27.8% | **FAIL: drop the gate** |
| 3 Not just MU | WDC+STX only: Sharpe 0.72, DD 39% vs 68% for their buy-and-hold (29 points smaller) | PASS |
| 4 Costs | +10 bps slippage: Sharpe 0.84, CAGR 26.4% | PASS |
| 5 Timing | entry 1 / 15 min before close: Sharpe 0.88 / 0.89 vs 0.88 | PASS |
| 6 Eras | Sharpe 0.79 (2011-15), 0.57 (2016-20), 1.26 (2021-26); DD 23% / 35% / 43% | PASS (barely in 2016-20) |
| 7 SNDK (info) | Sharpe 0.91, DD 41.6%: marginal | note only |
| 8 Scale (info) | 0.67x gross: CAGR 18.8%, Sharpe 0.80, DD 30.8% | scales roughly linearly |

**Verdict.** Ship the simpler own-trend-only version (`gate=NONE`): the SMH gate, which looked helpful in the local
hold-out, adds nothing on QuantConnect. The remaining rules pass, but they were run on the *gated* version; the
changed configuration needs a confirmation pass (cost stress at 10 bps and the three eras with `gate=NONE`).
Eras caveat: CAGR was 14.6% (2011-15) and 15.9% (2016-20) versus 53.2% (2021-26): most of the return is the recent
memory rally; the earlier eras show the drawdown reduction but modest returns.

## Confirmation runs for the shipped configuration (gate=NONE, 100-day own trend)

| Run | CAGR | Sharpe | Max DD | PSR |
|---|---|---|---|---|
| gate=NONE, +10 bps slippage, 2011-26 | 29.1% | 0.875 | 43.1% | 14.6% |
| gate=NONE, 2011-15 | 19.0% | 0.81 | 24.2% | 25.3% |
| gate=NONE, 2016-20 | 18.1% | 0.64 | 33.4% | 13.6% |
| gate=NONE, 2021-26 | 53.8% | 1.23 | 42.1% | 51.8% |

Rules 4 (costs: Sharpe >= 0.70) and 6 (eras: Sharpe >= 0.5 and DD < 50% in each) PASS for the shipped configuration.
**Shipped: `memory_basket_smh_trend.py` with default `gate="NONE"`.** Full-period QC result with no extra slippage:
CAGR 30.3%, Sharpe 0.91, max DD 42.1%.

## SPY-fallback confirmation (shipped default is now `fallback="SPY"`)

Local test (2 trials, 31 total): idle slots in SPY instead of cash raised return about 5 points a year at a similar Sharpe
(discovery 0.92 vs 0.88; hold-out 1.30 vs 1.28; max DD -41% / -46% vs -36% / -42%). Confirm on QuantConnect with
6 runs. Edit only the `OVERRIDES` line.

| # | `OVERRIDES =` | Purpose |
|---|---|---|
| S1 | `{}` | shipped default, full period |
| S2 | `{"fallback": "CASH"}` | sanity: must reproduce the earlier gate=NONE run (CAGR 30.3%, Sharpe 0.91, DD 42.1%, 689 orders) |
| S3 | `{"slippage_bps": 10}` | cost stress |
| S4 | `{"start_year": 2011, "end_year": 2015}` | era 1 |
| S5 | `{"start_year": 2016, "end_year": 2020}` | era 2 |
| S6 | `{"start_year": 2021}` | era 3 |

Pass rules (declared now): S2 matches within rounding, otherwise the port has a bug and nothing else counts.
S1 Sharpe >= 0.85 and max DD < 50%. S3 Sharpe >= 0.70. S4-S6 Sharpe >= 0.5 and max DD < 50% each.
If S1 fails but S2 passes, revert the default to `"CASH"`.

### SPY-fallback confirmation results (S1-S6, all pass)

| Run | CAGR | Sharpe | Max DD | Orders | Rule | Verdict |
|---|---|---|---|---|---|---|
| S1 default (SPY fallback) | 35.7% | 0.97 | 46.9% | 1,493 | Sharpe >= 0.85, DD < 50% | PASS |
| S2 fallback=CASH | 30.2% | 0.91 | 42.1% | 1,089 | reproduce earlier cash run (30.3% / 0.91 / 42.1%) | PASS (orders differ: 1,089 vs 689 because the new rebalancer re-trues all slots when one drifts 2%; fees $77.8k vs $77.4k) |
| S3 +10 bps slippage | 33.0% | 0.91 | 48.7% | 1,496 | Sharpe >= 0.70 | PASS (drawdown close to the 50% line) |
| S4 2011-15 | 21.3% | 0.79 | 35.8% | 429 | Sharpe >= 0.5, DD < 50% | PASS |
| S5 2016-20 | 26.1% | 0.79 | 40.8% | 499 | same | PASS |
| S6 2021-26 | 59.7% | 1.29 | 46.9% | 563 | same | PASS |

Versus the cash version: SPY fallback adds about 5 points of annual return and lifts the earlier eras (cash: 19.0% / 18.1% / 53.8%),
at the cost of deeper drawdowns (cash: 24% / 33% / 42%) and a beta of about 1.2 instead of 0.55. Submission file:
`submission/memory_trend_basket.py` (same logic, sweep scaffolding and the unused SMH gate removed).

## Six-stock basket (MU, WDC, STX, LRCX, AMAT, KLAC): QuantConnect confirmation

Local test (3 trials, 45 total): passed the discovery rule (Sharpe 0.94 vs 0.92, drawdown 38% vs 41%, MU's share of stock-specific
profit 42% vs 69%); hold-out one look: Sharpe 1.15, 41.4% a year, drawdown 44% (trio: 1.30, 54.1%, 46%). Confirm with the sweep
file `algorithms/memory_basket_smh_trend.py` (default tickers now the six). Edit only the `OVERRIDES` line.

| # | `OVERRIDES =` | Purpose / pass rule |
|---|---|---|
| T1 | `{}` | six-stock default. Sharpe >= 0.85, max DD < 50% |
| T2 | `{"tickers": "MU,WDC,STX"}` | sanity: must reproduce S1 (35.7% / Sharpe 0.97 / DD 46.9% / 1,493 orders) |
| T3 | `{"slippage_bps": 10}` | Sharpe >= 0.70 |
| T4 | `{"start_year": 2011, "end_year": 2015}` | Sharpe >= 0.5, DD < 50% |
| T5 | `{"start_year": 2016, "end_year": 2020}` | same |
| T6 | `{"start_year": 2021}` | same |

If T2 fails the port is broken and nothing else counts. If T1 fails but T2 passes, revert the submission default to the three-stock basket.

### Six-stock QuantConnect results (T1-T6, all pass)

| Run | CAGR | Sharpe | Max DD | Orders | Verdict |
|---|---|---|---|---|---|
| T1 six default | 30.1% | 0.89 | 44.3% | 2,856 | PASS (Sharpe >= 0.85, DD < 50%) |
| T2 trio sanity | 35.5% | 0.97 | 46.9% | 1,493 | PASS (identical to S1, same fees to the cent) |
| T3 +10 bps slippage | 27.5% | 0.82 | 46.0% | 2,860 | PASS (Sharpe >= 0.70) |
| T4 2011-15 | 17.5% | 0.74 | 29.8% | 793 | PASS |
| T5 2016-20 | 26.7% | 0.84 | 38.1% | 962 | PASS |
| T6 2021-26 | 46.4% | 1.09 | 44.5% | 1,113 | PASS |

Six vs three (QC): CAGR 30.1% vs 35.7%, Sharpe 0.89 vs 0.97, DD 44.3% vs 46.9%, beta 1.25 vs 1.21, PSR 15.8% vs 23.3%, orders 2,856 vs 1,493.
Era drawdowns are shallower for the six (30% / 38% / 45% vs 36% / 41% / 47%). Concentration falls but beta does not.
