from AlgorithmImports import *

# Backtest period: 2024-01-01 through 2025-12-31
# Starting capital: $10,000,000

class TankersLongShort(QCAlgorithm):
    """Tanker Bollinger Band mean-reversion portfolio.

    Fresh lower breach -> +1/3 portfolio in that stock.
    Fresh upper breach -> -1/3 portfolio in that stock (all three eligible).
    Exit on middle band or after 10 daily bars. Cash when no position.
    """

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(10_000_000)
        self.tickers = ["FRO", "STNG", "INSW"]
        self.short_tickers = ["FRO", "STNG", "INSW"]
        self.weight = 1.0 / 3.0
        self.max_hold_days = 10
        self.symbols = {}
        self.bands = {}
        self.days_held = {}
        self.was_below = {}
        self.was_above = {}
        for ticker in self.tickers:
            symbol = self.add_equity(ticker, Resolution.DAILY,
                data_normalization_mode=DataNormalizationMode.ADJUSTED).symbol
            self.symbols[ticker] = symbol
            self.bands[symbol] = self.bb(symbol, 20, 2, MovingAverageType.SIMPLE, Resolution.DAILY)
            self.days_held[symbol] = 0
            self.was_below[symbol] = False
            self.was_above[symbol] = False
        self.set_warm_up(30, Resolution.DAILY)

    def on_data(self, data: Slice):
        for ticker, symbol in self.symbols.items():
            if not data.bars.contains_key(symbol):
                continue
            bb = self.bands[symbol]
            if not bb.is_ready:
                continue
            price = data.bars[symbol].close
            below = price < bb.lower_band.current.value
            above = price > bb.upper_band.current.value
            new_lower = below and not self.was_below[symbol]
            new_upper = above and not self.was_above[symbol]
            # Maintain crossing state during warm-up, too.
            self.was_below[symbol] = below
            self.was_above[symbol] = above
            if self.is_warming_up:
                continue
            quantity = self.portfolio[symbol].quantity
            if quantity > 0:
                self.days_held[symbol] += 1
                if price >= bb.middle_band.current.value or self.days_held[symbol] >= self.max_hold_days:
                    self.liquidate(symbol)
                    self.days_held[symbol] = 0
            elif quantity < 0:
                self.days_held[symbol] += 1
                if price <= bb.middle_band.current.value or self.days_held[symbol] >= self.max_hold_days:
                    self.liquidate(symbol)
                    self.days_held[symbol] = 0
            else:
                if new_lower:
                    self.set_holdings(symbol, self.weight)
                    self.days_held[symbol] = 0
                elif new_upper and ticker in self.short_tickers:
                    self.set_holdings(symbol, -self.weight)
                    self.days_held[symbol] = 0
