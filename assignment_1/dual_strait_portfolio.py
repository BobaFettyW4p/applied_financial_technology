# region imports
from AlgorithmImports import *
# endregion

class DualStraitDisruptionPortfolio(QCAlgorithm):
    """
    Strait of Hormuz + Bab al-Mandeb — Second-Order Commodity Plays

    Extends the Hormuz-only portfolio with a sixth bucket (Container Shipping)
    capturing the BaM-specific disruption to Asia-Europe container routes.

    Strategic rationale: the Hormuz portfolio earned most of its return *before*
    the Feb 28 2026 official closure — the market priced in the disruption in
    advance. This portfolio is structured to capture the equivalent pre-closure
    run-up if Bab al-Mandeb tensions escalate.

    Two-level hierarchical structure:
      1. Within-bucket weights set by conviction (same as Hormuz portfolio)
      2. Bucket weights from 6-bucket Monte Carlo on 2022-2024 data (max Sharpe)
         — see assignment_1/dual_strait_optimization.ipynb

    Key changes vs Hormuz-only:
      - Container Shipping bucket added: GSL (Global Ship Lease)
          3.3yr avg charter duration → fastest repricing into a rate spike
          ZIM excluded: Israeli-flagged vessels are Houthi targets in the same
          scenario that closes BaM — wrong structure for a long position
      - Tankers allocation raised: dual closure is the extreme ton-mile scenario
      - LNG/Gas allocation reduced slightly: thesis remains strong, redistributed
        to fund the new bucket and higher tanker weight

    Backtest period: Jan 2025 – present (fully out-of-sample vs 2022-2024 window)
    Hormuz closure declared: Feb 28, 2026
    """

    def initialize(self):
        self.set_start_date(2025, 1, 1)
        self.set_end_date(2026, 10, 1)
        self.set_cash(10_000_000)

        # ── WEIGHTS ────────────────────────────────────────────────────────────
        # Source: dual_strait_optimization.ipynb (6-bucket Monte Carlo, max Sharpe)
        # Format: bucket_weight × within-bucket conviction weight
        #
        # NOTE: Replace the placeholder weights below with the actual output
        # from the notebook. The bucket structure and tickers are final;
        # only the numeric weights need updating after the notebook runs.
        #
        # Proposed bucket totals (pre-Monte Carlo, from strategy.md):
        #   Aluminum 10% | LNG/Gas 28% | Fertilizer 10% | Defense 18%
        #   Tankers 24%  | Container 10%
        # ──────────────────────────────────────────────────────────────────────

        # Final per-stock weights:
        #   bucket_weight (from 6-bucket Monte Carlo) × within-bucket conviction weight
        # Bucket totals: Aluminum 5.1% | LNG/Gas 29.3% | Fertilizer 5.4%
        #                Defense 28.1% | Tankers 24.2% | Container 7.8%
        #
        # Monte Carlo details: 10,000 Dirichlet draws, 2022-2024 data, max Sharpe
        # Tankers capped at 25%: highest resolution risk of all buckets; normalization
        # within days if either strait reopens. MC would have gone to 34.5% unconstrained.
        # Capital freed from tanker cap flows to Defense (structurally insulated,
        # multi-year procurement cycles independent of strait status).
        # Sharpe of optimal portfolio: 1.026 | Ann. Return: 28.1% | Ann. Vol: 23.2%
        # See: assignment_1/dual_strait_optimization.ipynb
        self.HOLDINGS = {
            # --- Aluminum (5.1%) ---
            # UAE smelters shut down; Chinese aluminum politically unavailable;
            # Western hydro-powered producers capture the spread.
            # AA overweighted: hydro smelters (Norway/Iceland) hedge the energy
            # cost spike that erodes margins at grid-dependent peers.
            "AA":    0.025582,   # Alcoa — 50% of bucket; hydro smelters in Norway/Iceland
            "CENX":  0.012791,   # Century Aluminum — 25%; highest beta to Al price
            "RIO":   0.012791,   # Rio Tinto — 25%; NYSE-listed; hydro exposure (Iceland, Quebec)

            # --- LNG / Natural Gas (29.3%) ---
            # Qatar LNG routes through Hormuz; Hormuz + BaM dual closure means
            # Qatar LNG cannot reach Europe via either route.
            # US Gulf Coast terminals become the sole large-scale alternative.
            "LNG":   0.073312,   # Cheniere Energy — largest US LNG exporter
            "EQT":   0.073312,   # EQT Corp — largest US natural gas producer
            "AR":    0.073312,   # Antero Resources — high LNG export leverage
            "GLNG":  0.073312,   # Golar LNG — shipping + FLNG; benefits from longer transits

            # --- Fertilizer (5.4%) ---
            # Catalyst 1: Hormuz → NG spike → ammonia cost spike → nitrogen shortage
            # Catalyst 2: US-Canada trade friction → domestic potash premium (independent of straits)
            "CF":    0.018127,   # CF Industries — largest US nitrogen producer
            "MOS":   0.018127,   # Mosaic — US potash + phosphate
            "IPI":   0.018127,   # Intrepid Potash — only US domestic potash pure-play; both catalysts

            # --- Interceptor Restocking / Defense (28.1%) ---
            # NOT a bet on escalation. THAAD/PAC-3 stores depleted; restocking
            # cycle multi-year and independent of strait status.
            # Defense stepped up significantly when tanker cap was applied — the MC
            # correctly identified it as the best structurally insulated alternative.
            "LMT":   0.168451,   # Lockheed Martin — 60%; THAAD + PAC-3 MSE (the consumable)
            "RTX":   0.084226,   # RTX Corp — 30%; SM-3, Patriot system; naval angle
            "NOC":   0.028075,   # Northrop Grumman — 10%; IBCS battle network

            # --- Tankers (24.2%) ---
            # Both straits closed: all Gulf-to-Europe AND Asia-Europe tankers
            # reroute Cape of Good Hope. Ton-miles roughly double.
            # Capped at 25%: tankers are the most resolution-sensitive position —
            # freight rates normalize within days if either strait reopens.
            # Meaningful step up from Hormuz-only (18.9%) to reflect the stronger
            # dual-closure thesis, but not the 34.5% the unconstrained MC wanted.
            "FRO":   0.080770,   # Frontline — VLCC crude tankers; most benefit from long haul
            "STNG":  0.080770,   # Scorpio Tankers — product tankers
            "INSW":  0.080770,   # International Seaways — mixed crude + product fleet

            # --- Container Shipping (7.8%) --- BaM-SPECIFIC
            # BaM closure forces Asia-Europe container traffic around Cape (+14 days),
            # sharply reducing effective vessel capacity and spiking freight rates globally.
            # GSL selected over CMRE: 3.3yr avg charter duration (vs CMRE 5.9yr) means
            # faster repricing into the rate spike. ZIM excluded: Israeli-flagged vessels
            # are the primary Houthi targets — the disruption trigger and ZIM downside
            # are the same event.
            "GSL":   0.078146,   # Global Ship Lease — 3.3yr charter avg; no Israeli exposure
        }

        # Verify weights sum to ~1.0 (QuantConnect tolerates small floating-point drift)
        total = sum(self.HOLDINGS.values())
        self.log(f"Total allocated weight: {total:.6f}")

        for ticker in self.HOLDINGS:
            self.add_equity(ticker, Resolution.DAILY)

    def on_data(self, data: Slice):
        if not self.portfolio.invested:
            for ticker, weight in self.HOLDINGS.items():
                self.set_holdings(ticker, weight)
