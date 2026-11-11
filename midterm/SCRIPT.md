# Situational Humility: video narration script

**Deck:** `Situational_Humility_deck_final.pptx`, all 23 slides in order (none hidden). **Strategy file:** `algo/main.py`.
**Target:** under 15 minutes (the assignment allows 8-15). Timing is estimated from word counts at about 140 words a minute; see the table at the end.

How to read this script:
- Lines starting with `>` are spoken. Everything else is a note to the presenter.
- Numbers in **[square brackets]** change with the market. They are set to the Tuesday 10 November close; if you record after another close, refresh them with `python src/today.py` (they must match slide 13).
- Stage directions are in *italics*.

---

## Slide 1: Title

> Hi, I'm Tom Dickson, presenting for our group with Charlotte Roth and Matthew Ivancic. Our strategy is called Situational Humility. It trades the companies around the AI build-out, and the idea fits in one line: awareness tells you what is happening; humility sizes the bet. It's always invested in single stocks, it can go short when the trend turns, and the AI group has just been through a sharp sell-off, so we can show you how it's positioned today.

## Slide 2: Motivation

> Big IPOs move the companies around them. Hsu, Reed and Rocholl studied 134 large IPOs from 1980 to 2001, and found that listed rivals lost about 0.8 percent around the IPO, because a newly public competitor is stronger and better funded. That paper is about rivals, not suppliers, so it told us where to look, not what to bet. Anthropic's IPO made us ask which public companies are tied to it, and whether those links create trading opportunities.

## Slide 3: The chain

> We focused on the supply chain, where the links are strongest. Customers buy AI models like Claude, which run on the big clouds, which buy chips, memory and data-center capacity. Our thesis: AI spending ripples through this chain, so these stocks move together, and memory's strength against the buyers tells us where the cycle is. Our backtests start on November 22, 2022, the week before ChatGPT launched, so they cover the whole AI trade. The question: which parts of the chain lead, and which break first?

## Slide 4: Anthropic's S-1

> We built the list of stocks from Anthropic's S-1 filing. Claude is sold through all three major clouds: AWS, Google Cloud and Azure. It's trained and served on four chip families: Amazon's Trainium, Google's TPUs, and NVIDIA and AMD GPUs, and Broadcom is a named supplier. And the S-1 says customer demand exceeds available compute. Compute is the bottleneck, so the suppliers of compute are where we look.

## Slide 5: Eighteen stocks

> That gives us eighteen stocks in four groups. The hyperscalers, the buyers of compute: Amazon, Google, Microsoft, Meta, Oracle and IBM. The chips: NVIDIA, Broadcom and AMD. Memory, our core idea: Micron, Western Digital, Seagate and SanDisk. And infrastructure: Dell, Arista, Vertiv, Equinix and Constellation. One thing up front: we chose these names knowing how the AI story played out, so the list has hindsight built in. We'll come back to that, and test it.

## Slide 6: Two sleeves

> Situational Humility runs two strategies side by side, with half the capital each. The first is a regime signal: is the AI basket trending up or down? The second bets on a relationship: memory against the cloud buyers. Everything is in single stocks. The only SPY position is a hedge that cancels the market exposure of the second sleeve.

## Slide 7: Regime sleeve

> The regime sleeve builds an equal-weight index of the 18 stocks and asks three yes-or-no questions. Is the basket above its 50-day average? Above its 100-day average? And are more than half the stocks above their own 50-day averages? Three yeses: fully net long. Three noes: fully net short. One or two yeses give a partial position. So it usually moves one step at a time, though one sharp day can flip all three tests at once.

## Slide 8: Spread sleeve

> The spread sleeve compares a memory basket with a hyperscaler basket. When memory is beating the hyperscalers, meaning this ratio is above its 100-day average, we go long memory and short the hyperscalers. Below the average, we reverse. Memory is the part of the chain most sensitive to AI spending. The sleeve is sized to a 15 percent volatility target, so it shrinks when the spread gets wild, and the SPY hedge cancels its market exposure. It's a bet on the relationship, not the market. Notice the ratio fell below its average this autumn.

## Slide 9: What we tried

> Before settling on this, we tested about 80 ideas, and most of them failed. Ranking stocks by momentum, long the winners and short the losers, lost 16 to 30 percent in the 2022 bear market. Betting that the hyperscalers lead the chip stocks by two days lost 37 percent in 2021, and again in 2022. Holding the basket only overnight looked great, until it lost 38 percent in 2022. Situational Humility survived because it combines two signals that worked in different periods, and it's built to lose less when the group falls.

## Slide 10: Result

> Here's the QuantConnect backtest, from November 22, 2022 to August 7, 2026, with default fees. Situational Humility returned 25.7 percent a year, against 21.5 for SPY. That's a modest edge, not a large one. Its worst drawdown was 15.7 percent, and its beta to the market was 0.11, so it isn't just riding the market. Adding 10 basis points of slippage on every trade cuts the return to 23.3 percent.

## Slide 11: Live demo

*Before you start recording: open the finished QuantConnect backtest Q1 in your browser (default settings, 22 Nov 2022 to 7 Aug 2026: 25.7% a year, 2,635 orders), let every chart load, and click the browser and then Keynote, so the browser is the last app you used. Don't start a new backtest.*

*On this slide, press H to hide the slideshow and jump to the browser. Point at three things, in this order: the equity curve against SPY, the statistics (drawdown 15.7%, beta 0.11, 2,635 orders), and the exposure chart (long and short exposure over time).*

> Let's look at the run itself. Here's the equity curve against SPY, and here are the statistics: the 15.7 percent drawdown and the beta of 0.11. The run placed 2,635 orders in about four years, because it checks every day, five minutes before the close, and trades when a position drifts more than 2 percent from target. And this is the exposure chart: net long most of the time, with the short side kicking in during sell-offs, which is what the regime sleeve is built to do.

*Click Keynote in the Dock to return to the slideshow, then advance to slide 12.*

## Slide 12: Two halves

> We also split the QuantConnect window in half. The first half returned 21 percent a year with a drawdown under 10 percent, a little behind SPY's 24. The second half returned 29 percent, well ahead of SPY's 19.5. And four years is short: the Sharpe ratio's error band is about plus or minus 0.6.

*The slide's cost card (10 bps of slippage trims 2.4 points) and the probabilistic Sharpe of 39% are spoken on slides 10 and 20, so they aren't repeated here.*

## Slide 13: Today

*Values as of the Tuesday 10 November close, which is what slide 13 shows in the final deck. If you record after another close, rerun `python src/today.py` and update slide 13 and the bracketed numbers together.*

> So where is it right now? Last week the AI group sold off hard: on **[Thursday]** the basket fell **[10]** percent and the memory names **[18]**. It bounced about **[8]** percent over **[Friday and Monday]**, then slipped **[1.1]** percent on **[Tuesday]**. At **[Tuesday's]** close the basket is still **[12 to 13]** percent below its 50- and 100-day averages, so all three tests are still bearish. The strategy is net short about **[half]** its capital, with memory the most short, and a **[25]** percent SPY position offsetting part of the market risk. These are offline numbers from Yahoo prices, not a live QuantConnect run.

*The slide's two session cards are the last two sessions (Mon 9 Nov: basket +5.8%, memory +8.0%; Tue 10 Nov: basket -1.1%, memory -1.3%). Thursday's fall and Friday's +2.3% are spoken context.*

## Slide 14: The risk

> We should be honest about the risk. Since 2012, all three signals turned bearish together 58 times. Usually the group rebounded: the average return over the next 20 days was plus 3.4 percent, the median plus 4.5, and only about a quarter of the time did it keep falling. So being short here is a bet that the fall continues, and the main danger is a sharp bounce. That's why the net short is capped at half the capital, the spread shrinks when volatility rises, and SPY offsets part of the market risk.

## Slide 15: Test 1, random baskets

> Now the part where we tried to break it. These tests use our own offline engine, so every alternative runs the same way; on QuantConnect's dates it gives 25.0 percent a year, against 25.7. First question: is it the rules, or the names? We ran the same rules on 500 random baskets of tech and communication stocks, with the same structure, costs and dates. The typical basket loses money: the median Sharpe ratio, which is return per unit of risk, is minus 0.39, and the median return about minus 6 percent a year, while stocks went up. Our 18 names score 1.43, above all 500. So it beats luck, but read it the other way too: the rules have no edge on their own. The result depends on these names, picked with hindsight.

## Slide 16: Test 2, before the AI boom

> Second test: before the AI boom. We ran the strategy unchanged on 2016 to 2019. It returned 5.1 percent a year against 14.7 for SPY, a Sharpe of 0.44 against 1.13, with a worse drawdown. But look at 2018: SPY fell 4.6 percent and Situational Humility gained 12.8. Then in 2019 it gave it all back, minus 18.7 percent while SPY rose 31. We haven't split that loss between the sleeves, so we don't claim to know why. Two of our three pre-set pass rules passed: a partial verdict. And the names are still hindsight picks, so this is out of cycle, not out of sample.

## Slide 17: Test 3, a one-line trend switch

> The third test surprised us most. Drop all the machinery, and just hold the same 18 stocks equally while their basket is above its 100-day average, and cash otherwise. That one-line rule has a higher Sharpe than Situational Humility in the AI era, 1.87 against 1.43, and in 2016 to 2019, 1.28 against 0.44, with a third of the trading. It also cuts the worst drawdown from 32 percent for always holding to 21. To be fair, the switch is long-only and carries market risk, while our strategy is hedged and can go short. So the honest reading: Situational Humility doesn't add risk-adjusted return over a trend filter; it trades return for low market exposure. And just holding the names earned the most, because they are hindsight winners.

## Slide 18: Test 4, sell-offs and rebounds

> This is the claim that matters most: does it protect when the AI group falls? Mostly, yes. In the 2018 sell-off it made 6.9 percent while SPY lost 6.1. Over 2020 and 2021, including COVID, its worst drawdown was 18.5 percent against 33.7 for SPY. In the AI era its worst drawdown, 15.1, is the shallowest here, against 31.9 for holding the stocks. The trend switch gets part of this protection, but it can't go net short, as Situational Humility did a week after the 2018 memory peak. The cost is the last row, the 2019 rebound we just saw. Only the 2018 sell-off against SPY was a pre-registered test; the rest is descriptive, so treat it as evidence, not proof.

## Slide 19: What did not help

> We also tried to turn our regime-change hunch into a signal. These 18 stocks grew from about 10 percent of S&P 500 market cap in early 2016 to about 31 percent now. We tested two signals, each set up in advance and run once. First, share of trading volume didn't predict the next 20 days beyond the price trend, and it flagged only 2 of 11 big declines, against 10 of 11 for a plain 100-day price switch. Second, market-cap share as a veto on the trend switch passed 2 of 6 rules, so we left the strategy unchanged. Market-cap share mostly moves with price: it shows how big the AI trade became, but it isn't a better signal.

*About the caption: its "correlation about 0.6 with relative return" was measured for market-cap share (EXP-007). Volume share, counted in shares, actually moved opposite to price (EXP-006). The narration ties the price link to market-cap share only; keep it that way if you ad-lib.*

## Slide 20: Before you trust it

> Before you trust any of this, five things. One: the stocks were chosen with hindsight. Two: we tried about 80 rule variations on this data, so some of the result is luck; QuantConnect's probabilistic Sharpe is only 39 percent. Three: the 50- and 100-day windows were chosen after seeing 2022. Four: before the AI era it earned far less than SPY, about 4 percent a year from 2011 to 2022 against 12, in our offline test. And five, not on the slide: it failed our own pre-declared rule, a positive 2022. We show it because it's the best protection we found, not because it passed every test.

## Slide 21: Why not the alternatives

> Why this strategy and not the alternatives? We also built a long-only version that holds the stocks when the trend is up and SPY otherwise. It returned 63 percent a year, but with a beta of 1.4 it's the AI trade, not a hedge. A pure memory basket returned even more, with a 44 percent drawdown. In 2022, before our window, those two lost 23 and 28 percent; Situational Humility lost about 6. With the group already falling, we chose the one built to be short and hedged.

## Slide 22: Close

> To sum up: Situational Humility is a long/short bet on the AI supply chain, sized to survive being wrong. It's net short about half its capital right now, with memory the most short. It earned about 26 percent a year in the backtest, with a 16 percent worst drawdown, and we've shown you where it's weak. If the sell-off continues, it's positioned for it. A sharp rebound in the next few weeks is the main risk, and the hedge and the position limits are there to contain the damage.

## Slide 23: Backup, the five QuantConnect runs

> For reference, this last slide lists all five QuantConnect runs. Extra slippage or a tighter trading band cost between 1.6 and 2.4 points a year, and both halves of the window made money. Thanks for watching.

*Backup slide, kept for this recording. If you drop it later, move "Thanks for watching" back to the end of slide 22.*

---

## Timing (about 140 words a minute)

| Slide | Words | Time at 140 wpm | Running total |
|---|---|---|---|
| Slide 1: Title | 79 | 0:34 | 0:34 |
| Slide 2: Motivation | 78 | 0:33 | 1:07 |
| Slide 3: The chain | 86 | 0:37 | 1:44 |
| Slide 4: Anthropic's S-1 | 68 | 0:29 | 2:13 |
| Slide 5: Eighteen stocks | 75 | 0:32 | 2:45 |
| Slide 6: Two sleeves | 59 | 0:25 | 3:11 |
| Slide 7: Regime sleeve | 77 | 0:33 | 3:44 |
| Slide 8: Spread sleeve | 94 | 0:40 | 4:24 |
| Slide 9: What we tried | 92 | 0:39 | 5:03 |
| Slide 10: Result | 70 | 0:30 | 5:33 |
| Slide 11: Live demo | 87 | 0:37 | 6:11 |
| Slide 12: Two halves | 54 | 0:23 | 6:34 |
| Slide 13: Today | 103 | 0:44 | 7:18 |
| Slide 14: The risk | 93 | 0:40 | 7:58 |
| Slide 15: Test 1, random baskets | 133 | 0:57 | 8:55 |
| Slide 16: Test 2, before the AI boom | 106 | 0:45 | 9:40 |
| Slide 17: Test 3, a one-line trend switch | 128 | 0:55 | 10:35 |
| Slide 18: Test 4, sell-offs and rebounds | 121 | 0:52 | 11:27 |
| Slide 19: What did not help | 119 | 0:51 | 12:18 |
| Slide 20: Before you trust it | 107 | 0:46 | 13:04 |
| Slide 21: Why not the alternatives | 88 | 0:38 | 13:42 |
| Slide 22: Close | 89 | 0:38 | 14:20 |
| Slide 23: Backup, the five QuantConnect runs | 36 | 0:15 | 14:35 |
| **Total (23 slides)** | **2042** | **14:35** | |

Word counts cover the spoken lines only (lines starting with `>`); headings and stage directions are excluded.
- **Pace:** the same 2,042 words take about 15:42 at 130 words a minute and 13:37 at 150.
- **Numbers:** the script has 133 of them, and numbers take longer to say than ordinary words. Counting each as about 2.5 spoken words gives about 16:00 at 140.
- **Live demo:** switching to QuantConnect and back on slide 11 adds roughly 10-20 seconds.

So a careful, slow read could run past 15 minutes. Time your first take.

**If the first take runs over about 14:45**, make these cuts, in order. Each one removes only words, so nothing else needs rewording.

| # | Slide | Cut this | Saves |
|---|---|---|---|
| 1 | 13 | "These are offline numbers from Yahoo prices, not a live QuantConnect run." (the slide's source line says it) | ~5 s |
| 2 | 17 | "And just holding the names earned the most, because they are hindsight winners." | ~6 s |
| 3 | 19 | ", and it flagged only 2 of 11 big declines, against 10 of 11 for a plain 100-day price switch" (end the sentence at "price trend.") | ~8 s |
| 4 | 9 | "Betting that the hyperscalers lead the chip stocks by two days lost 37 percent in 2021, and again in 2022." (the table shows it) | ~9 s |
| 5 | 23 | All of slide 23's narration. Click through it silently, and move "Thanks for watching." to the end of slide 22. | ~15 s |

All five together save about 43 seconds, bringing the estimate to about 13:50 at 140 words a minute.
