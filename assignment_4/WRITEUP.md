# Assignment 4: A factor beyond Fama-French 5

**Question.** Pick a factor we haven't covered, backtest it, and say whether it is additive to and worthwhile relative to the Fama-French 5 (FF5) script.

## Summary

- **Our pick: "cash quality" (`cashq`).** The mean percentile rank of four standard metrics: ROIC, ROE, FCF yield and buyback yield. Each has independent literature support; together they describe businesses that earn good returns on capital and return real cash to shareholders. Before it, we tested fundamental momentum (improving profitability) and low volatility, and both failed.
- **Baseline: FF5 as provided earns about nothing risk-adjusted.** On the script's own universe (top 200 US stocks by dollar volume, 20 long / 20 short, 2011-2026) it returned +44.8% over 15.6 years: CAGR 2.3%, Sharpe 0.02, max drawdown 51.5%. The script also sorts backwards relative to its own comments: it longs the *worst* names on the textbook factors.
- **`cashq` raw is not a result.** It looked good in the 2011-2018 discovery window (Sharpe 0.69) and did nothing in the 2019-2026 hold-out (Sharpe 0.06). It is 0.85 correlated with the FF5 long-quality / short-growth trade.
- **`cashq` with style exposures removed is a low-risk diversifier, not a money-maker.** +18.3% over the period (CAGR 1.0%), 21.5% max drawdown, positive in both windows (+0.8% and +1.9% a year), but statistically indistinguishable from zero (monthly t = 0.73). Its return is below T-bills, so QuantConnect's Sharpe (which subtracts the risk-free rate) is -0.18.
- **Additive to FF5? In a regression sense, no; in a portfolio sense, partly.** Regressed on the published Fama-French 5 factors (Section 4b), raw `cashq` is mostly FF5's own profitability factor (RMW loading 0.78, t 7.9) with an insignificant alpha (+3.1% a year, t 1.4; +5.4% in discovery and +0.1% in the hold-out). Style-neutral `cashq` has no alpha at all (-0.3% a year, t -0.3): the factors explain what little it earned, mainly through a value (HML) tilt. Where it does help is in a blend: its return stream is negatively correlated with the provided FF5 (-0.25 in 2011-18, -0.22 in 2019-26). A 50/50 blend lifts the Sharpe to 0.33 from 0.24 (no risk-free), halves volatility (7.0% vs 13.6%) and cuts the worst drawdown from 51% to 28%. The blend earns less than FF5 alone (2.3% vs 3.3% a year, difference not significant). The gain is in risk, not return.
- **On our themed 11-stock basket, nothing works** in the textbook direction (FF5, low vol, fundamental momentum, `cashq`). Factors found on a broad universe do not transfer to a concentrated defense / shipping / metals / fertilizer basket.

![Growth of $1M](figures/fig1_equity_curves.png)

## 1. What `cashq` is

| Metric | Measures | Why it might predict returns |
|---|---|---|
| ROIC | After-tax operating profit over all invested capital | High returns on capital mark a good business |
| ROE | Net income over shareholders' equity | The FF5 profitability leg (RMW); profitable firms have beaten unprofitable ones |
| FCF yield | Free cash flow over market value | Cash is harder to fake than earnings; a value signal built on cash |
| Buyback yield | Net repurchases over market value | Managers shrinking the share count signal cheapness and return cash; issuers show the opposite |

Each month every stock is ranked 0 to 1 on each metric across the universe and `cashq` is the average rank (at least 3 of 4 required). The strategy is long the top 20 and short the bottom 20, equal weight, 100% gross, rebalanced monthly. The name is ours; it is not a standard factor label.

**Honest caveat on selection.** We did not pick these four on theory alone. They were the four factors that cleared t >= 2 in discovery out of 34 tested. They kept the right sign in the hold-out but did not pass the stricter multiple-testing bar.

## 2. Research process, and what each step found

**Step 1: our 11-stock basket (2018-2023 research window; 2024+ reserved).** Universe: LMT, RTX, FRO, STNG, INSW, AA, CENX, CF, MOS, IPI, GSL.

| Candidate | Result |
|---|---|
| FF5 composite | IC -0.090 (t -2.4): wrong sign. Profitability *levels* are lowest right before a commodity cycle turns |
| Low volatility | Raw IC 0.046 (t 1.0). Residual IC after removing FF5 looked strong (t 3.1) but was a suppression artifact: low vol is 0.55 correlated with the wrong-signed FF5, and in backtests it picked the same book |
| Fundamental momentum | IC -0.171 (t -3.2): wrong sign, in all three sub-periods |
| 117 within-peer-group subsets x factors | 0 survive a best-of-grid permutation test. Closest: contrarian profitability (adjusted p 0.10), the opposite of the literature direction |
| `cashq` on the 11 (one pre-declared test) | IC -0.095 (t -1.97), 3/3 long-short Sharpe -0.87, permutation p 0.97. Wrong sign |

**Step 2: broad universe, discovery 2011-2018 / hold-out 2019-2026.** 34 candidate metrics from standard literature (value, payout, quality, growth/investment, momentum, reversal, risk, size/liquidity, profitability change, plus the five FF5 parts as controls), directions fixed in advance.

- **Best-of-34 null.** The 95th percentile of the best |t| under pure noise is 3.19. The best real factor (buyback yield) reached 2.60, so **no factor passed the adjusted bar.**
- **But the unadjusted winners all replicated in the hold-out with the right sign:**

| Factor | Discovery IC (t) | Hold-out IC (t) |
|---|---|---|
| ROIC | 0.032 (2.5) | 0.040 (2.5) |
| ROE | 0.027 (2.1) | 0.032 (2.0) |
| FCF yield | 0.036 (2.5) | 0.028 (1.3) |
| Buyback yield | 0.030 (2.6) | 0.021 (1.4) |

  This is the theme `cashq` is built from. FF5's own ROE leg is one of them; the FF5 composite fails mainly because of its other legs (raw book value per share has IC -0.034, t -2.5).
- **Composite results.**

| | IC discovery (t) | IC hold-out (t) | Net Sharpe 20/20, 10bp costs: disc / hold-out |
|---|---|---|---|
| `cashq` raw | 0.043 (3.1) | 0.038 (2.1) | 0.39 / **-0.02** |
| `cashq` style-neutral | 0.033 (2.6) | 0.026 (2.0) | 0.05 / **0.23** |
| Fundamental momentum | -0.025 (-2.3) | n/a | negative |

  Style-neutral means regressing out beta, size, book yield, 12-1 momentum and 1-year volatility each month (one fixed control set, chosen in advance). It lowered the long/short correlation with the FF5 trade from 0.84 to 0.39.

## 3. Backtest comparison (top-200 universe, 20 long / 20 short, monthly, $1M, 2011-01 to 2026-07)

| Run | Return | CAGR | Sharpe (QC) | Max DD | Alpha / beta vs SPY |
|---|---|---|---|---|---|
| 01 FF5 textbook orientation | -51.9% | -4.32% | -0.40 | 64.5% | -0.026 / -0.20 |
| **02 FF5 as provided (the benchmark)** | **+44.8%** | **+2.26%** | **0.02** | **51.5%** | -0.016 / +0.21 |
| 03 Fundamental momentum alone | -29.4% | -2.08% | -0.53 | 41.5% | -0.036 / +0.05 |
| 04 FF5 + fundamental momentum (5/6, 1/6) | -30.4% | -2.17% | -0.42 | 56.4% | -0.018 / -0.16 |
| 05 FF5 + fundamental momentum (50/50) | -32.2% | -2.32% | -0.60 | 46.9% | -0.029 / -0.06 |
| 06 `cashq` raw | +44.7% | +2.25% | 0.02 | 51.2% | +0.016 / -0.16 |
| **07 `cashq` style-neutral** | **+18.3%** | **+1.02%** | **-0.18** | **21.5%** | -0.015 / +0.05 |
| SPY (price only) | +673% | +14.0% | n/a | 33.7% | n/a |
| 50/50 blend of 02 and 07 | +39.1% | about +2.2% | n/a | 28.0% | n/a |

QC's Sharpe subtracts the risk-free rate. Sharpe from monthly returns *without* a risk-free rate (the convention below) reads higher; e.g. FF5 provided is 0.24.

**By window (monthly Sharpe without risk-free; annual return)**

| | 2011-2018 | 2019-2026 |
|---|---|---|
| 01 FF5 textbook | -0.18 (-1.4%) | -0.34 (-6.2%) |
| 02 FF5 provided | 0.12 (+0.9%) | 0.32 (+5.7%) |
| 04 FF5 + fm (5/6) | -0.68 (-3.6%) | -0.00 (-0.0%) |
| 05 FF5 + fm (50/50) | -0.72 (-4.0%) | -0.01 (-0.1%) |
| 06 `cashq` raw | **0.69** (+5.3%) | 0.06 (+1.1%) |
| 07 `cashq` style-neutral | 0.12 (+0.8%) | **0.24** (+1.9%) |
| 50/50 blend 02 + 07 | 0.20 | 0.43 |

(Run 03's results file was not exported, so it has no window split.)

**Calendar years (%)**

| | 2020 | 2021 | 2022 | 2023 |
|---|---|---|---|---|
| 01 FF5 textbook | -38 | +6 | +38 | -19 |
| 02 FF5 provided | +54 | -11 | -30 | +19 |
| 06 `cashq` raw | -31 | +14 | +39 | -16 |
| 07 `cashq` style-neutral | -18 | +3 | +10 | -3 |

![Drawdowns](figures/fig2_drawdowns.png)

## 4. Is it additive, and is it worthwhile?

**Fundamental momentum: no.** Wrong sign on both universes. Adding it to FF5 lowered volatility (13.6% to 8.9% and 7.3% annualized, correlation with `01` of 0.72 and 0.29) but did not improve returns: paired against `01`, +1.9% a year (t 0.79) and +1.7% (t 0.48). Not additive in a statistically meaningful way.

**`cashq` raw: no.** In-sample strength (discovery Sharpe 0.69), no hold-out edge (0.06), and 0.85 correlation with the FF5 trade it was supposed to differ from.

**`cashq` style-neutral: modestly yes as a diversifier, no as an alpha source.**
- Positive net return in both windows, 21.5% max drawdown versus 51-65% for the FF5 runs.
- Return stream negatively correlated with the provided FF5 and only 0.22 correlated with the textbook version.
- Absolute return is cash-like (CAGR 1.0%), the monthly t-stat is 0.73, and QC's own Sharpe (-0.18) is worse than FF5's (0.02).
- The blend result is about risk, not return: the blend's return is not significantly different from FF5's alone (-1.0% a year, t -0.46).

**Relative to FF5:** the provided FF5 is a weak benchmark (Sharpe 0.02). `cashq` style-neutral is lower-return, much lower-risk and a good partner for it. That is the only sense in which it is "additive", and Section 4b shows it comes from offsetting factor exposures rather than alpha: the regression on the published FF5 factors leaves zero unexplained return. It is not a standalone strategy worth deploying.

## 4b. Formal test: regression on the published Fama-French 5 factors

Each backtest's monthly return is regressed on Mkt-RF, SMB, HML, RMW and CMA (Kenneth R. French Data Library, monthly, through 2026-08; Newey-West t-stats with 6 lags). Strategies are dollar-neutral, so raw returns are used. The intercept (alpha) is the return the five factors do not explain. Code: `ff5_regression.py`; results: `figures/ff5_regression_results.csv`.

| Strategy | Alpha (% a year) | Alpha t | R² | Mkt-RF | SMB | HML | RMW | CMA |
|---|---|---|---|---|---|---|---|---|
| 01 FF5 textbook | -3.09 | -1.40 | 0.58 | -0.22 | -0.29 | **+0.44** | **+0.71** | +0.20 |
| 02 FF5 as provided | +2.61 | 1.18 | 0.58 | +0.22 | +0.28 | **-0.44** | **-0.72** | -0.19 |
| 04 FF5 + fm (5/6, 1/6) | -1.12 | -0.66 | 0.43 | -0.14 | -0.17 | +0.15 | +0.29 | **+0.33** |
| 05 FF5 + fm (50/50) | -1.90 | -1.07 | 0.08 | -0.03 | -0.15 | 0.00 | -0.05 | +0.19 |
| 06 `cashq` raw | +3.14 | 1.38 | 0.48 | -0.16 | -0.27 | +0.33 | **+0.78** | +0.11 |
| 07 `cashq` style-neutral | **-0.34** | **-0.27** | 0.21 | +0.11 | -0.06 | **+0.25** | +0.08 | 0.00 |
| 50/50 blend (02 + 07) | +1.20 | 1.13 | 0.46 | +0.16 | +0.13 | -0.10 | -0.30 | -0.09 |

Bold loadings have |t| above about 3. No strategy has a statistically significant alpha.

**Alpha by window (% a year, t in parentheses)**

| | 2011-2018 | 2019-2026 |
|---|---|---|
| 06 `cashq` raw | +5.42 (2.48) | +0.09 (0.03) |
| 07 `cashq` style-neutral | -0.53 (-0.33) | -0.27 (-0.14) |
| 02 FF5 as provided | +0.77 (0.46) | +5.36 (1.48) |

**What it says**
- **The provided FF5 script is a profitability and value bet.** It loads -0.72 on RMW and -0.44 on HML (R² 0.58): it is short the profitable, high book-to-market names, which is why it earns the opposite of the textbook factors.
- **Raw `cashq` is largely the FF5 profitability factor.** Its RMW loading is +0.78 (t 7.9). The metrics we thought were beyond FF5 (FCF yield, buyback yield) did not make it separable once ROIC and ROE dominate. Its apparent discovery-window edge (alpha +5.4% a year, t 2.5) vanishes in the hold-out (+0.1%).
- **Style-neutral `cashq` has no FF5 alpha.** What little it earned is explained by a value tilt (HML +0.25, t 4.4) and a small positive market loading. Alpha is -0.3% a year (t -0.3). Adding the momentum factor does not change this (alpha +0.0%).
- **So the diversification in the blend is factor exposure, not alpha.** `02` is short HML and RMW; `07` is long HML. Their offsetting loadings explain the negative correlation and the drop in risk.
- **Honest conclusion on "additive relative to FF5":** in the formal, regression sense, `cashq` adds nothing (zero alpha). The raw version is FF5's own profitability premium; the style-neutral version is a small value tilt with cash-like returns. The one thing it does for an investor is partly hedge the specific FF5-as-provided book.

## 5. Research versus backtest: what we learned

1. **Statistical signal is not tradeable return.** `cashq` IC held at about 0.04 in both windows. Converting it to equal-weighted top/bottom-20 books produced a Sharpe of about zero in the hold-out because the extreme tails behave like a growth-versus-quality bet (the 2020 and 2022 regime swings dominate every run).
2. **Neutralizing style exposures is what made it portfolio-useful.** It did not make it profitable.
3. **The first strong-looking result was an artifact.** Low-vol's residual IC (t 3.1) came from FF5 being wrong-signed on the 11 stocks, and the low-vol and FF5 backtests picked nearly the same book.
4. **Many tests mean many chances.** We tested dozens of factors across two universes. The permutation null (best-of-grid) showed that a t of 2.6 is what luck produces; the factors that survive are the ones that also kept their sign out of sample.
5. **Concentrated books and tiny universes are noisy.** On 11 stocks and a 3/3 book, one name swap moved results by 10 points (04 vs 05). Do not read ranking differences among those runs.
6. **The provided FF5 script runs backwards.** It sorts each factor descending and then longs the highest average index, i.e. the worst names on the textbook factors. We ran both orientations and labelled them (`01` textbook, `02` as provided). Its "size" and "book value" legs also use raw dollar and per-share levels, which are not meaningful cross-sectionally.

## 6. Limitations

- **The hold-out is no longer pristine.** We viewed individual-factor hold-out ICs before building the composite and ran several diagnostics on it afterward. Treat the hold-out as confirmation of a candidate, not a clean discovery. A clean test needs data we do not have, or a different stock population.
- **Evidence is moderate at best.** The best candidate did not clear the multiple-testing bar and its returns are not statistically significant.
- **Blend weights are post hoc.** 50/50 is the default choice but was evaluated after seeing results.
- **Costs and shorting.** 10bp one-way was assumed in research; QuantConnect fees were included in backtests ($17-27k on $1M). Borrow costs and short availability are not modeled.
- **Sharpe conventions differ.** QC subtracts the risk-free rate; the monthly-return Sharpes in Section 3's window table do not.
- **The 11-stock backtests ran with an early first-day bug** (runs `01`-`03` in `algorithms/`; fixed for later runs), so their January 2024 positioning is unreliable.

## 7. 11-stock backtests (for completeness; 3 long / 3 short, 2024-01 to 2026-07, SPY about +60%)

| Run | Return | Note |
|---|---|---|
| `01_ff5_provided` | +7.7% | run before the data-readiness fix |
| `02_ff5_textbook` | -17.1% | before the fix |
| `03_lowvol_only` | -22.0% | before the fix |
| `04_ff5_plus_lowvol` | -29.9% | fixed |
| `05_ff5_plus_lowvol_heavy` | -20.7% | fixed |

Every variant converged to the same trade (defense long versus aluminum/potash short), so differences between them are one or two names.

## Files

| Path | What it is |
|---|---|
| `FamaFrench5FactorAlgorithm.py` | The provided FF5 script |
| `factor_exploration*.ipynb` | 11-stock research (IC, residual IC, subsets, fundamental momentum); later copies add parts |
| `broad_factor_research*.ipynb` | Broad-universe 34-factor search with hold-out, permutation null, `cashq` composite, style-neutral diagnostics |
| `cashq_11_stock_test.ipynb` | `cashq` on our 11 stocks, one pre-declared test |
| `algorithms/` | 11-stock backtest algorithms (`01`-`05`) |
| `algorithms_broad/` | Broad-universe FF5 and fundamental-momentum backtests (`01`-`05`) |
| `algorithms_cashq/` | `06_cashq_raw.py`, `07_cashq_style_neutral.py` (+ exported results JSON) |
| `*.json` (this folder) | Exported QuantConnect results for runs `01`, `02`, `04`, `05` |
| `ff5_regression.py` | Regresses each backtest's monthly returns on the published FF5 (and, as a check, UMD) factors; run with `uv run --with pandas --with numpy --with statsmodels python ff5_regression.py` |
| `data/ff5_umd_monthly_percent.csv` | Monthly FF5 and momentum factors, in percent, parsed from the Kenneth R. French Data Library (data through 2026-08) |
| `figures/` | Charts, `figure_stats.json`, `ff5_regression_results.csv`, `monthly_equity_by_run.csv` (month-end equity for every run, the table view of Figure 1) |
