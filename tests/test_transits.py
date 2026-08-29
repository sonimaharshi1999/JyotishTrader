import datetime
from unittest.mock import patch

from src.astrology.natal_chart import NatalChart
from src.astrology.transits import compute_transits
from src.data.ephemeris import Planet, GrahaPosition


def _mock_positions():
    return {
        p: GrahaPosition(
            graha=p, longitude=float(i * 36), latitude=0.0, speed=1.0,
            rashi_index=int(float(i * 36) // 30), rashi="Test", rashi_en="Test",
            degree_in_rashi=float(i * 36) % 30,
        )
        for i, p in enumerate(Planet)
    }


NATAL = NatalChart(
    ticker="TEST",
    birth_date=datetime.date(2000, 1, 1),
    positions={
        p: GrahaPosition(
            graha=p, longitude=float(i * 30), latitude=0.0, speed=1.0,
            rashi_index=int(float(i * 30) // 30), rashi="Test", rashi_en="Test",
            degree_in_rashi=float(i * 30) % 30,
        )
        for i, p in enumerate(Planet)
    },
)


class TestComputeTransits:
    @patch("src.astrology.transits.get_all_positions", return_value=_mock_positions())
    def test_returns_report(self, mock_pos):
        report = compute_transits(NATAL, datetime.date(2024, 6, 15))
        assert report.ticker == "TEST"
        assert report.date == datetime.date(2024, 6, 15)
        assert isinstance(report.aspects, list)

    @patch("src.astrology.transits.get_all_positions", return_value=_mock_positions())
    def test_finds_aspects(self, mock_pos):
        report = compute_transits(NATAL, datetime.date(2024, 6, 15))
        assert len(report.aspects) > 0
