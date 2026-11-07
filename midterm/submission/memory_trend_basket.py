# region imports
from AlgorithmImports import *
# endregion


class MemoryTrendBasket(QCAlgorithm):
    """Memory-stock trend basket with a market fallback (QuantConnect).

    Portfolio: six equal slots, one each for Micron (MU), Western Digital (WDC) and Seagate (STX), the US-listed memory and
    storage names behind the Roundhill Memory ETF (DRAM), plus the memory-capex equipment makers Lam Research (LRCX),
    Applied Materials (AMAT) and KLA (KLAC) to cut single-stock concentration. Shortly before each close a slot is set as follows:
        stock above its own 100-day average  ->  the slot holds the stock
        stock below its own 100-day average  ->  the slot holds SPY
    So the portfolio is always fully invested; when the memory names are in a downtrend it sits in the market, and each slot
    returns to its stock when that stock's trend recovers. Positions are held through the next session (no intraday trading).

    Evidence (QuantConnect, 2011-01 to 2026-08, default settings, six stocks): 30.1% annual return, Sharpe 0.89, max drawdown
    44.3%, beta to SPY ~1.25, ~2,900 orders. With 10 bps extra slippage: 27.5%, Sharpe 0.82. By era: 2011-15 Sharpe 0.74
    (drawdown 30%), 2016-20 0.84 (38%), 2021-26 1.09 (45%). The three-stock version (MU, WDC, STX) earned more (35.7%, Sharpe
    0.97, drawdown 46.9%) but leaned on MU for ~70% of stock-specific profit in discovery versus ~42% for the six. SPY returned
    ~14% a year with a ~34% drawdown over the same period. Honest limits: the stocks were chosen with hindsight (DRAM's
    holdings today; the equipment names are a diversifier from a pre-declared list); the 100-day rule cut drawdowns on most
    AI-chain names but raised Sharpe mainly on memory itself; probabilistic Sharpe is only ~16%; beta is above 1; SPY is an
    ETF and needs instructor sign-off.

    Optional parameters (QuantConnect parameter panel): tickers (default "MU,WDC,STX"), trend_days (100),
    fallback ("SPY" or "CASH"), gross_exposure (1.0), entry_minutes_before_close (5), slippage_bps (0),
    start_date ("2011-01-03"), end_date (empty = run to the latest data).
    """

    def initialize(self):
        y, m, d = [int(x) for x in self.get_parameter("start_date", "2011-01-03").split("-")]
        self.set_start_date(y, m, d)
        end = self.get_parameter("end_date", "")
        if end:
            y, m, d = [int(x) for x in end.split("-")]
            self.set_end_date(y, m, d)
        self.set_cash(1_000_000)
        self.set_benchmark("SPY")

        tickers = self.get_parameter("tickers", "MU,WDC,STX,LRCX,AMAT,KLAC").split(",")
        self.trend_days = int(self.get_parameter("trend_days", 100))
        self.fallback = self.get_parameter("fallback", "SPY")
        self.gross = float(self.get_parameter("gross_exposure", 1.0))
        entry_min = int(self.get_parameter("entry_minutes_before_close", 5))

        self.symbols = [self.add_equity(t, Resolution.MINUTE).symbol for t in tickers]
        self.spy = self.add_equity("SPY", Resolution.MINUTE).symbol
        slip = float(self.get_parameter("slippage_bps", 0)) / 1e4
        if slip > 0:
            for s in self.symbols + [self.spy]:
                self.securities[s].set_slippage_model(ConstantSlippageModel(slip))
        self.set_warm_up(self.trend_days + 5, Resolution.DAILY)

        self.schedule.on(self.date_rules.every_day(self.spy),
                         self.time_rules.before_market_close(self.spy, entry_min), self.rebalance)

    def _trend_up(self, symbol) -> bool:
        """Price now vs the 100-day SMA as it will print at today's close (prior 99 closes + current price)."""
        hist = self.history(symbol, self.trend_days - 1, Resolution.DAILY)
        if hist.empty or len(hist) < self.trend_days - 1:
            return False
        price = self.securities[symbol].price
        return price > (hist["close"].sum() + price) / self.trend_days

    def rebalance(self):
        if self.is_warming_up:
            return
        w = self.gross / len(self.symbols)                  # fixed slot per name
        targets = {s: 0.0 for s in self.symbols}
        spy_w = 0.0
        for s in self.symbols:
            if self.securities[s].price > 0 and self._trend_up(s):
                targets[s] = w
            elif self.fallback == "SPY":
                spy_w += w                                  # idle slot goes to SPY
        targets[self.spy] = spy_w

        total = self.portfolio.total_portfolio_value
        if any(abs(self.portfolio[s].holdings_value / total - t) > 0.02 for s, t in targets.items()):
            self.set_holdings([PortfolioTarget(s, t) for s, t in targets.items()])
