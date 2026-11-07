# Midterm — Video Script
## F4: Trading the AI Ecosystem Long and Short

**Format:** 3–7 minute screen capture, face in corner, slides as the main visual (about 6 minutes at a normal pace; the "Disclosures" slide can be shortened if time is tight)
**Live demo:** QuantConnect run Q1 (default settings) shown at slide 9
**Strategy file:** `midterm/algorithms/f4_regime_spread.py`
**Presenter:** [name]

> **Before recording:** re-run the positioning check (it changes daily) and update slide 11. The numbers on slides 8-10 come from QuantConnect results and do not change. Positioning figures below are as of Friday, Nov 6, 2026 close, computed offline with Yahoo prices, not a QuantConnect live run.

---

## Slide 1 — Title
*"F4: Trading the AI Ecosystem, Long and Short"*

> Our midterm strategy trades the companies around the AI build-out. It's always invested in single stocks, it can go short when the trend turns, and right now the AI group is in a sharp sell-off, so we can show how it's positioned.

---

## Slide 2 — The thesis, in one sentence
*"AI demand flows through a chain: customers → clouds → chips → memory → data centers. The chain moves together, but not at the same speed."*

> ChatGPT launched on November 22, 2022. That's our start date, because that's when this trade began. Our thesis is that AI spending ripples through a supply chain, and the stocks in that chain are connected: when one part of it moves, the others tend to follow, and the strength of the memory names relative to the buyers tells us where the cycle is.

---

## Slide 3 — Where we found the chain: Anthropic's S-1
*Visual: three quotes from the S-1, with the company names highlighted*

> We built the universe from Anthropic's S-1. Claude runs on all three major clouds: AWS, Google Cloud and Azure. It trains and serves on four chip families: Amazon's Trainium, Google's TPUs, NVIDIA and AMD GPUs. It buys from Broadcom, and it relies on data-center partners. The S-1 also says customer demand exceeds available compute. Compute is the bottleneck, so the suppliers of compute are where we look.

---

## Slide 4 — The 18 stocks
*Visual: four colored groups*

> Eighteen names in four groups. Hyperscalers, the buyers: Amazon, Google, Microsoft, Meta, Oracle, IBM. Chips: NVIDIA, Broadcom, AMD. Memory, our core idea: Micron, Western Digital, Seagate, SanDisk. And infrastructure: Dell, Arista, Vertiv, Equinix, Constellation. We chose these knowing how the story played out, so we'll be upfront that the list has hindsight in it.

---

## Slide 5 — The first sleeve: a regime signal
*Visual: three icons, one for each test, with a dial going from "net short" to "net long"*

> Half the capital runs on a regime signal. We build an equal-weight index of the 18 stocks and ask three questions. Is it above its 50-day average? Above its 100-day average? And are more than half of the stocks above their own 50-day averages? All three yes, we're fully net long the basket. All three no, we're fully net short. In between, we scale down gradually, so it never flips all at once.

---

## Slide 6 — The second sleeve: memory versus the buyers
*Visual: ratio chart of the memory basket divided by the hyperscaler basket, with the 100-day average*

> The other half bets on a relationship. When memory stocks are outperforming the hyperscalers and the trend is up, we go long memory and short the hyperscalers. When the trend turns, we reverse. That's because memory is the most sensitive part of the chain to AI capital spending. We size it to a 15% volatility target so it can't dominate, and use a small SPY position to cancel its market exposure.

---

## Slide 7 — How we got here, including what failed
*Visual: a table of what we tried, with a red cross for each failed idea*

> We started with about 80 rule variations and kept a record of every one. Momentum rankings lost money in the 2022 bear. A rule that bets the hyperscalers lead the chip stocks by two days lost 37% in a year. Shorting the group when it's weak turned out to cost us more than simply moving to SPY. F4 survived because it combines two things that worked in different periods, a regime signal and the memory relationship, and it's built to lose less when the group falls.

---

## Slide 8 — The QuantConnect result
*Visual: equity curve of F4 against SPY, Q1*

> Running from the ChatGPT launch through August 2026, F4 returned 25.7% a year against 21.5% for SPY, a modest edge, not a large one. Its worst drawdown was 15.7%. Its beta to the market was 0.11, so it isn't just riding the market. Adding 10 basis points of slippage on every trade cut that to 23.3%.

---

## Slide 9 — LIVE DEMO: QuantConnect
*Show the Q1 backtest: equity curve, statistics, and the long/short exposure chart*

> Here's the live backtest. You can see the equity curve, 2,635 orders over about four years, and the exposure chart showing the days we're net short. It's mostly long, with the short side kicking in during sell-offs.

---

## Slide 10 — Does it hold up? Two halves
*Visual: two small tables, first half and second half*

> We split the window in half. The first half returned 21% a year with a drawdown under 10%, a little behind SPY's 24% because the strategy was mostly hedged while the group ran. The second half returned 29% with a 15.7% drawdown, well ahead of SPY's 19.5%. We were careful here: a four-year window is short, and a Sharpe over four years carries a lot of statistical noise.

---

## Slide 11 — Where is F4 right now?
*Visual: the current positions table, with the net exposure highlighted*

> This week the group fell to about 17% below its recent trend, with the worst day on Thursday, down 10% for the basket and 18% for the memory names. All three of F4's signals are now bearish. As of Friday's close the strategy is net short about 50% of capital across the 18 names, with the memory stocks most short, and a 24% SPY position offsetting part of the market risk. It's positioned for the decline to continue.

---

## Slide 12 — What could go wrong
*Visual: a histogram of next-20-day returns after all three signals turned bearish*

> We should be honest about the risk. We looked at every time all three signals turned bearish together. In most cases the group rebounded. The average next-20-day return was positive, about 3%, and only a quarter of the time did the group keep falling. So this is a bet on continuation, and the main danger is a sharp bounce. That's the reason the short side is capped by the volatility target and hedged with SPY.

---

## Slide 13 — Disclosures
*Visual: a list of five short bullet points*

> Five things you should know. One: the stocks were chosen with hindsight. Two: about 87 rule variations were tested on this data, so some of the result will be luck, and QuantConnect's probabilistic Sharpe is only 39%, so we can't be confident it's skill. Three: the regime windows were tuned after seeing 2022. Four: before the AI era, the same approach earned much less than SPY, about 4% a year against 12% in our offline test. Five: F4 failed our own pre-declared test, because it had to make money in 2022 and it didn't. We're showing it because it's the best protection we found, not because it passed every test.

---

## Slide 14 — Why F4 and not the alternatives
*Visual: a three-column comparison, F4 / gated AI basket / memory basket*

> We also built a long-only version that holds the stocks when the trend is up and SPY otherwise. It returned 63% a year, but with a beta of 1.4, so it's the AI trade, not a hedge. The old memory basket returned more still, but with a 44% drawdown. We chose F4 because, with the group already in a downtrend, we want the strategy that is built to be short and hedged, and the one that gave up the least in a bear.

---

## Slide 15 — Close
*"A long/short bet on the AI chain, sized to survive being wrong."*

> F4 is a long/short strategy on the AI ecosystem. It's net short right now. It earned about 26% a year in the backtest with a shallow drawdown, and we've told you where it's weak. If the sell-off continues, it's positioned for it. If the group rebounds, the volatility target and the hedge are there to limit the damage.

---

## If asked (Q&A cheat sheet)

* **"Why not just use the long-only version?"** It earned more in the bull market but carries beta of 1.4. We wanted the one that protects when the group falls.
* **"Is the 25.7% real?"** It's a QuantConnect backtest with default fees and one tested slippage case (23.3% at 10 bps). Statistical confidence is low (probabilistic Sharpe 39%) and the window is short.
* **"Why does the short side matter if rebounds usually follow?"** Because the regime signal only flips net short after a large fall; in the backtest the short sleeve helped in 2018-style grinding declines and hurt in V-shaped recoveries. We show both.
* **"What's the most likely way F4 loses money from here?"** A violent rebound in the first few weeks. A rebound of 8% to 29% in the basket has followed past bearish signals.
* **"Did you look at the data to pick the window?"** The window start, the ChatGPT launch, was a thesis choice made before the final tests, but several rule parameters were tuned on data that overlaps it.

## Facts used in this script (all from files in this folder)
* QC runs Q1-Q5 (`qc_f4_results.csv`): 25.7% / Sharpe 0.985 / DD 15.7% / beta 0.11 / PSR 38.7% / 2,635 orders; +10 bps: 23.3%; halves 21.3% (DD 9.9%) and 29.1% (DD 15.7%); SPY 21.5%.
* Offline positioning, Nov 6 2026: net stock exposure -0.5, SPY +0.24, gross 0.74, basket 17% below its 50d and 100d averages, 17% of names above their own 50d.
* This week (equal-weight basket): Thu Nov 5 -10.0%, memory -18.3%; Fri Nov 6 +2.3%.
* After all three signals turned bearish (58 episodes since 2012): mean next-20-day basket return +3.4%, median +4.5%, 24% fell, range -14.8% to +29.3%.
* Pre-AI (2011 to 2022-11-21), offline F4: Sharpe 0.37, CAGR 4.4% vs SPY 12.2%.
* Alternatives: gated AI basket 62.9% CAGR, beta 1.36, DD 27.8% (QC R1); memory basket -44% drawdown (offline AI era).
* The S-1 statements: Claude on AWS, GCP and Azure; four chip families; Broadcom as a supplier; Fluidstack data-center services; demand exceeds compute.
