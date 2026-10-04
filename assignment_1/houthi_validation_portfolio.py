# region imports
from AlgorithmImports import *
# endregion

class HouthiValidationPortfolio(QCAlgorithm):
    """
    Historical Analogue Validation — 2023-2024 Houthi Red Sea Attacks

    This backtest applies the dual-strait portfolio weights to the period of the
    Houthi attacks on Red Sea shipping (Bab al-Mandeb disruption), which serve
    as the closest historical analogue to the BaM closure scenario the dual-strait
    portfolio is designed for.

    Timeline:
      Oct 1, 2023   — backtest start (pre-attack baseline)
      Nov 18, 2023  — Galaxy Leader seized; Houthi attacks begin escalating
      Dec 2023      — Maersk, Hapag-Lloyd, MSC reroute around Cape of Good Hope
      Jan–Jun 2024  — peak disruption; container freight rates spike globally
      Dec 31, 2024  — backtest end

    IMPORTANT CAVEAT — IN-SAMPLE:
      The dual-strait MC optimization ran on 2022-2024 data, so this backtest
      period overlaps with the training window. This is NOT an out-of-sample
      test. It is a mechanistic validation: we are checking that the thesis-
      selected stocks responded to a BaM-type disruption as the thesis predicted,
      not claiming forward-looking predictive validity.

    Key results (Python/yfinance validation):
      Portfolio during attack period (Nov 18 – Jul 31 2024): +26.9%
      SPY during same period:                                 +21.5%
      Top bucket — Container/GSL:                            +52.9%
      Tankers:                                               +29.1%
      Defense:                                               +29.1%

    Weights: same as dual_strait_portfolio.py (25% tanker cap, MC-optimized)
    """

    def initialize(self):
        self.set_start_date(2023, 10, 1)   # one month before first major attack
        self.set_end_date(2024, 12, 31)    # full disruption period + resolution tail
        self.set_cash(10_000_000)

        # Annotation markers for the equity curve
        self.GALAXY_LEADER = datetime(2023, 11, 18)   # first major seizure
        self.MAERSK_REROUTE = datetime(2023, 12, 15)  # major lines reroute

        # Identical weights to dual_strait_portfolio.py
        # Bucket totals: Aluminum 5.1% | LNG/Gas 29.3% | Fertilizer 5.4%
        #                Defense 28.1% | Tankers 24.2% | Container 7.8%
        self.HOLDINGS = {
            # --- Aluminum (5.1%) ---
            "AA":    0.025582,
            "CENX":  0.012791,
            "RIO":   0.012791,

            # --- LNG / Natural Gas (29.3%) ---
            "LNG":   0.073312,
            "EQT":   0.073312,
            "AR":    0.073312,
            "GLNG":  0.073312,

            # --- Fertilizer (5.4%) ---
            "CF":    0.018127,
            "MOS":   0.018127,
            "IPI":   0.018127,

            # --- Defense (28.1%) ---
            "LMT":   0.168451,
            "RTX":   0.084226,
            "NOC":   0.028075,

            # --- Tankers (24.2%) ---
            "FRO":   0.080770,
            "STNG":  0.080770,
            "INSW":  0.080770,

            # --- Container Shipping (7.8%) --- BaM-SPECIFIC
            "GSL":   0.078146,
        }

        for ticker in self.HOLDINGS:
            self.add_equity(ticker, Resolution.DAILY)

    def on_data(self, data: Slice):
        if not self.portfolio.invested:
            for ticker, weight in self.HOLDINGS.items():
                self.set_holdings(ticker, weight)
