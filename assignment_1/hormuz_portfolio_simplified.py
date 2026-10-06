# region imports
from AlgorithmImports import *
# endregion

class HormuzDisruptionPortfolio(QCAlgorithm):
    """
    Strait of Hormuz Disruption — Second-Order Commodity Plays

    Simplified 10-stock, conviction-weighted portfolio focused purely on second-order
    effects of a Hormuz closure. LNG removed: a direct gas price play is a first-order
    effect, not a second-order supply chain disruption.

    Four thematic buckets, conviction-weighted:
      Defense    35% — structurally insulated; multi-year procurement independent of strait status
      Tankers    25% — second-order ton-mile spike; capped as most resolution-sensitive position
      Aluminum   25% — second-order Western supply gap; hydro smelters hedge energy cost spike
      Fertilizer 15% — second-order NG cascade + US-Canada trade friction (independent catalyst)

    Backtest period: Jan 2025 – present (fully out-of-sample vs. 2022-2024 optimization window)
    Strait declared closed: Feb 28, 2026
    """

    def initialize(self):
        self.set_start_date(2025, 1, 1)
        self.set_end_date(2026, 10, 1)
        self.set_cash(10_000_000)

        # Bucket totals: Defense 35% | Tankers 25% | Aluminum 25% | Fertilizer 15%
        self.HOLDINGS = {
            # --- Defense (35%) ---
            # NOT a bet on escalation — THAAD/PAC-3 stores depleted via Ukraine/Israel
            # transfers; restocking cycle is underway regardless of strait status.
            # Most structurally insulated bucket: performs whether strait opens or closes.
            "LMT":   0.210,   # Lockheed Martin — 60%; makes the interceptor consumable itself
            "RTX":   0.140,   # RTX Corp — 40%; SM-3, Patriot system; naval angle in Gulf

            # --- Tankers (25%) ---
            # Closure adds 7-10 days transit each way → ton-mile spike → freight rate spike.
            # Equal-weighted across fleet types for diversification within the bucket.
            "FRO":   0.0833,  # Frontline — VLCC crude tankers; most benefit from long haul
            "STNG":  0.0833,  # Scorpio Tankers — product tankers; different cargo type
            "INSW":  0.0833,  # International Seaways — mixed crude + product fleet

            # --- Aluminum (25%) ---
            # UAE/Middle East smelters shut down; Chinese aluminum politically unavailable
            # (Section 232 tariffs + weaponization risk); Western producers capture the spread.
            # AA overweighted: hydro smelters in Norway/Iceland hedge the energy cost spike
            # that would erode margins at grid-dependent peers like CENX.
            "AA":    0.150,   # Alcoa — 60%; hydro-powered; full revenue upside, partial cost hedge
            "CENX":  0.100,   # Century Aluminum — 40%; highest beta to Al price

            # --- Fertilizer (15%) ---
            # Catalyst 1: Hormuz → global NG spike → ammonia/urea cost spike → domestic
            #   US producers (on domestic gas pricing) outcompete Middle East and European peers
            # Catalyst 2: US-Canada trade friction → domestic potash premium (strait-independent)
            "CF":    0.050,   # CF Industries — largest US nitrogen producer
            "MOS":   0.050,   # Mosaic — US potash + phosphate
            "IPI":   0.050,   # Intrepid Potash — only US domestic potash pure-play; both catalysts
        }

        for ticker in self.HOLDINGS:
            self.add_equity(ticker, Resolution.DAILY)

    def on_data(self, data: Slice):
        if not self.portfolio.invested:
            for ticker, weight in self.HOLDINGS.items():
                self.set_holdings(ticker, weight)

        for ticker in self.HOLDINGS:
            self.add_equity(ticker, Resolution.DAILY)

    def on_data(self, data: Slice):
        if not self.portfolio.invested:
            for ticker, weight in self.HOLDINGS.items():
                self.set_holdings(ticker, weight)
