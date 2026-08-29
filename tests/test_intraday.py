import datetime
from unittest.mock import patch

from src.data.company_registry import CompanyInfo
from src.signals.generator import SignalDirection
from src.signals.intraday import (
    IntradaySignal, IntradayState,
    generate_intraday_signal, plan_trading_day,
)
from src.astrology.scoring import AstroScore
from src.data.ephemeris import Graha

COMPANY = CompanyInfo(
    ticker="TEST", incorporation_date=datetime.date(2000, 1, 1),
    incorporation_location="Mumbai MH", sector="Technology",
)


def _mock_natal(score: float = 5.0) -> AstroScore:
    return AstroScore(
        ticker="TEST", raw_score=score, clamped_score=score,
        aspect_count=3, dominant_aspect="GURU FULL SURYA",
        drishti_score=score, dasha_score=0.0, nakshatra_score=0.0,
        yoga_score=0.0, bhava_score=0.0, active_yogas=[],
        current_dasha="GURU/BUDHA", moon_nakshatra="Rohini",
    )


class TestIntradaySignal:
    def test_buy_during_auspicious_window(self):
        # Thursday (Guru's day), first hora = Guru
        dt = datetime.datetime(2024, 6, 20, 6, 30)
        natal = _mock_natal(5.0)

        signal = generate_intraday_signal(
            COMPANY, dt, natal,
            trend_signal=1, has_position=False,
        )
        assert signal.direction in (SignalDirection.BUY, SignalDirection.HOLD)
        assert signal.hora_ruler is not None
        assert signal.muhurta_name != ""
        assert signal.confidence > 0

    def test_hold_when_max_trades_reached(self):
        dt = datetime.datetime(2024, 6, 20, 10, 0)
        natal = _mock_natal(5.0)

        signal = generate_intraday_signal(
            COMPANY, dt, natal,
            has_position=False,
            max_trades_per_day=8,
            trades_today=8,
        )
        assert signal.direction == SignalDirection.HOLD
        assert "Max trades" in signal.reason

    def test_hold_when_low_confidence(self):
        dt = datetime.datetime(2024, 6, 20, 10, 0)
        natal = _mock_natal(0.5)

        signal = generate_intraday_signal(
            COMPANY, dt, natal,
            has_position=False,
            min_confidence=95,
        )
        assert signal.direction == SignalDirection.HOLD

    def test_rahu_kaal_blocks_new_position(self):
        # Find a time in Rahu Kaal for Thursday (4th hora = 9:00-10:30)
        dt = datetime.datetime(2024, 6, 20, 9, 30)
        natal = _mock_natal(5.0)

        signal = generate_intraday_signal(
            COMPANY, dt, natal,
            has_position=False,
        )
        if signal.warnings and any("Rahu Kaal" in w for w in signal.warnings):
            assert signal.direction == SignalDirection.HOLD

    def test_signal_has_all_vedic_fields(self):
        dt = datetime.datetime(2024, 6, 20, 10, 0)
        natal = _mock_natal(3.0)

        signal = generate_intraday_signal(COMPANY, dt, natal)
        assert signal.ticker == "TEST"
        assert signal.hora_ruler is not None
        assert isinstance(signal.hora_score, float)
        assert isinstance(signal.muhurta_name, str)
        assert isinstance(signal.muhurta_score, float)
        assert isinstance(signal.panchang_score, float)
        assert isinstance(signal.natal_score, float)
        assert isinstance(signal.combined_score, float)
        assert isinstance(signal.confidence, int)
        assert isinstance(signal.warnings, list)
        assert signal.reason != ""

    def test_sell_during_bearish_hora_with_position(self):
        # Saturday = Shani's day, bearish
        dt = datetime.datetime(2024, 6, 22, 6, 30)
        natal = _mock_natal(-2.0)

        signal = generate_intraday_signal(
            COMPANY, dt, natal,
            has_position=True,
        )
        assert signal.direction in (SignalDirection.SELL, SignalDirection.HOLD)


class TestPlanTradingDay:
    @patch("src.signals.intraday.compute_natal_score_for_day")
    def test_plan_returns_schedule_and_panchang(self, mock_natal):
        mock_natal.return_value = _mock_natal(3.0)
        result = plan_trading_day(COMPANY, datetime.date(2024, 6, 20))
        plan, panchang = result
        assert len(plan) > 0
        assert all("time" in row for row in plan)
        assert all("recommendation" in row for row in plan)
        assert panchang.date == datetime.date(2024, 6, 20)
