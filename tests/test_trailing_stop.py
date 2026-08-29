from decimal import Decimal

from src.trading.trailing_stop import TrailingStop


class TestTrailingStop:
    def test_create(self):
        ts = TrailingStop.create("AAPL", Decimal("150.00"), 0.07)
        assert ts.highest_price == Decimal("150.00")
        assert ts.stop_price == Decimal("150.00") * Decimal("0.93")

    def test_update_higher(self):
        ts = TrailingStop.create("AAPL", Decimal("150.00"), 0.07)
        ts2 = ts.update(Decimal("160.00"))
        assert ts2.highest_price == Decimal("160.00")
        assert ts2.stop_price > ts.stop_price

    def test_update_lower_no_change(self):
        ts = TrailingStop.create("AAPL", Decimal("150.00"), 0.07)
        ts2 = ts.update(Decimal("145.00"))
        assert ts2.highest_price == Decimal("150.00")
        assert ts2.stop_price == ts.stop_price

    def test_triggered(self):
        ts = TrailingStop.create("AAPL", Decimal("150.00"), 0.07)
        assert not ts.is_triggered(Decimal("145.00"))
        assert ts.is_triggered(Decimal("139.00"))

    def test_locked_gain(self):
        ts = TrailingStop.create("AAPL", Decimal("100.00"), 0.10)
        ts = ts.update(Decimal("130.00"))
        assert ts.locked_gain_pct > 0
        assert ts.current_gain_pct == 30.0
