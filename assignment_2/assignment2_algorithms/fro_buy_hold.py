from AlgorithmImports import *

# Backtest period: 2024-01-01 through 2025-12-31
# Starting capital: $10,000,000

class FROBuyHold(QCAlgorithm):
    """Passive buy-and-hold FRO benchmark, adjusted-price equity data."""

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(10_000_000)
        self.fro_symbol = self.add_equity("FRO", Resolution.DAILY,
            data_normalization_mode=DataNormalizationMode.ADJUSTED).symbol
        self.purchased = False

    def on_data(self, data: Slice):
        if not self.purchased and data.bars.contains_key(self.fro_symbol):
            self.set_holdings(self.fro_symbol, 0.99)
            self.purchased = True
