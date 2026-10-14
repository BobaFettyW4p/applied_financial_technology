from AlgorithmImports import *

# Backtest period: 2024-01-01 through 2025-12-31
# Starting capital: $10,000,000

class FROLongOnly(QCAlgorithm):
    """Original exploratory FRO long-only strategy.

    Entry: whenever flat and price closes below lower 20,2 BB.
    Exit: price >= middle BB or 10 daily data bars in position.
    NOTE: Unlike fro_long_short.py, this version does NOT require a fresh breach.
    """

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(10_000_000)
        self.fro_symbol = self.add_equity("FRO", Resolution.DAILY,
            data_normalization_mode=DataNormalizationMode.ADJUSTED).symbol
        self.bands = self.bb(self.fro_symbol, 20, 2, MovingAverageType.SIMPLE, Resolution.DAILY)
        self.set_warm_up(30, Resolution.DAILY)
        self.days_held = 0

    def on_data(self, data: Slice):
        if self.is_warming_up or not self.bands.is_ready or not data.bars.contains_key(self.fro_symbol):
            return
        price = data.bars[self.fro_symbol].close
        if self.portfolio[self.fro_symbol].quantity > 0:
            self.days_held += 1
            if price >= self.bands.middle_band.current.value or self.days_held >= 10:
                self.liquidate(self.fro_symbol)
                self.days_held = 0
        elif price < self.bands.lower_band.current.value:
            self.set_holdings(self.fro_symbol, 1.0)
            self.days_held = 0
