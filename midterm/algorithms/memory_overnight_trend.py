# region imports
from AlgorithmImports import *
# endregion


class MemoryOvernightTrend(QCAlgorithm):
    """Memory-theme overnight strategy: own the stock only overnight (close -> next open), and only while
    its price is above its 100-day average. The rest of the time, hold cash.

    Research basis (local yfinance screen, discovery 2011-2020, hold-out 2021+):
      * Micron earns essentially all of its return overnight; the intraday leg was negative in discovery.
      * Gating the overnight leg by a 100-day trend roughly halves the drawdown.
    Parameters (set via QC parameters to run sensitivity): tickers, trend_days, entry_minutes_before_close.
    """

    def initialize(self):
        self.set_start_date(2011, 1, 3)
        self.set_end_date(2026, 10, 30)
        self.set_cash(1_000_000)
        self.set_benchmark("SPY")

        tickers = self.get_parameter("tickers", "MU").split(",")
        self.trend_days = int(self.get_parameter("trend_days", 100))
        self.entry_min = int(self.get_parameter("entry_minutes_before_close", 5))
        self.gross = float(self.get_parameter("gross_exposure", 1.0))

        self.symbols = [self.add_equity(t, Resolution.MINUTE).symbol for t in tickers]
        self.set_warm_up(self.trend_days + 5, Resolution.DAILY)

        anchor = self.symbols[0]
        # Entry shortly before the close; exit one minute after the open.
        self.schedule.on(self.date_rules.every_day(anchor),
                         self.time_rules.before_market_close(anchor, self.entry_min), self.enter)
        self.schedule.on(self.date_rules.every_day(anchor),
                         self.time_rules.after_market_open(anchor, 1), self.exit)

    def _trend_up(self, symbol) -> bool:
        """Price now vs. the mean of the prior (trend_days - 1) closes plus today's price: the 100-day SMA as it
        will print at today's close, using only information available before the closing auction."""
        hist = self.history(symbol, self.trend_days - 1, Resolution.DAILY)
        if hist.empty or len(hist) < self.trend_days - 1:
            return False
        price = self.securities[symbol].price
        sma = (hist["close"].sum() + price) / self.trend_days
        return price > sma

    def enter(self):
        if self.is_warming_up:
            return
        on = [s for s in self.symbols if self.securities[s].price > 0 and self._trend_up(s)]
        w = self.gross / len(self.symbols)          # idle names stay in cash; weights are fixed per name
        for s in self.symbols:
            self.set_holdings(s, w if s in on else 0)

    def exit(self):
        if self.is_warming_up:
            return
        self.liquidate()
