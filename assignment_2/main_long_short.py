# region imports
from AlgorithmImports import *
from collections import deque
import numpy as np
# endregion

# LONG/SHORT version: the first backtest we ran (Run 1). Compare with main.py, the long-only version (Run 2).
# Bollinger Band + RSI extremes, filtered by whether the move into the signal was orderly.
#   calm move  -> fade the extreme (buy lower extreme, short upper extreme)
#   sharp move -> skip
# Parameters are fixed from the 2018-2023 research; do not tune them on this backtest.

TICKERS = ["LMT", "RTX", "FRO", "STNG", "INSW", "AA", "CENX", "CF", "MOS", "IPI", "GSL"]

BB_PERIOD, BB_K = 20, 2
RSI_PERIOD, RSI_LOW, RSI_HIGH = 14, 30, 70
VOL_WINDOW = 20          # daily-return std window, ending the day before the signal
PUSH_THRESHOLD = 2.0     # signal-direction 3-day move, in daily-vol units; below = calm
HOLD_DAYS = 20

ALLOW_SHORT = True       # shorts the calm upper extreme (this is what main.py turns off)
USE_SHARP_FOLLOW = False # no sharp-breakout long leg (main.py turns it on)

START, END = (2024, 1, 1), (2025, 12, 31)   # 2024-2025 has already been seen; see notes below

POSITION_PCT = 0.10      # fraction of equity per position
MAX_POSITIONS = 8


class BollingerRsiLongShort(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(100000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.symbols = []
        self.bbs, self.rsis, self.closes = {}, {}, {}
        for ticker in TICKERS:
            symbol = self.add_equity(ticker, Resolution.DAILY).symbol
            self.symbols.append(symbol)
            self.bbs[symbol] = self.bb(symbol, BB_PERIOD, BB_K, MovingAverageType.SIMPLE, Resolution.DAILY)
            self.rsis[symbol] = self.rsi(symbol, RSI_PERIOD, MovingAverageType.WILDERS, Resolution.DAILY)
            self.closes[symbol] = deque(maxlen=VOL_WINDOW + 5)

        self.hold = {}  # symbol -> {"days": int, "rule": str}
        self.first_close = {}
        self.set_warm_up(280, Resolution.DAILY)

    def on_data(self, data: Slice):
        for symbol in self.symbols:
            if not data.bars.contains_key(symbol):
                continue
            close = data.bars[symbol].close
            self.closes[symbol].append(close)
            if self.is_warming_up:
                continue
            self.first_close.setdefault(symbol, close)

            if symbol in self.hold:
                self.hold[symbol]["days"] += 1
                if self.hold[symbol]["days"] >= HOLD_DAYS:
                    info = self.hold[symbol]
                    pnl = self.portfolio[symbol].unrealized_profit_percent
                    self.debug(f"{self.time.date()} EXIT {symbol.value} {info['rule']} dir={info['dir']} pnl={pnl:.2%}")
                    self.liquidate(symbol)
                    del self.hold[symbol]
                continue

            bb, rsi = self.bbs[symbol], self.rsis[symbol]
            if not (bb.is_ready and rsi.is_ready) or len(self.hold) >= MAX_POSITIONS:
                continue

            lower_ext = close < bb.lower_band.current.value and rsi.current.value < RSI_LOW
            upper_ext = close > bb.upper_band.current.value and rsi.current.value > RSI_HIGH
            if not (lower_ext or upper_ext):
                continue

            side = 1 if lower_ext else -1
            push = self._push(symbol, side)
            if push is None:
                continue

            if push < PUSH_THRESHOLD:
                direction, rule = side, "calm_fade"
            elif USE_SHARP_FOLLOW and side == -1:
                direction, rule = 1, "sharp_follow"
            else:
                continue
            if direction == -1 and not ALLOW_SHORT:
                continue

            quantity = int(POSITION_PCT * self.portfolio.total_portfolio_value / close)
            if quantity <= 0:
                continue
            self.market_order(symbol, direction * quantity)
            self.hold[symbol] = {"days": 0, "rule": rule, "dir": direction}
            self.debug(f"{self.time.date()} {symbol.value} {rule} dir={direction} push={push:.2f}")

    def on_end_of_algorithm(self):
        rets = [self.closes[s][-1] / self.first_close[s] - 1 for s in self.symbols if s in self.first_close]
        if rets:
            self.debug(f"Equal-weight buy-and-hold of {len(rets)} names, price only (no dividends): {np.mean(rets):.2%}")

    def _push(self, symbol, side):
        """3-day move in the signal direction, in units of prior 20-day daily-return std."""
        closes = np.array(self.closes[symbol], dtype=float)
        if len(closes) < VOL_WINDOW + 2:
            return None
        returns = closes[1:] / closes[:-1] - 1
        vol = returns[-(VOL_WINDOW + 1):-1].std(ddof=1)
        if vol <= 0:
            return None
        ret3 = closes[-1] / closes[-4] - 1
        return -side * ret3 / (vol * np.sqrt(3))
