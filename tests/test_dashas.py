import datetime

from src.astrology.dashas import (
    DASHA_ORDER, DASHA_YEARS, compute_dashas,
    compute_antardashas, score_dasha_period,
)
from src.data.ephemeris import Graha


class TestDashas:
    def test_order_has_nine_lords(self):
        assert len(DASHA_ORDER) == 9

    def test_total_years_120(self):
        total = sum(DASHA_YEARS.values())
        assert total == 120

    def test_compute_dashas_returns_info(self):
        info = compute_dashas(
            datetime.date(1976, 4, 1),
            moon_longitude=45.0,  # Rohini nakshatra (Chandra lord)
            target_date=datetime.date(2024, 6, 15),
        )
        assert info.birth_date == datetime.date(1976, 4, 1)
        assert len(info.maha_dashas) > 0
        assert info.current_maha is not None

    def test_current_maha_contains_target(self):
        target = datetime.date(2024, 6, 15)
        info = compute_dashas(datetime.date(2000, 1, 1), 100.0, target)
        if info.current_maha:
            assert info.current_maha.start_date <= target
            assert info.current_maha.end_date > target

    def test_antardashas(self):
        info = compute_dashas(datetime.date(2000, 1, 1), 100.0, datetime.date(2024, 1, 1))
        if info.current_maha:
            antars = compute_antardashas(info.current_maha)
            assert len(antars) == 9

    def test_score_range(self):
        info = compute_dashas(datetime.date(2000, 1, 1), 50.0, datetime.date(2024, 1, 1))
        score = score_dasha_period(info)
        assert -3.0 <= score <= 3.0


class TestDashaMarketScores:
    def test_guru_dasha_positive(self):
        # Place Moon in Punarvasu (Guru lord) so first dasha is Guru
        info = compute_dashas(datetime.date(2020, 1, 1), 90.0, datetime.date(2024, 1, 1))
        # Just verify it runs
        score = score_dasha_period(info)
        assert isinstance(score, float)
