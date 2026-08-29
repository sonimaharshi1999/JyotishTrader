import datetime

from src.astrology.hora import (
    CHALDEAN_ORDER, DAY_RULERS, HORA_MARKET_ACTION,
    compute_hora_ruler, compute_trading_day_horas,
    get_current_hora, get_hora_recommendation,
)
from src.data.ephemeris import Graha


class TestHoraRuler:
    def test_chaldean_order_has_seven(self):
        assert len(CHALDEAN_ORDER) == 7

    def test_day_rulers_cover_week(self):
        assert len(DAY_RULERS) == 7

    def test_thursday_is_guru(self):
        # Thursday = weekday 3
        assert DAY_RULERS[3] == Graha.GURU

    def test_first_hora_is_day_ruler(self):
        # Monday (weekday 0) = Chandra
        monday = datetime.date(2024, 6, 17)  # A Monday
        ruler = compute_hora_ruler(monday, 0)
        assert ruler == Graha.CHANDRA

    def test_hora_cycles_through_chaldean(self):
        monday = datetime.date(2024, 6, 17)
        rulers = [compute_hora_ruler(monday, i) for i in range(7)]
        # Should cycle through all 7 Chaldean planets starting from Chandra
        assert len(set(rulers)) == 7

    def test_hora_wraps_at_24(self):
        monday = datetime.date(2024, 6, 17)
        r0 = compute_hora_ruler(monday, 0)
        r7 = compute_hora_ruler(monday, 7)
        assert r0 == r7  # Chaldean cycle is 7


class TestMarketActions:
    def test_guru_is_buy(self):
        assert HORA_MARKET_ACTION[Graha.GURU] == "BUY"

    def test_shani_is_sell(self):
        assert HORA_MARKET_ACTION[Graha.SHANI] == "SELL"

    def test_chandra_is_hold(self):
        assert HORA_MARKET_ACTION[Graha.CHANDRA] == "HOLD"

    def test_all_grahas_have_action(self):
        for graha in Graha:
            assert graha in HORA_MARKET_ACTION


class TestTradingDayHoras:
    def test_schedule_has_market_horas(self):
        date = datetime.date(2024, 6, 17)
        schedule = compute_trading_day_horas(date)
        assert len(schedule.horas) == 24
        assert len(schedule.market_horas) > 0
        assert len(schedule.market_horas) <= 8

    def test_buy_and_sell_windows(self):
        date = datetime.date(2024, 6, 17)
        schedule = compute_trading_day_horas(date)
        assert len(schedule.buy_windows) + len(schedule.sell_windows) <= len(schedule.market_horas)


class TestHoraRecommendation:
    def test_bullish_alignment(self):
        dt = datetime.datetime(2024, 6, 20, 10, 0)  # Thursday, Guru's day
        rec = get_hora_recommendation(dt, natal_astro_score=5.0)
        assert rec["final_action"] in ("BUY", "HOLD", "SELL")
        assert isinstance(rec["combined_score"], float)

    def test_bearish_alignment(self):
        dt = datetime.datetime(2024, 6, 22, 10, 0)  # Saturday, Shani's day
        rec = get_hora_recommendation(dt, natal_astro_score=-5.0)
        assert rec["final_action"] in ("BUY", "HOLD", "SELL")
