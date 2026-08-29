import datetime

from src.astrology.muhurta import (
    MUHURTA_NAMES, MUHURTA_SCORES, MUHURTAS_PER_DAY,
    compute_muhurta_schedule, get_current_muhurta,
    compute_rahu_kaal, is_in_rahu_kaal,
)


class TestMuhurta:
    def test_30_muhurtas_per_day(self):
        assert MUHURTAS_PER_DAY == 30

    def test_30_names(self):
        assert len(MUHURTA_NAMES) == 30

    def test_all_have_scores(self):
        for i in range(30):
            assert i in MUHURTA_SCORES

    def test_schedule_returns_market_hours(self):
        date = datetime.date(2024, 6, 20)
        windows = compute_muhurta_schedule(date)
        assert len(windows) > 0
        for w in windows:
            assert 9 <= w.start_time.hour < 16

    def test_current_muhurta(self):
        dt = datetime.datetime(2024, 6, 20, 11, 0)
        m = get_current_muhurta(dt)
        assert m.name in MUHURTA_NAMES
        assert -2.0 <= m.score <= 2.0

    def test_abhijit_muhurta(self):
        dt = datetime.datetime(2024, 6, 20, 11, 0)
        # Abhijit is around midday, index 14
        schedule = compute_muhurta_schedule(datetime.date(2024, 6, 20))
        abhijits = [w for w in schedule if w.is_abhijit]
        # May or may not fall in market hours depending on sunrise
        # Just check the property works
        for w in schedule:
            assert isinstance(w.is_abhijit, bool)


class TestRahuKaal:
    def test_rahu_kaal_varies_by_day(self):
        monday = datetime.date(2024, 6, 17)
        tuesday = datetime.date(2024, 6, 18)
        rk_mon = compute_rahu_kaal(monday)
        rk_tue = compute_rahu_kaal(tuesday)
        assert rk_mon != rk_tue

    def test_rahu_kaal_duration(self):
        date = datetime.date(2024, 6, 20)
        start, end = compute_rahu_kaal(date)
        assert end - start == 1.5  # 1.5 hours

    def test_is_in_rahu_kaal(self):
        date = datetime.date(2024, 6, 17)  # Monday, Rahu Kaal = 2nd hora
        start, end = compute_rahu_kaal(date)
        dt_in = datetime.datetime(date.year, date.month, date.day, int(start), 30)
        dt_out = datetime.datetime(date.year, date.month, date.day, int(end) + 1, 0)
        assert is_in_rahu_kaal(dt_in)
        assert not is_in_rahu_kaal(dt_out)

    def test_muhurta_rahu_kaal_flag(self):
        date = datetime.date(2024, 6, 20)
        schedule = compute_muhurta_schedule(date)
        # At least some muhurtas should NOT be in Rahu Kaal
        non_rahu = [w for w in schedule if not w.is_rahu_kaal]
        assert len(non_rahu) > 0
