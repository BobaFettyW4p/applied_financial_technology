# region imports
from AlgorithmImports import *
import pandas as pd
# endregion

# To run a sweep variant, edit ONLY this line (leave {} for the default run), e.g.
#   OVERRIDES = {}                                                    default: 2022-11-22 to latest, 2% band
#   OVERRIDES = {"slippage_bps": 10}                                  Q2
#   OVERRIDES = {"band": 0.01}                                        Q3
#   OVERRIDES = {"start_date": "2022-11-22", "end_date": "2024-06-30"}  Q4
#   OVERRIDES = {"start_date": "2024-07-01"}                          Q5
OVERRIDES = {}


class F4RegimeSpread(QCAlgorithm):
    """F4: AI-ecosystem regime book + memory-vs-hyperscaler spread (QuantConnect).

    Two equal sleeves (each 50% of capital), always in single stocks:
      F2  graded regime on the equal-weight basket of 18 names. Three binaries (prior-close style, computed 5 min before the close):
          basket above its 50d SMA, basket above its 100d SMA, share of names above their own 50d SMA > 50%.
          net exposure e = (count/3)*2 - 1  in {-1, -1/3, +1/3, +1}; every available name gets e/N of the sleeve (net long in uptrends,
          net SHORT in downtrends).
      N2  memory-vs-hyperscaler spread: long the equal-weight memory basket (MU WDC STX SNDK) and short the equal-weight hyperscaler basket
          (AMZN GOOGL MSFT META ORCL IBM) when the memory/hyperscaler ratio is above its 100d SMA, reverse below; exposure scaled by
          min(1, 15% / trailing-60d annualised spread vol); SPY overlay offsets the spread's 120d beta.
    Universe (18): MU WDC STX SNDK | NVDA AVGO AMD | AMZN GOOGL MSFT META ORCL IBM | DELL ANET VRT EQIX CEG. A name trades after 200 days of history.

    Research evidence (local pandas, 2 bps per leg; NOT yet confirmed on QuantConnect): 2021-26 Sharpe 0.98, 15.5% a year, max drawdown -17%,
    2022 -7.7%, 5 of 6 years positive. It FAILED the pre-declared rule (2022 had to be positive). Slower-regime sibling on 2011-20 (exploratory,
    one look): Sharpe 0.61 vs SPY 0.84, so the edge was not stable across eras. Universe was chosen with hindsight; ~75 trials behind it.
    Declared deviation from research: orders only when a position is off target by more than `band` of equity (default 2%) to cut churn. A QC run with a 1% band hit the 10,000-order cap in 2022; offline, 2% needs ~3,100 orders over 2022-11-22 to 2026-08 versus ~4,800 at 1%, with no meaningful change in results (Sharpe differences across bands are noise).

    Parameters (QuantConnect parameter panel): start_date ("2022-11-22", the ChatGPT launch), end_date, vol_target (0.15), band (0.02),
    entry_minutes_before_close (5), slippage_bps (0), regime_weight (0.5; spread sleeve = 1 - regime_weight).
    """

    # --- signal core (pure pandas; tested offline against the research code by f4_parity_check.py) ---
    MEM = ["MU", "WDC", "STX", "SNDK"]
    HYP = ["AMZN", "GOOGL", "MSFT", "META", "ORCL", "IBM"]
    OTHER = ["NVDA", "AVGO", "AMD", "DELL", "ANET", "VRT", "EQIX", "CEG"]

    @staticmethod
    def f4_targets(closes, regime_weight=0.5, vol_target=0.15):
        """closes: DataFrame of daily closes (>= ~400 rows, last row = today's price), columns = tickers incl. 'SPY'. Returns {ticker: weight}."""
        import numpy as np
        MEM, HYP = F4RegimeSpread.MEM, F4RegimeSpread.HYP
        UNI = MEM + F4RegimeSpread.OTHER[:3] + HYP + F4RegimeSpread.OTHER[3:]
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
        tgt = self.f4_targets(closes, self.regime_weight, self.vol_target)
        if not tgt:
            return
        total = self.portfolio.total_portfolio_value
        full = {t: tgt.get(t, 0.0) for t in self.symbols}
        if any(abs(self.portfolio[self.symbols[t]].holdings_value / total - w) > self.band for t, w in full.items()):
            self.set_holdings([PortfolioTarget(self.symbols[t], w) for t, w in full.items()])
