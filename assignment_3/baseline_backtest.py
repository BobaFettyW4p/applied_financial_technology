from AlgorithmImports import *
from datetime import timedelta
import numpy as np


# Baseline-only run. Project scenario parameters are intentionally ignored.
MODE = "baseline"
START = (2025, 1, 1)
END = (2026, 7, 22)  # Match the completed export for every comparison run.
TILT = 0.50
MARGIN_PERCENTILE = 75
CASH_BUFFER = 0.01

GROUPS = {
    "Aluminum": ["AA", "CENX", "RIO"],
    "LNG / Natural Gas": ["LNG", "EQT", "AR", "GLNG"],
    "Fertilizer": ["CF", "MOS", "IPI"],
    "Defense": ["LMT", "RTX", "NOC"],
    "Tankers": ["FRO", "STNG", "INSW"],
    "Container Shipping": ["GSL"],
}

# Same per-stock allocations as the expanded Project 1 portfolio.
BASE_WEIGHTS = {'AA': 0.025582, 'CENX': 0.012791, 'RIO': 0.012791, 'LNG': 0.073312, 'EQT': 0.073312, 'AR': 0.073312, 'GLNG': 0.073312, 'CF': 0.018127, 'MOS': 0.018127, 'IPI': 0.018127, 'LMT': 0.168451, 'RTX': 0.084226, 'NOC': 0.028075, 'FRO': 0.08077, 'STNG': 0.08077, 'INSW': 0.08077, 'GSL': 0.078146}


def pb_weights(base, groups, pb, tilt):
    """Keep half of each original allocation; tilt the rest to cheapest P/B."""
    weights = dict(base)
    for tickers in groups.values():
        valid = [t for t in tickers if np.isfinite(pb.get(t, np.nan)) and pb[t] > 0]
        if len(valid) < 2:
            continue  # No comparative signal: retain the original allocation.
        lowest = min(pb[t] for t in valid)
        winners = [t for t in valid if np.isclose(pb[t], lowest)]
        bucket_total = sum(base[t] for t in tickers)
        for ticker in tickers:
            weights[ticker] = (1 - tilt) * base[ticker]
        for ticker in winners:
            weights[ticker] += tilt * bucket_total / len(winners)
    return weights


def funded_buys(desired, prices, settled_cash, reserve):
    """Scale buys together to fit settled cash, allowing for fees and slippage."""
    # 0.5% above the ask plus $0.01/share and $1/order is a conservative
    # sizing allowance; actual fees and 10-bps slippage still use LEAN's models.
    unit_cost = {t: prices[t] * 1.005 + 0.01 for t in desired}
    budget = max(0.0, settled_cash - reserve - len(desired))
    cost = sum(desired[t] * unit_cost[t] for t in desired)
    scale = min(1.0, budget / cost) if cost > 0 else 0.0
    return {t: int(np.floor(desired[t] * scale)) for t in desired}


class FundamentalPortfolioBacktest(QCAlgorithm):
    def initialize(self):
        # Fix the control strategy even if the project has an old scenario parameter.
        self.mode = "baseline"
        self.set_runtime_statistic("Strategy", self.mode)
        if self.mode not in {"original", "baseline", "pb", "combined"}:
            raise ValueError("Unknown MODE")
        if not 0 <= TILT <= 1 or not 0 < MARGIN_PERCENTILE < 100:
            raise ValueError("Check strategy parameters")
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(10_000_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE,
                                 AccountType.CASH)
        self.settings.free_portfolio_value_percentage = CASH_BUFFER
        self.symbols = {}
        for ticker in BASE_WEIGHTS:
            security = self.add_equity(ticker, Resolution.MINUTE)
            security.set_slippage_model(ConstantSlippageModel(0.001))  # 10 bps/order
            self.symbols[ticker] = security.symbol
        self.spy = self.add_equity("SPY", Resolution.MINUTE).symbol
        self.set_benchmark(self.spy)
        self.set_warm_up(5, Resolution.DAILY)
        total = sum(BASE_WEIGHTS.values())
        self.base = {t: w / total for t, w in BASE_WEIGHTS.items()}
        self.pending_targets = None
        self.rejected_orders = 0
        self.cash_limited_batches = 0
        self.started = False
        self.exposure_sum = 0.0
        self.exposure_days = 0
        self.blocked_decisions = 0
        self.checked_decisions = 0
        self.schedule.on(self.date_rules.month_start(self.spy),
                         self.time_rules.after_market_open(self.spy, 31),
                         self.rebalance)
        # Retry pending purchases after sales settle, including holiday/weekend gaps.
        self.schedule.on(self.date_rules.every_day(self.spy),
                         self.time_rules.after_market_open(self.spy, 36),
                         self.execute_pending)
        self.schedule.on(self.date_rules.every_day(self.spy),
                         self.time_rules.before_market_close(self.spy, 1),
                         self.record_exposure)

    def margin_is_high(self, ticker):
        symbol = self.symbols[ticker]
        f = self.securities[symbol].fundamentals
        if not f.has_fundamental_data:
            self.debug(f"{ticker}: no fundamentals; margin filter skipped")
            return False
        current = f.operation_ratios.operation_margin.get_period_values()
        value = float(current["1Y"]) if "1Y" in current else np.nan
        if not np.isfinite(value):
            self.debug(f"{ticker}: no current annual margin; filter skipped")
            return False

        # One past observation per completed month, from the preceding five years.
        # The current month never enters its own comparison threshold.
        monthly = {}
        history = self.history[Fundamental](
            symbol, self.time - timedelta(days=5 * 366), self.time)
        current_month = (self.time.year, self.time.month)
        for past in history:
            month = (past.end_time.year, past.end_time.month)
            if month >= current_month or not past.has_fundamental_data:
                continue
            periods = past.operation_ratios.operation_margin.get_period_values()
            margin = float(periods["1Y"]) if "1Y" in periods else np.nan
            monthly[month] = (past.end_time, margin) if month not in monthly or past.end_time > monthly[month][0] else monthly[month]
        values = [v for _, v in monthly.values() if np.isfinite(v)]
        if len(values) < 36:
            self.debug(f"{ticker}: only {len(values)} monthly margins; filter skipped")
            return False
        cutoff = float(np.percentile(values, MARGIN_PERCENTILE))
        blocked = value > cutoff
        self.checked_decisions += 1
        self.blocked_decisions += int(blocked)
        self.debug(f"{self.time.date()} {ticker}: margin={value:.3f}, "
                   f"past {MARGIN_PERCENTILE}th percentile={cutoff:.3f}, skip={blocked}")
        return blocked

    def rebalance(self):
        if self.is_warming_up:
            return
        if self.started and (self.mode == "original" or self.time.month not in (1, 7)):
            return
        weights = dict(self.base)
        if self.mode in ("pb", "combined"):
            pb = {}
            for ticker, symbol in self.symbols.items():
                f = self.securities[symbol].fundamentals
                pb[ticker] = float(f.valuation_ratios.pb_ratio) if f.has_fundamental_data else np.nan
            weights = pb_weights(self.base, GROUPS, pb, TILT)
        if self.mode == "combined":
            for ticker in GROUPS["Fertilizer"]:
                if self.margin_is_high(ticker):
                    weights[ticker] = 0.0  # Leave this allocation in cash.
        if self.pending_targets is not None:
            raise RuntimeError("Previous rebalance has not completed; check pending orders")
        self.pending_targets = {}
        for ticker, weight in weights.items():
            symbol = self.symbols[ticker]
            security = self.securities[symbol]
            if not security.is_tradable or not security.has_data or security.price <= 0:
                self.debug(f"{ticker}: unavailable; no order submitted")
                continue
            # CalculateOrderQuantity applies the 1% portfolio buffer once.
            # Freeze share targets at the signal time while waiting for settlement.
            delta = self.calculate_order_quantity(symbol, weight)
            target = max(0, int(self.portfolio[symbol].quantity + delta))
            self.pending_targets[ticker] = target
        self.started = True
        self.debug(f"{self.time.date()} {self.mode}: preparing rebalance")
        self.execute_pending()

    def execute_pending(self):
        if self.is_warming_up or self.pending_targets is None:
            return
        if self.transactions.get_open_orders():
            return  # Do not duplicate orders that are still waiting for fills.

        sells = []
        buys = {}
        prices = {}
        for ticker, target in self.pending_targets.items():
            symbol = self.symbols[ticker]
            security = self.securities[symbol]
            if not security.is_tradable or not security.has_data or security.price <= 0:
                continue
            delta = target - int(self.portfolio[symbol].quantity)
            if delta < 0:
                sells.append((symbol, delta))
            elif delta > 0:
                buys[ticker] = delta
                prices[ticker] = max(float(security.price), float(security.ask_price))

        if sells:
            for symbol, quantity in sells:
                self.market_order(symbol, quantity, tag="Rebalance: sell first")
            return  # Cash-account sale proceeds cannot fund same-day purchases.

        unsettled = float(self.portfolio.unsettled_cash_book["USD"].amount)
        if unsettled > 0.01:
            self.debug(f"{self.time.date()}: waiting for ${unsettled:,.0f} to settle")
            return
        if not buys:
            self.pending_targets = None
            return

        settled = float(self.portfolio.cash_book["USD"].amount)
        # Keep half of the original buffer available after overnight price changes.
        reserve = max(1000.0, CASH_BUFFER * float(self.portfolio.total_portfolio_value) / 2)
        quantities = funded_buys(buys, prices, settled, reserve)
        if any(quantities[t] < buys[t] for t in buys):
            self.cash_limited_batches += 1
            self.debug("Purchase sizes reduced to fit settled cash and execution cushion")
        before = self.rejected_orders
        for ticker, quantity in quantities.items():
            if quantity > 0:
                self.market_order(self.symbols[ticker], quantity,
                                  tag="Rebalance: buy with settled cash")
        # Market orders are synchronous in these minute-data backtests.
        # Keep rejected targets pending so the next scheduled attempt can retry.
        if self.rejected_orders == before and not self.transactions.get_open_orders():
            self.pending_targets = None

    def record_exposure(self):
        if self.is_warming_up:
            return
        exposure = self.portfolio.total_holdings_value / self.portfolio.total_portfolio_value
        self.exposure_sum += exposure
        self.exposure_days += 1
        self.plot("Investment", "Invested (%)", 100 * exposure)

    def on_order_event(self, event):
        if event.status == OrderStatus.INVALID:
            self.rejected_orders += 1
            self.error(f"Order rejected: {event}")

    def on_end_of_algorithm(self):
        self.set_runtime_statistic("Rejected orders", str(self.rejected_orders))
        self.set_runtime_statistic("Cash-limited batches", str(self.cash_limited_batches))
        self.set_runtime_statistic("Pending rebalance", str(self.pending_targets is not None))
        self.set_runtime_statistic("Last trading date", str(self.time.date()))
        if self.exposure_days:
            self.set_runtime_statistic("Average invested",
                f"{self.exposure_sum / self.exposure_days:.1%}")
        self.set_runtime_statistic("Margin exclusions",
            f"{self.blocked_decisions}/{self.checked_decisions}")
