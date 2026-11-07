# region imports
from AlgorithmImports import *
import pandas as pd
# endregion

# To run a sweep variant, edit ONLY this line (leave {} for the default run), e.g.
#   OVERRIDES = {}                                                      default: 2022-11-22 to latest, 2% band
#   OVERRIDES = {"slippage_bps": 10}                                    R2
#   OVERRIDES = {"band": 0.01}                                          R3
#   OVERRIDES = {"start_date": "2022-11-22", "end_date": "2024-06-30"}  R4
#   OVERRIDES = {"start_date": "2024-07-01"}                            R5
OVERRIDES = {}


class P1RegimeBasket(QCAlgorithm):
    """P1: AI-ecosystem basket with a trend-regime gate, SPY as the fallback (QuantConnect). Long only, always fully invested.

    Rule, evaluated every day 5 minutes before the close (prior closes + live price):
      Basket G = equal-weight index of the 18 names that have >= 200 days of history.
      Three regime signals: G above its 50d SMA; G above its 100d SMA; more than half of the names above their own 50d SMA.
      If at least 2 of the 3 are true (regime up): hold the 18 names equal weight (1/N each).
      Otherwise (regime down): hold 100% SPY.
    Universe (18): MU WDC STX SNDK | NVDA AVGO AMD | AMZN GOOGL MSFT META ORCL IBM | DELL ANET VRT EQIX CEG.

    Research evidence (offline, 2 bps per leg, NOT yet confirmed on QuantConnect): AI-era 2022-11-22 to latest: Sharpe 1.86, CAGR 56%, max drawdown -26%, beta 1.36, vs
    equal-weight buy-and-hold 1.94 / 70% / -34%. Pre-AI sanity window 2011 to 2022-11-21: Sharpe 0.96, drawdown -36%, 2022 -23% (SPY -16%, buy-and-hold -32%).
    Honest limits: beta is about 1.4 (a smaller version of the AI trade, not a hedge); the universe was chosen with hindsight; the 50/100-day windows were tuned after
    seeing 2022; ~87 trials sit behind the idea; the pre-AI window was used several times; shorting variants did worse, which is why this version goes to SPY.
    Declared deviation from research: orders only when a position is off target by more than `band` of equity (default 2%).

    Parameters (via OVERRIDES): start_date ("2022-11-22", the ChatGPT launch), end_date, band (0.02), entry_minutes_before_close (5), slippage_bps (0).
    """

    # --- signal core (pure pandas; tested offline against the research code by p1_check.py) ---
    MEM = ["MU", "WDC", "STX", "SNDK"]
    CHIPS = ["NVDA", "AVGO", "AMD"]
    HYP = ["AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM"]
    INFRA = ["DELL", "ANET", "VRT", "EQIX", "CEG"]

    @staticmethod
    def p1_targets(closes):
        """closes: DataFrame of daily closes (>= ~420 rows, last row = today's live price), columns = tickers incl. 'SPY'. Returns ({ticker: weight}, regime_up)."""
        import numpy as np
        C = P1RegimeBasket
        UNI = C.MEM + C.CHIPS + C.HYP + C.INFRA
        px = closes.reindex(columns=UNI)
        r = px.pct_change()
        have = px.notna().rolling(200).sum() >= 200
        avail_prev = have.shift(1).fillna(False).astype(bool)
        avail_now = have.iloc[-1]
        if avail_now.sum() < 8:
            return {}, False
        w_prev = avail_prev.astype(float).div(avail_prev.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
        gr = (w_prev * r.fillna(0)).sum(axis=1).where(avail_prev.sum(axis=1) >= 8, 0.0)
        g = (1 + gr).cumprod()
        b1 = g.iloc[-1] > g.rolling(50).mean().iloc[-1]
        b2 = g.iloc[-1] > g.rolling(100).mean().iloc[-1]
        above = (px > px.rolling(50).mean()).iloc[-1]
        b3 = above[avail_now].mean() > 0.5
        up = (int(b1) + int(b2) + int(b3)) >= 2
        if up:
            n = int(avail_now.sum())
            return {t: 1.0 / n for t in UNI if avail_now[t]}, True
        return {"SPY": 1.0}, False
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

        self.band = float(self._p("band", 0.02))
        entry_min = int(self._p("entry_minutes_before_close", 5))
        slip = float(self._p("slippage_bps", 0)) / 1e4

        self.tickers = self.MEM + self.CHIPS + self.HYP + self.INFRA
        self.symbols = {}
        for t in self.tickers + ["SPY"]:
            s = self.add_equity(t, Resolution.MINUTE).symbol
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
        tgt, up = self.p1_targets(closes)
        if not tgt:
            return
        total = self.portfolio.total_portfolio_value
        full = {t: tgt.get(t, 0.0) for t in self.symbols}
        if any(abs(self.portfolio[self.symbols[t]].holdings_value / total - w) > self.band for t, w in full.items()):
            self.set_holdings([PortfolioTarget(self.symbols[t], w) for t, w in full.items()])
