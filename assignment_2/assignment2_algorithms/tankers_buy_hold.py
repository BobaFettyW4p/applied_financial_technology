from AlgorithmImports import *

# Backtest period: 2024-01-01 through 2025-12-31
# Starting capital: $10,000,000

class TankersBuyHold(QCAlgorithm):
    """Passive equal-weight buy-and-hold FRO, STNG, INSW benchmark.

    Buy each stock at roughly one-third of initial capital when first tradable.
    Do not rebalance afterward; allow weights to drift.
    """

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(10_000_000)
        self.symbols = {}
        self.purchased = {}
        for ticker in ["FRO", "STNG", "INSW"]:
            symbol = self.add_equity(ticker, Resolution.DAILY,
                data_normalization_mode=DataNormalizationMode.ADJUSTED).symbol
            self.symbols[ticker] = symbol
            self.purchased[symbol] = False

    def on_data(self, data: Slice):
        for symbol in self.symbols.values():
            if not self.purchased[symbol] and data.bars.contains_key(symbol):
                # Leave a small cash buffer for order fees / price movement.
                self.set_holdings(symbol, 0.33)
                self.purchased[symbol] = True
