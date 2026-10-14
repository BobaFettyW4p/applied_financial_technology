from AlgorithmImports import *

# Backtest period: 2024-01-01 through 2025-12-31
# Starting capital: $10,000,000

class FROLongShort(QCAlgorithm):
    """Original exploratory FRO symmetric mean-reversion strategy.

    Fresh lower BB breach -> 100% long; fresh upper BB breach -> 100% short.
    Exit at middle BB or after 10 daily bars in position.
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
        self.was_below = False
        self.was_above = False

    def on_data(self, data: Slice):
        if self.is_warming_up or not self.bands.is_ready or not data.bars.contains_key(self.fro_symbol):
            return
        price = data.bars[self.fro_symbol].close
        below = price < self.bands.lower_band.current.value
        above = price > self.bands.upper_band.current.value
        new_lower = below and not self.was_below
        new_upper = above and not self.was_above
        self.was_below = below
        self.was_above = above
        quantity = self.portfolio[self.fro_symbol].quantity
        if quantity > 0:
            self.days_held += 1
            if price >= self.bands.middle_band.current.value or self.days_held >= 10:
                self.liquidate(self.fro_symbol)
                self.days_held = 0
        elif quantity < 0:
            self.days_held += 1
            if price <= self.bands.middle_band.current.value or self.days_held >= 10:
                self.liquidate(self.fro_symbol)
                self.days_held = 0
        else:
            if new_lower:
                self.set_holdings(self.fro_symbol, 1.0)
                self.days_held = 0
            elif new_upper:
                self.set_holdings(self.fro_symbol, -1.0)
                self.days_held = 0
