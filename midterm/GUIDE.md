# Midterm guide for teammates (read this first)

You do not need to read the research files to present this. This page gives you the story, the five numbers, the six files that matter, and what to be careful saying.

## The story in one paragraph
Our thesis is the AI trade after ChatGPT launched (22 Nov 2022). AI spending flows through a chain of companies (cloud buyers, chips, memory, data centers) and their stocks move together. We tested about 87 trading rules on 18 stocks from that chain and kept the one built to hold up if the group keeps falling: **F4**. F4 is always invested in single stocks, goes net short when the group's trend breaks, and earned 25.7% a year (SPY 21.5%) with a 15.7% worst drawdown on QuantConnect. It is net short about half its capital right now.

## What F4 does (plain English)
F4 splits its money 50/50 between two strategies:
1. **Regime sleeve.** Build an equal-weight index of the 18 stocks. Count three tests: index above its 50-day average, above its 100-day average, and more than half the stocks above their own 50-day averages. 3 passes = fully net long, 0 passes = fully net short, in between scales gradually.
2. **Spread sleeve.** Compare the memory stocks (Micron, Western Digital, Seagate, SanDisk) with the cloud buyers (Amazon, Google, Microsoft, Meta, Oracle, IBM). If memory is outperforming and the trend is up, go long memory and short the buyers; otherwise reverse. Size it to a 15% volatility target and use a small SPY position to cancel market risk.

The 18 stocks: MU WDC STX SNDK | NVDA AVGO AMD | AMZN GOOGL MSFT META ORCL IBM | DELL ANET VRT EQIX CEG.

## The five numbers to know
| Number | Meaning |
|---|---|
| **25.7% vs 21.5%** | F4's yearly return vs SPY, 22 Nov 2022 to 7 Aug 2026 (QuantConnect) |
| **15.7%** | worst peak-to-trough loss over that window |
| **0.11** | beta: how much F4 moves with the market (SPY is 1.0); low means it is hedged |
| **39%** | QuantConnect's probabilistic Sharpe: low, so we cannot be confident the edge is skill |
| **+3.4%, 24%** | after all three regime tests turned bearish, the basket's average next-20-day return, and how often it kept falling: the main risk is a rebound |

## How we got here (six steps, with the file to open)
1. **Universe.** Read the Anthropic S-1 for named partners (three clouds, four chip families, Broadcom, data centers), kept memory as the core. Chosen with hindsight.
2. **Relationship research.** Which stocks lead or follow each other? Only memory-vs-buyers ratios trended. `rel_research.py`
3. **Many rules, mostly failures.** Momentum rankings, a "hyperscalers lead chips" trade, shorting variants, overnight-only holding. Each was written down with a pass rule before running. `mem_ls.py` through `mem_ls9.py`
4. **A near miss.** Memory-vs-buyers spread with a volatility target (`mem_ls3.py`, N2) and a regime signal that can go short (`mem_ls5.py`, `mem_ls6.py`) were the two best ideas. F4 is their 50/50 combination. It missed our own 2022 rule.
5. **Moved the window** to start at the ChatGPT launch.
6. **Confirmed on QuantConnect.** Five runs: default, extra costs, tighter order band, each half of the window. All passed the rules we wrote before running. `QC_F4_PLAN.md`

## The six files that matter
| File | What it is |
|---|---|
| `algorithms/f4_regime_spread.py` | the strategy as it runs on QuantConnect |
| `QC_F4_PLAN.md` | the QC test plan, pass rules and verdicts |
| `SCRIPT.md` | the short (3 to 7 minute) video script |
| `F4_midterm_deck.pptx` | the sample slides for an 8 to 15 minute talk, with speaker notes |
| `mem_ls6.py` | where F4's regime sleeve and combination were defined and tested |
| `f4_parity_check.py` | proves the QuantConnect code matches the research numbers |

Everything else in the folder is lab notebook: it records what we tried. You can ignore it.

## How to re-run
* **On QuantConnect:** paste `f4_regime_spread.py` into a new project. To run a variant, edit only the `OVERRIDES = {}` line at the top (examples are in the file). Defaults run 22 Nov 2022 to the latest data.
* **Locally:** the research scripts need the price files in `data/` (about 200 MB, not in the repo). Ask [name] for them before running anything with `mem_` in its name.

## Glossary
* **CAGR / return per year:** average yearly growth rate.
* **Drawdown:** biggest fall from a peak to a later low.
* **Beta:** sensitivity to the market. 1.0 moves with SPY, 0 is independent.
* **Sharpe:** return per unit of risk; QuantConnect subtracts the risk-free rate, so its number is lower than ours offline.
* **Regime:** a label for whether the group is in an uptrend or downtrend.
* **Spread:** being long one group and short another, so the result depends on their difference.
* **Short:** profiting when a stock falls.

## Say this, not that
* Say: "F4 is positioned for the decline to continue and built to survive a rebound." Not: "The decline will continue." History says bearish signals like this were usually followed by a rebound.
* Say: "It failed our own 2022 test; we chose it for protection." Do not say it passed everything.
* Say: "The stocks were chosen with hindsight and about 87 variants were tested." Do not present the 25.7% as a forecast.
* The first half of the window F4 trailed SPY (21% vs 24%). Do not say "beat SPY in both halves".

## Before recording
* Re-run the positioning check; the "where is F4 today" slide (slide 12) uses 6 Nov numbers.
* Put presenter names on slide 1 and add the QuantConnect screen capture on slide 10.
* Check the timing: 17 slides is about 11 to 12 minutes; skip slides 8 and 15 for 8 minutes, and keep the backup slide (17) for questions.
