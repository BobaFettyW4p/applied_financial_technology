# Assignment 1: Portfolio Strategy
## Strait of Hormuz Disruption — Second-Order Commodity Plays

---

## Macro Thesis

The Strait of Hormuz is the world's most critical maritime chokepoint, through which approximately **20% of global oil supply** and **20% of global LNG trade** passes daily. A closure or sustained disruption creates ripple effects well beyond crude oil prices — the story most investors will chase.

**Our angle:** The obvious trade (buy oil) will be crowded and likely already priced in within hours of a disruption (to quote the reading, we expect oil to be an Efficient Market). We focus on the **second-order commodity supply chains** that the market is slower to reprice, and the **Western producers** who become the only viable alternatives when Middle Eastern supply is cut off and Chinese supply is geopolitically unavailable.

### Why China Won't Help

A key structural element of this thesis is that China (~57% of global aluminum production, significant LNG capacity) is not a viable relief valve for US/Western markets:

- US-China relations are at a prolonged low; China has a demonstrated pattern of weaponizing commodity exports (rare earths, gallium, germanium) as geopolitical leverage
- Section 232 tariffs already restrict Chinese aluminum imports to the US market
- In a scenario where the US is adversely affected by Middle East disruption, China has every incentive to withhold supply rather than ease it

This removes the natural market relief valve and amplifies the price impact on Western producers.

---

## Portfolio Architecture

Rather than picking individual stocks and running a single large optimization (which suffers from the curse of dimensionality and high overfitting risk), we use a **two-level hierarchical structure**:

```
                        PORTFOLIO
                            |
           ┌────────────────────────────────┐
           │   Monte Carlo optimises        │
           │   weights between buckets      │
           └────────────────────────────────┘
                            |
    ┌──────────┬──────────┬──────────┬──────────┬──────────┐
 Aluminum    LNG/Gas  Fertilizer  Restock    Tanker
 (3 stocks) (4 stocks) (3 stocks) (3 stocks) (3 stocks)
    │            │          │          │          │
  equal wt    equal wt  equal wt  conviction  equal wt
```

**Why hierarchical?**

| Dimension | Flat (all 17 stocks) | Hierarchical (5 buckets) |
|---|---|---|
| Optimization space | 16-dimensional simplex | 4-dimensional simplex |
| Simulations needed | Millions for good coverage | 10,000 is sufficient |
| Overfitting risk | High | Low |
| Presentation clarity | "Why 7.3% AA vs 6.1% CENX?" | "35% to aluminum thesis" |

Each bucket is treated as a single synthetic asset (the equal-weighted return of its constituents). The Monte Carlo then searches over the much simpler 5-bucket weight space.

---

## The Five Buckets

### 1. Aluminum Supply Shock

**Thesis:** Emirates Global Aluminium (UAE, state-owned) is one of the world's largest producers and runs on cheap regional natural gas — Hormuz closure disrupts both their fuel input and their export route. With Chinese aluminum politically unavailable, Western producers capture the spread.

**Energy cost nuance:** Aluminum smelting consumes ~14,000 kWh per tonne. If energy prices spike globally, US smelters face higher costs on the same shock that raises their revenue. We mitigate this by overweighting Alcoa, whose hydro-powered smelters in Norway and Iceland provide a natural hedge.

| Ticker | Company | Role | Weight | Key reason |
|---|---|---|---|---|
| `AA` | Alcoa | Primary | **50%** | Largest Western producer; hydro-powered smelters in Norway and Iceland hedge the energy cost spike that would erode margins at grid-dependent peers |
| `CENX` | Century Aluminum | US pure-play | 25% | Highest beta to aluminum price; accepts more energy cost risk in exchange for more upside if the thesis plays out strongly |
| `NHYDY` | Norsk Hydro (ADR) | Norwegian | 25% | Fully hydro-powered like Alcoa, geopolitically neutral, insulated from both the supply disruption and the energy cost spike |

**Within-bucket weighting:** Conviction-weighted — AA 50%, CENX 25%, NHYDY 25%

> **Note for the group:** All three are primary aluminum producers who directly benefit from price spikes. AA is overweighted because its hydro-powered assets mean it captures the full revenue upside without bearing the full energy cost increase that grid-dependent smelters face. If the group prefers simplicity, equal weight at 33% each is equally defensible — the thesis direction is the same, only the internal emphasis differs.

---

### 2. LNG / Natural Gas Rerouting

**Thesis:** Qatar is the world's #1 or #2 LNG exporter; virtually all of its exports transit the Strait of Hormuz. A closure severs those routes. US Gulf Coast LNG terminals — already operating at high utilization — become the only large-scale alternative source for European and Asian buyers.

| Ticker | Company | Role | Key reason |
|---|---|---|---|
| `LNG` | Cheniere Energy | Primary | Largest US LNG exporter; Sabine Pass + Corpus Christi terminals |
| `EQT` | EQT Corporation | Gas producer | Largest US natural gas producer; higher NG prices = direct revenue benefit |
| `AR` | Antero Resources | Gas producer | Significant LNG export exposure; high leverage to NG price spike |
| `GLNG` | Golar LNG | Infrastructure | LNG shipping + FLNG assets; benefits from longer transit distances |

**Within-bucket weighting:** Equal weight (25% each)

---

### 3. Energy → Fertilizer Cascade

**Thesis:** This bucket has two independent, compounding catalysts.

**Catalyst 1 — Hormuz energy cascade:** The mechanism is not a direct shipping disruption (potash and phosphate don't primarily route through Hormuz) but rather:

```
Hormuz closure → global natural gas price spike
    → ammonia/urea production cost spike (~70-80% of input cost is natural gas)
        → nitrogen fertilizer shortage + price spike
            → demand pressure across all fertilizer inputs (potash, phosphate)
                → food security concerns → governments stockpile
```

US domestic producers benefit because they operate on domestic gas prices, insulated from the global spike that cripples Middle Eastern and European competitors.

**Catalyst 2 — US-Canada trade friction:** Canada holds the world's largest potash reserves and produces ~35-40% of global supply from Saskatchewan. Current US-Canada trade friction creates a second, independent tailwind for US domestic potash producers: if tariffs are imposed on Canadian imports, domestic producers receive a price premium that Canadian competitors cannot match.

**Critical note on Nutrien (`NTR`):** Nutrien is the world's largest potash producer but is **Canadian**, headquartered in Saskatoon. It is listed on the NYSE but its mines are in Canada — meaning tariffs on Canadian potash would hurt Nutrien's US market access. It was originally included in this bucket, but has been excluded due to risk of Candian tariffs negatively impacting it.

| Ticker | Company | Role | Key reason |
|---|---|---|---|
| `CF` | CF Industries | Nitrogen | Largest US nitrogen producer; domestic gas pricing is a structural cost advantage over Middle Eastern and European peers |
| `MOS` | Mosaic | Potash + phosphate | US-domiciled (Tampa, FL); benefits from global potash price spike; some Canadian mine exposure but net US beneficiary |
| `IPI` | Intrepid Potash | US domestic potash | Only significant US-domiciled potash producer (New Mexico + Utah); the pure-play beneficiary of **both** catalysts simultaneously |

**Within-bucket weighting:** Equal weight (33% each)

---

### 4. Interceptor Restocking (Defense)

**Thesis:** This is explicitly **not** a bet on escalation. Interceptor stores (THAAD rounds, PAC-3 MSE missiles, SM-3s, AMRAAM) have been substantially depleted through transfers to Ukraine and Israel over the preceding years prior to their accelerated use in the current conflict with Iran. These stores **must be replenished regardless of whether the Hormuz situation escalates** — the restocking cycle was already underway.

The asymmetric trigger structure:
- **If tensions stay contained:** Normal procurement restocking → multi-year backlog → locked revenue
- **If tensions escalate:** Emergency procurement + Congressional supplementals → same companies, higher urgency and volume

Production lead times for THAAD interceptors are 18-24 months, meaning contracts placed today translate to immediate backlog recognition.

**Key distinction — LMT vs RTX:**
- **LMT** makes the *interceptors themselves* (THAAD rounds ~$10M each, PAC-3 MSE kill vehicles) — the consumable that must be reordered after every firing
- **RTX** makes the Patriot *system* (radar, launchers) and SM-3 — benefits more from new system sales than from pure restocking; retained here for the SM-3 naval angle specifically relevant to Gulf operations
- **NOC** makes the IBCS (battle network integrating all interceptor systems) — sticky, long-cycle revenue

| Ticker | Company | Role | Key reason |
|---|---|---|---|
| `LMT` | Lockheed Martin | Primary | THAAD + PAC-3 MSE interceptors; the consumable logic is most direct |
| `RTX` | RTX Corp | Secondary | SM-3 for Navy ships in Gulf; Patriot system infrastructure |
| `NOC` | Northrop Grumman | Tertiary | IBCS integration; long-term sticky defense network revenue |

**Within-bucket weighting:** Conviction-weighted — LMT 60%, RTX 30%, NOC 10%

---

### 5. Disruption Duration (Tankers)

**Thesis:** A Hormuz closure forces tankers to reroute around the Arabian Peninsula, adding 7-10 days of transit each way. More ton-miles with the same global fleet means higher freight rates. This is a **tactical position** — it pays while the disruption lasts but is the most sensitive to resolution duration.

| Ticker | Company | Fleet type | Key reason |
|---|---|---|---|
| `FRO` | Frontline | Crude (VLCC) | Large crude tankers benefit most from long-haul rerouting |
| `STNG` | Scorpio Tankers | Product tankers | Refined fuel rerouting; different cargo type provides diversification within bucket |
| `INSW` | International Seaways | Mixed fleet | Crude + product exposure; smoother ride than pure plays |

**Within-bucket weighting:** Equal weight (33% each)

---

## Optimization Methodology

### Step 1: Construct bucket return series

For each of the 5 buckets, compute a daily return series as the weighted average of constituent stock returns (using the within-bucket weights above). This produces 5 synthetic time series.

### Step 2: Monte Carlo over bucket weights

Generate N random weight vectors over the 5-bucket simplex using a Dirichlet distribution (uniform draws, normalized). For each weight vector, compute:

- **Annualized portfolio return**
- **Annualized volatility** (using the 5-bucket covariance matrix)
- **Sharpe ratio** = (return − risk-free rate) / volatility

### Step 3: Select optimal allocation

Plot the efficient frontier and identify the **maximum Sharpe ratio portfolio** as the primary candidate. Also note the minimum variance portfolio for comparison.

**Key design decisions:**
- **Objective function:** Sharpe ratio (standard; balances return and risk)
- **Risk-free rate:** Current 3-month T-bill rate
- **Weight constraints:** 5% floor per bucket, 50% ceiling per bucket
- **Data window:** 3 years of historical daily returns
- **Simulation count:** 10,000 (sufficient for a 4-dimensional simplex)
- **Overfitting guard:** Optimize on 2022-2024, validate on 2025-present

---

## QuantConnect Implementation

The optimized bucket weights, combined with within-bucket weights, produce a final weight for each of the 17 stocks. These are implemented as a fixed-allocation buy-and-hold strategy in QuantConnect, with the backtest covering at least 1 year.

**Important:** Verify that all stocks were publicly traded at the backtest start date (IPO date check).

---

## Limitations of This Approach

These are worth discussing in the presentation as the assignment explicitly asks for them:

1. **Fixed allocation drift:** A buy-and-hold strategy doesn't rebalance, so weights drift over time as prices move. The portfolio you hold at month 12 may look very different from what you started with.

2. **Survivorship bias:** We're picking stocks we know exist and are liquid. Companies that delisted or went bankrupt during the backtest period are excluded, making historical performance look better than it would have been in real time.

3. **In-sample optimization:** Even with a train/test split, the Monte Carlo finds the historically optimal weights — not necessarily the forward-optimal ones. Correlation and volatility regimes shift.

4. **Asymmetric resolution risk across buckets:** This portfolio is not a bet that the Hormuz disruption *will* occur — it is a bet that the second-order commodity effects of an ongoing disruption are not yet fully reflected in prices, and that physical supply chain adjustments will take longer to unwind than any diplomatic resolution. The primary risk is not thesis failure but thesis timing: a rapid strait reopening would affect buckets very differently.

   | Bucket | Resolution risk | Reason |
   |---|---|---|
   | Tanker | High | Freight rates normalize within days as vessels reposition |
   | LNG | Moderate | Qatar exports restart in weeks; vessel repositioning adds lag |
   | Aluminum | Low-moderate | Smelters take months to restore full output; not an on/off switch |
   | Fertilizer (Hormuz cascade) | Low-moderate | Seasonal agricultural supply chains add lag to price normalization |
   | Fertilizer (Canada friction) | None | Driven by US-Canada trade policy, independent of strait status |
   | Interceptor restock | None | Pentagon procurement cycles operate on multi-year timelines regardless |

   The tanker position is therefore the most tactically sensitive and a more robust algorithm would dynamically be resized — or exited if a resolution appears imminent. The defense and domestic potash positions are structurally insulated.

5. **Thin within-bucket diversification:** With 3-4 stocks per bucket, idiosyncratic risk in any one stock has an outsize effect on bucket performance.

**Potential improvements:** Dynamic rebalancing on a fixed schedule, stop-loss triggers per bucket, regime-aware allocation that scales tanker exposure based on estimated disruption duration, and factor-based within-bucket weighting (e.g., momentum or quality screens).

---

## Next Steps

- [ ] Pull historical price data for all stocks
- [ ] Construct 5 bucket return series
- [ ] Run Monte Carlo simulation (10K iterations) to find optimal bucket weights
- [ ] Validate out-of-sample
- [ ] Implement final weights in QuantConnect backtest
- [ ] Record video walkthrough of backtest results
