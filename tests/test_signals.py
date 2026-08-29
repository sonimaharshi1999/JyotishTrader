import datetime
from unittest.mock import patch, MagicMock

from src.data.company_registry import CompanyInfo
from src.signals.generator import SignalDirection, generate_signal
from src.signals.filters import apply_filters, _force_hold
from src.astrology.scoring import AstroScore
from src.astrology.transits import TransitReport
from src.data.ephemeris import Planet, GrahaPosition


COMPANY = CompanyInfo(
    ticker="TEST",
    incorporation_date=datetime.date(2000, 1, 1),
    incorporation_location="New York NY",
    sector="Technology",
)


def _mock_natal(ticker, date):
    from src.astrology.natal_chart import NatalChart
    positions = {
        p: GrahaPosition(
            graha=p, longitude=float(i * 30), latitude=0.0, speed=1.0,
            rashi_index=int(float(i * 30) // 30), rashi="Test", rashi_en="Test",
            degree_in_rashi=float(i * 30) % 30,
        )
        for i, p in enumerate(Planet)
    }
    return NatalChart(ticker=ticker, birth_date=date, positions=positions)


def _mock_transit(natal, date, orbs=None, weights=None):
    return TransitReport(date=date, ticker=natal.ticker, transit_positions={}, aspects=[])


class TestGenerateSignal:
    @patch("src.signals.generator.fetch_history")
    @patch("src.signals.generator.compute_transits", side_effect=_mock_transit)
    @patch("src.signals.generator.build_natal_chart", side_effect=_mock_natal)
    def test_hold_on_neutral(self, mock_natal, mock_transit, mock_history):
        import pandas as pd
        mock_history.return_value = pd.DataFrame()

        signal = generate_signal(COMPANY, datetime.date(2024, 6, 15))
        assert signal.direction == SignalDirection.HOLD
        assert signal.ticker == "TEST"


class TestFilters:
    def test_force_hold(self):
        from src.signals.generator import TradingSignal
        signal = TradingSignal(
            ticker="TEST",
            date=datetime.date(2024, 6, 15),
            direction=SignalDirection.BUY,
            astro_score=5.0,
            trend_signal=1,
            composite_score=6.5,
            dominant_aspect="GURU TRINE SURYA",
        )
        held = _force_hold(signal)
        assert held.direction == SignalDirection.HOLD
        assert held.astro_score == 5.0

    def test_hold_passes_through(self):
        from src.signals.generator import TradingSignal
        signal = TradingSignal(
            ticker="TEST",
            date=datetime.date(2024, 6, 17),  # Monday
            direction=SignalDirection.HOLD,
            astro_score=0.0,
            trend_signal=0,
            composite_score=0.0,
            dominant_aspect=None,
        )
        result = apply_filters(signal)
        assert result.direction == SignalDirection.HOLD
