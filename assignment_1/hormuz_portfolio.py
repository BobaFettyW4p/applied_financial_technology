# region imports
from AlgorithmImports import *
# endregion

class HormuzDisruptionPortfolio(QCAlgorithm):
    """
    Strait of Hormuz Disruption — Second-Order Commodity Plays

    Fixed-allocation buy-and-hold strategy derived from a two-step process:
      1. Five thematic buckets with conviction-weighted internal allocations
      2. Monte Carlo optimization (10,000 Dirichlet draws) over bucket weights
         trained on 2022-2024 data, maximising Sharpe with asymmetric constraints
         (tankers capped at 20% as a tactical position sensitive to strait resolution)

    Backtest period: Jan 2025 – present (fully out-of-sample vs. optimization window)
    Strait declared closed: Feb 28, 2026
    """

    def initialize(self):
        self.set_start_date(2025, 1, 1)
        self.set_end_date(2026, 10, 1)
        self.set_cash(10_000_000)

        # Final per-stock weights:
        #   bucket_weight (from Monte Carlo) × within-bucket weight (conviction-set)
        # Bucket totals: Aluminum 12.6% | LNG/Gas 37.1% | Fertilizer 10.3% | Defense 21.1% | Tankers 18.9%
        self.HOLDINGS = {
            # --- Aluminum (12.6%) ---
            # Western producers benefit from UAE/Middle East supply disruption;
            # hydro-powered assets hedge the energy cost spike
            "AA":    0.063000,   # Alcoa — 50% of bucket; hydro smelters in Norway/Iceland
            "CENX":  0.031500,   # Century Aluminum — 25%; highest beta to Al price
            "RIO":   0.031500,   # Rio Tinto — 25%; NYSE-listed; major bauxite/alumina/Al producer with hydro smelters in Iceland + Quebec

            # --- LNG / Natural Gas (37.1%) ---
            # Qatar LNG routes entirely through Hormuz; US Gulf Coast terminals
            # become the only large-scale alternative source
            "LNG":   0.092750,   # Cheniere Energy — largest US LNG exporter
            "EQT":   0.092750,   # EQT Corp — largest US natural gas producer
            "AR":    0.092750,   # Antero Resources — high LNG export leverage
            "GLNG":  0.092750,   # Golar LNG — shipping + FLNG assets

            # --- Fertilizer (10.3%) ---
            # Two independent catalysts: Hormuz energy cascade (NG → ammonia cost spike)
            # + US-Canada trade friction benefiting US domestic potash producers
            "CF":    0.034333,   # CF Industries — largest US nitrogen producer
            "MOS":   0.034333,   # Mosaic — US potash + phosphate
            "IPI":   0.034333,   # Intrepid Potash — only major US domestic potash pure-play

            # --- Interceptor Restocking / Defense (21.1%) ---
            # NOT a bet on escalation — THAAD/PAC-3 stores depleted via Ukraine/Israel
            # transfers; restocking cycle is underway regardless of strait status
            "LMT":   0.126600,   # Lockheed Martin — 60%; THAAD + PAC-3 MSE (the consumable)
            "RTX":   0.063300,   # RTX Corp — 30%; SM-3, Patriot system
            "NOC":   0.021100,   # Northrop Grumman — 10%; IBCS battle network integration

            # --- Tankers (18.9%) ---
            # Tactical position: closure adds 7-10 days transit each way → rate spike.
            # Capped at 20% because this is the one bucket to exit on resolution.
            "FRO":   0.063000,   # Frontline — VLCC crude tankers
            "STNG":  0.063000,   # Scorpio Tankers — product tankers
            "INSW":  0.063000,   # International Seaways — mixed crude + product fleet
        }

        for ticker in self.HOLDINGS:
            self.add_equity(ticker, Resolution.DAILY)

    def on_data(self, data: Slice):
        if not self.portfolio.invested:
            for ticker, weight in self.HOLDINGS.items():
                self.set_holdings(ticker, weight)
