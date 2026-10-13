from AlgorithmImports import *


class FROSymmetricMeanReversion(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(10_000_000)

        self.symbol = self.add_equity(
            "FRO",
            Resolution.DAILY,
            data_normalization_mode=DataNormalizationMode.ADJUSTED
        ).symbol

        self.bb = self.bb(
            self.symbol,
            20,
            2,
            MovingAverageType.SIMPLE,
            Resolution.DAILY
        )

        self.set_warm_up(30, Resolution.DAILY)

        # Position age, measured in daily bars
        self.days_held = 0

        # Track whether a signal condition was true
        # on the previous observation.
        self.was_below = False
        self.was_above = False

    def on_data(self, data):

        if self.is_warming_up or not self.bb.is_ready:
            return

        if not data.bars.contains_key(self.symbol):
            return

        price = data.bars[self.symbol].close

        lower = self.bb.lower_band.current.value
        middle = self.bb.middle_band.current.value
        upper = self.bb.upper_band.current.value

        below = price < lower
        above = price > upper

        # Detect the start of a new signal episode
        new_lower_signal = below and not self.was_below
        new_upper_signal = above and not self.was_above

        # Remember conditions for the next daily bar
        self.was_below = below
        self.was_above = above

        holdings = self.portfolio[self.symbol]
        quantity = holdings.quantity

        # LONG POSITION
        if quantity > 0:

            self.days_held += 1

            if price >= middle or self.days_held >= 10:
                self.liquidate(self.symbol)
                self.days_held = 0

        # SHORT POSITION
        elif quantity < 0:

            self.days_held += 1

            if price <= middle or self.days_held >= 10:
                self.liquidate(self.symbol)
                self.days_held = 0

        # NO POSITION
        else:

            if new_lower_signal:
                self.set_holdings(self.symbol, 1.0)
                self.days_held = 0

            elif new_upper_signal:
                self.set_holdings(self.symbol, -1.0)
                self.days_held = 0