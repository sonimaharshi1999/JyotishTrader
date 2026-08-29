from decimal import Decimal

from src.trading.kelly import compute_kelly, compute_kelly_from_trades, kelly_position_size
from src.trading.portfolio import Portfolio


class TestKelly:
    def test_positive_edge(self):
        result = compute_kelly(win_rate=0.6, avg_win_pct=10.0, avg_loss_pct=-5.0)
        assert result.kelly_fraction > 0
        assert result.half_kelly > 0
        assert result.half_kelly == result.kelly_fraction / 2

    def test_no_edge(self):
        result = compute_kelly(win_rate=0.5, avg_win_pct=5.0, avg_loss_pct=-5.0)
        assert result.kelly_fraction == 0.0

    def test_negative_edge(self):
        result = compute_kelly(win_rate=0.3, avg_win_pct=5.0, avg_loss_pct=-5.0)
        assert result.kelly_fraction == 0.0

    def test_from_trades(self):
        trades = [10.0, -5.0, 8.0, -3.0, 12.0, -4.0, 7.0, -6.0]
        result = compute_kelly_from_trades(trades)
        assert result.win_rate == 0.5
        assert result.avg_win > 0
        assert result.avg_loss < 0

    def test_position_size(self):
        result = compute_kelly(win_rate=0.6, avg_win_pct=10.0, avg_loss_pct=-5.0)
        portfolio = Portfolio(cash=Decimal("100000"))
        shares = kelly_position_size(portfolio, Decimal("150.00"), result)
        assert shares >= 0

    def test_empty_trades(self):
        result = compute_kelly_from_trades([])
        assert result.kelly_fraction == 0.0
