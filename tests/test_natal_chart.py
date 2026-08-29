import datetime
from unittest.mock import patch, MagicMock

from src.astrology.natal_chart import build_natal_chart
from src.data.ephemeris import Planet, GrahaPosition


def _mock_positions(dt):
    return {
        p: GrahaPosition(
            graha=p, longitude=float(i * 30), latitude=0.0, speed=1.0,
            rashi_index=int(float(i * 30) // 30), rashi="Test", rashi_en="Test",
            degree_in_rashi=float(i * 30) % 30,
        )
        for i, p in enumerate(Planet)
    }


class TestBuildNatalChart:
    @patch("src.astrology.natal_chart.get_all_positions", side_effect=_mock_positions)
    def test_creates_chart(self, mock_pos):
        chart = build_natal_chart("AAPL", datetime.date(1976, 4, 1))
        assert chart.ticker == "AAPL"
        assert chart.birth_date == datetime.date(1976, 4, 1)
        assert len(chart.positions) == len(Planet)

    @patch("src.astrology.natal_chart.get_all_positions", side_effect=_mock_positions)
    def test_get_planet(self, mock_pos):
        chart = build_natal_chart("MSFT", datetime.date(1975, 4, 4))
        sun = chart.get_planet(Planet.SURYA)
        assert sun.graha == Planet.SURYA
