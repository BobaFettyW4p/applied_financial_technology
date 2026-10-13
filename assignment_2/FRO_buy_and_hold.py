from AlgorithmImports import *


class FROBuyAndHold(QCAlgorithm):
    """Benchmark for FRO_mean_reversion.py: same dates, cash and data settings, but buy once and hold."""

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(10_000_000)

        self.symbol = self.add_equity(
            "FRO",
            Resolution.DAILY,
            data_normalization_mode=DataNormalizationMode.ADJUSTED
        ).symbol

        self.bought = False
        self.first_close = None
        self.last_close = None

    def on_data(self, data):
        if not data.bars.contains_key(self.symbol):
            return

        close = data.bars[self.symbol].close
        self.last_close = close
        if self.first_close is None:
            self.first_close = close

        # Buy once with the whole account; the order fills at the next open.
        if not self.bought:
            self.set_holdings(self.symbol, 1.0)
            self.bought = True

    def on_end_of_algorithm(self):
        if self.first_close and self.last_close:
            self.debug(f"FRO price return over the run (first to last close): "
                       f"{self.last_close / self.first_close - 1:.2%}")
