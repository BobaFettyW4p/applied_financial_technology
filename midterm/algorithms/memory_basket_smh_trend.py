# region imports
from AlgorithmImports import *
# endregion

# SWEEP CONTROL: for each run, edit ONLY this line, then click Backtest. Examples (see QC_SWEEP_PLAN.md):
#   OVERRIDES = {}                                   shipped default (SPY fallback)
#   OVERRIDES = {"fallback": "CASH"}                 idle slots in cash instead of SPY
#   OVERRIDES = {"slippage_bps": 10}
#   OVERRIDES = {"start_year": 2016, "end_year": 2020}
#   OVERRIDES = {"trend_days": 150}   {"gate": "SMH"}   {"tickers": "WDC,STX"}
OVERRIDES = {}


class MemoryBasketSmhTrend(QCAlgorithm):
    """Memory-theme trend basket (MU, WDC, STX + memory-capex equipment LRCX, AMAT, KLAC) with a market fallback.

    The portfolio is six equal slots. A slot holds its stock only while the stock is above its own 100-day average;
    otherwise that slot holds SPY (fallback="SPY", shipped) or cash (fallback="CASH"). Decided shortly before each
    close and held through. An optional second gate (gate="SMH": semiconductor ETF above its 100-day average) exists
    but the QuantConnect sweep showed it adds nothing, so it is off by default.

    Research basis (local yfinance screen + QuantConnect sweep, 2011-2026): the trend rule cuts memory's ~68%
    buy-and-hold drawdown to ~42% at a Sharpe near buy-and-hold; filling idle slots with SPY instead of cash adds
    about 5 points a year of return at similar Sharpe (local test: discovery Sharpe 0.92 vs 0.88, hold-out 1.30 vs 1.28).
    Parameters: tickers, trend_days, gate, fallback, gross_exposure, entry_minutes_before_close, slippage_bps,
    start_year, end_year.
    """

    def _p(self, name, default):
        """Value from OVERRIDES if set, else from QuantConnect's Parameters panel, else the default."""
        return OVERRIDES.get(name, self.get_parameter(name, str(default)))

    def initialize(self):
        end_year = int(self._p("end_year", 2026))
        self.set_start_date(int(self._p("start_year", 2011)), 1, 3)
        self.set_end_date(end_year, 10 if end_year == 2026 else 12, 30)
        self.set_cash(1_000_000)
        self.set_benchmark("SPY")

        tickers = self._p("tickers", "MU,WDC,STX,LRCX,AMAT,KLAC").split(",")
        self.trend_days = int(self._p("trend_days", 100))
        self.use_gate = self._p("gate", "NONE")             # "NONE" (own trend only) or "SMH"
        self.fallback = self._p("fallback", "SPY")          # "SPY" (idle slots hold SPY) or "CASH"
        self.gross = float(self._p("gross_exposure", 1.0))
        self.entry_min = int(self._p("entry_minutes_before_close", 5))

        self.symbols = [self.add_equity(t, Resolution.MINUTE).symbol for t in tickers]
        self.gate_symbol = self.add_equity("SMH", Resolution.MINUTE).symbol
        self.spy = self.add_equity("SPY", Resolution.MINUTE).symbol
        slip = float(self._p("slippage_bps", 0)) / 1e4      # cost stress: extra one-way slippage
        if slip > 0:
            for s in self.symbols + [self.spy]:
                self.securities[s].set_slippage_model(ConstantSlippageModel(slip))
        self.set_warm_up(self.trend_days + 5, Resolution.DAILY)

        self.schedule.on(self.date_rules.every_day(self.spy),
                         self.time_rules.before_market_close(self.spy, self.entry_min), self.rebalance)

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
        gate_ok = True if self.use_gate == "NONE" else self._trend_up(self.gate_symbol)
        w = self.gross / len(self.symbols)                  # fixed slot per name
        targets = {s: 0.0 for s in self.symbols}
        spy_w = 0.0
        for s in self.symbols:
            if gate_ok and self.securities[s].price > 0 and self._trend_up(s):
                targets[s] = w
            elif self.fallback == "SPY":
                spy_w += w                                  # idle slot goes to SPY
        targets[self.spy] = spy_w

        total = self.portfolio.total_portfolio_value
        if any(abs(self.portfolio[s].holdings_value / total - t) > 0.02 for s, t in targets.items()):
            self.set_holdings([PortfolioTarget(s, t) for s, t in targets.items()])
