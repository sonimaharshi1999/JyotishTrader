import datetime
from decimal import Decimal

from src.trading.portfolio import (
    Portfolio,
    Position,
    calculate_position_size,
    open_position,
    close_position,
)
from src.trading.risk import check_max_exposure, check_stop_loss, check_position_size_limit


class TestPortfolio:
    def test_initial_state(self):
        p = Portfolio(cash=Decimal("100000"))
        assert p.total_value == Decimal("100000")
        assert p.exposure_pct == 0.0
        assert not p.has_position("AAPL")

    def test_open_position(self):
        p = Portfolio(cash=Decimal("100000"))
        p2 = open_position(p, "AAPL", 10, Decimal("150.00"), datetime.date(2024, 1, 1))
        assert p2.has_position("AAPL")
        assert p2.cash == Decimal("98500.00")
        pos = p2.get_position("AAPL")
        assert pos.shares == 10

    def test_close_position(self):
        p = Portfolio(cash=Decimal("98500"))
        p.positions["AAPL"] = Position(
            ticker="AAPL", shares=10,
            entry_price=Decimal("150.00"),
            entry_date=datetime.date(2024, 1, 1),
        )
        p2 = close_position(p, "AAPL", Decimal("160.00"))
        assert not p2.has_position("AAPL")
        assert p2.cash == Decimal("100100.00")

    def test_position_size(self):
        p = Portfolio(cash=Decimal("100000"))
        shares = calculate_position_size(p, Decimal("150.00"), max_position_pct=0.05)
        assert shares == 33  # 5000 / 150 = 33

    def test_cant_afford(self):
        p = Portfolio(cash=Decimal("100"))
        p2 = open_position(p, "AAPL", 10, Decimal("150.00"), datetime.date(2024, 1, 1))
        assert not p2.has_position("AAPL")


class TestRisk:
    def test_exposure_under_limit(self):
        p = Portfolio(cash=Decimal("100000"))
        assert check_max_exposure(p, 0.30) is True

    def test_exposure_over_limit(self):
        p = Portfolio(cash=Decimal("10000"))
        p.positions["AAPL"] = Position(
            ticker="AAPL", shares=100,
            entry_price=Decimal("500.00"),
            entry_date=datetime.date(2024, 1, 1),
        )
        assert check_max_exposure(p, 0.30) is False

    def test_stop_loss_triggered(self):
        assert check_stop_loss(Decimal("100"), Decimal("92"), 0.07) is True

    def test_stop_loss_not_triggered(self):
        assert check_stop_loss(Decimal("100"), Decimal("95"), 0.07) is False

    def test_position_size_limit(self):
        p = Portfolio(cash=Decimal("100000"))
        assert check_position_size_limit(p, Decimal("5000"), 0.05) is True
        assert check_position_size_limit(p, Decimal("6000"), 0.05) is False
