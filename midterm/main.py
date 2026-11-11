# region imports
from AlgorithmImports import *
import pandas as pd
# endregion

"""Situational Humility: a long/short strategy on the AI ecosystem (QuantConnect / LEAN).

Applied Financial Technology midterm.
Idea: AI spending moves through a supply chain (hyperscalers -> chips -> memory -> data
centers), and the stocks in that chain move together. "Awareness tells you what is
happening; humility sizes the bet." The strategy follows the chain's trend, bets on
memory against the cloud buyers, and is built to go net short when the trend breaks.
"""

# Optional overrides for test runs. Leave as {} for the default run. Examples:
#   OVERRIDES = {"slippage_bps": 10}                                    extra slippage
#   OVERRIDES = {"band": 0.01}                                          tighter rebalance band
#   OVERRIDES = {"start_date": "2022-11-22", "end_date": "2024-06-30"}  sub-window
# The same names can also be set in QuantConnect's Parameters panel.
OVERRIDES = {}


class SituationalHumility(QCAlgorithm):
    """Two equal sleeves (50% of capital each), always in single stocks, rebalanced daily
    5 minutes before the close.

    1. Regime sleeve. Equal-weight basket of the 18 names; three yes/no tests:
         - basket above its 50-day average
         - basket above its 100-day average
         - more than half of the names above their own 50-day average
       Net exposure e = (tests passed / 3) * 2 - 1, i.e. -1, -1/3, +1/3 or +1. Each name
       gets e / N of the sleeve: net long in uptrends, net SHORT in downtrends.

    2. Memory spread sleeve. Long memory (MU WDC STX SNDK) and short hyperscalers
       (AMZN GOOGL MSFT META ORCL IBM) when the memory/hyperscaler ratio is above its
       100-day average; the reverse below it. Scaled to a 15% volatility target
       (trailing 60 days); a SPY position cancels the spread's 120-day market beta.

    Universe (18): MU WDC STX SNDK | NVDA AVGO AMD | AMZN GOOGL MSFT META ORCL IBM |
    DELL ANET VRT EQIX CEG. A name trades once it has 200 days of history.
    Orders are sent only when some position is more than `band` (default 2%) of equity
    off target, to limit churn.

    QuantConnect backtest, 2022-11-22 (the week before ChatGPT launched) to 2026-08-07,
    default fees: 25.7% a year (SPY 21.5%), max drawdown 15.7%, beta 0.11, 2,635 orders.
    Known limitations (see the video): the 18 names were chosen with hindsight; about 80
    rule variations were tried; the 50/100-day windows were chosen after seeing 2022. In
    our offline stress tests the same rules lose money on random tech baskets (median
    Sharpe -0.39), and in 2016-2019 the strategy returned 5.1% a year against 14.7% for SPY.
    Its strength is protection: net short in sell-offs, at the cost of lagging rebounds.

    Parameters: start_date ("2022-11-22"), end_date (blank = latest data), vol_target
    (0.15), band (0.02), entry_minutes_before_close (5), slippage_bps (0), regime_weight
    (0.5; the spread sleeve gets 1 - regime_weight).
    """

    # --- signal core (pure pandas, so it can be tested offline) ---
    MEM = ["MU", "WDC", "STX", "SNDK"]
    HYP = ["AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM"]
    OTHER = ["NVDA", "AVGO", "AMD", "DELL", "ANET", "VRT", "EQIX", "CEG"]

    @staticmethod
    def compute_targets(closes, regime_weight=0.5, vol_target=0.15):
        """closes: DataFrame of daily closes (>= ~400 rows, last row = today's price), columns = tickers incl. 'SPY'. Returns {ticker: weight}."""
        import numpy as np
        MEM, HYP = SituationalHumility.MEM, SituationalHumility.HYP
        UNI = MEM + SituationalHumility.OTHER[:3] + HYP + SituationalHumility.OTHER[3:]
        px = closes.reindex(columns=UNI)
        spy = closes["SPY"]
        r = px.pct_change(); rs = spy.pct_change()
        have = px.notna().rolling(200).sum() >= 200
        avail_prev = have.shift(1).fillna(False).astype(bool)                      # weights known before each day's return
        avail_now = have.iloc[-1]                                                  # who can be held tomorrow
        if avail_now.sum() < 8:
            return {}
        w_prev = avail_prev.astype(float).div(avail_prev.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
        w_now = avail_now.astype(float) / avail_now.sum()
        gr = (w_prev * r.fillna(0)).sum(axis=1).where(avail_prev.sum(axis=1) >= 8, 0.0)
        g = (1 + gr).cumprod()
        b1 = g.iloc[-1] > g.rolling(50).mean().iloc[-1]
        b2 = g.iloc[-1] > g.rolling(100).mean().iloc[-1]
        above = (px > px.rolling(50).mean()).iloc[-1]
        b3 = above[avail_now].mean() > 0.5
        e = (int(b1) + int(b2) + int(b3)) / 3 * 2 - 1
        tgt = {t: regime_weight * e * w_now[t] for t in UNI if w_now[t] > 0}

        # spread sleeve
        def basket(names):
            a = avail_prev[names].astype(float); return a.div(a.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
        wm_p, wh_p = basket(MEM), basket(HYP)
        rm = (wm_p * r[MEM].fillna(0)).sum(axis=1); rh = (wh_p * r[HYP].fillna(0)).sum(axis=1)
        ratio = (1 + rm).cumprod() / (1 + rh).cumprod()
        sma = ratio.rolling(100).mean()
        if np.isnan(sma.iloc[-1]):
            return tgt
        sig = 1.0 if ratio.iloc[-1] > sma.iloc[-1] else -1.0
        vol = (rm - rh).rolling(60).std().iloc[-1] * np.sqrt(252)
        scale = min(1.0, vol_target / vol) if vol and vol > 0 else 0.0
        sw = {}
        am = avail_now[MEM]; ah = avail_now[HYP]
        for t in MEM:
            if am[t]: sw[t] = sig * scale / am.sum()
        for t in HYP:
            if ah[t]: sw[t] = sw.get(t, 0.0) - sig * scale / ah.sum()
        beta = r.rolling(120).cov(rs).div(rs.rolling(120).var(), axis=0).iloc[-1].fillna(1.0)
        hedge = -sum(sw[t] * beta[t] for t in sw)
        for t, v in sw.items():
            tgt[t] = tgt.get(t, 0.0) + (1 - regime_weight) * v
        tgt["SPY"] = (1 - regime_weight) * hedge
        return tgt
    # --- end signal core ---

    def _p(self, name, default):
        """OVERRIDES line first, then the QC Parameters panel, then the default."""
        if name in OVERRIDES:
            return str(OVERRIDES[name])
        return self.get_parameter(name, default)

    def initialize(self):
        y, m, d = [int(x) for x in self._p("start_date", "2022-11-22").split("-")]
        self.set_start_date(y, m, d)
        end = self._p("end_date", "")
        if end:
            y, m, d = [int(x) for x in end.split("-")]
            self.set_end_date(y, m, d)
        self.set_cash(1_000_000)
        self.set_benchmark("SPY")

        self.regime_weight = float(self._p("regime_weight", 0.5))
        self.vol_target = float(self._p("vol_target", 0.15))
        self.band = float(self._p("band", 0.02))
        entry_min = int(self._p("entry_minutes_before_close", 5))
        slip = float(self._p("slippage_bps", 0)) / 1e4

        self.tickers = self.MEM + self.OTHER + self.HYP
        self.symbols = {}
        for t in self.tickers + ["SPY"]:
            s = self.add_equity(t, Resolution.MINUTE, leverage=3).symbol
            self.symbols[t] = s
            if slip > 0:
                self.securities[s].set_slippage_model(ConstantSlippageModel(slip))
        self.spy = self.symbols["SPY"]
        self.set_warm_up(420, Resolution.DAILY)
        self.schedule.on(self.date_rules.every_day(self.spy),
                         self.time_rules.before_market_close(self.spy, entry_min), self.rebalance)

    def _closes(self):
        hist = self.history(list(self.symbols.values()), 420, Resolution.DAILY)
        if hist.empty:
            return None
        c = hist["close"].unstack(level=0)
        names = {s: t for t, s in self.symbols.items()}
        c.columns = [names.get(x, str(x).split(" ")[0]) for x in c.columns]
        c.index = c.index.normalize()
        today = pd.Timestamp(self.time.date())
        row = {t: self.securities[s].price for t, s in self.symbols.items() if self.securities[s].price > 0}
        if today in c.index:
            c = c.drop(index=today)                          # replace any partial/stale bar with the live price
        c.loc[today] = pd.Series(row)
        return c.sort_index()

    def rebalance(self):
        if self.is_warming_up:
            return
        closes = self._closes()
        if closes is None or "SPY" not in closes:
            return
        tgt = self.compute_targets(closes, self.regime_weight, self.vol_target)
        if not tgt:
            return
        total = self.portfolio.total_portfolio_value
        full = {t: tgt.get(t, 0.0) for t in self.symbols}
        if any(abs(self.portfolio[self.symbols[t]].holdings_value / total - w) > self.band for t, w in full.items()):
            self.set_holdings([PortfolioTarget(self.symbols[t], w) for t, w in full.items()])
