import datetime
from unittest.mock import patch

from src.astrology.lunar import LunarPhase, get_lunar_phase, PHASE_SCORES
from src.data.ephemeris import Planet, GrahaPosition


class TestLunarPhase:
    @patch("src.astrology.lunar.get_planet_position")
    def test_new_moon(self, mock_pos):
        mock_pos.side_effect = lambda planet, dt: GrahaPosition(
            graha=planet, longitude=100.0, latitude=0.0, speed=1.0,
            rashi_index=int(100.0 // 30), rashi="Test", rashi_en="Test",
            degree_in_rashi=100.0 % 30,
        )
        info = get_lunar_phase(datetime.date(2024, 1, 1))
        assert info.phase == LunarPhase.NEW_MOON
        assert info.elongation < 22.5

    @patch("src.astrology.lunar.get_planet_position")
    def test_full_moon(self, mock_pos):
        def side_effect(planet, dt):
            if planet == Planet.CHANDRA:
                lng = 280.0
            else:
                lng = 100.0
            return GrahaPosition(
                graha=planet, longitude=lng, latitude=0.0, speed=1.0,
                rashi_index=int(lng // 30), rashi="Test", rashi_en="Test",
                degree_in_rashi=lng % 30,
            )
        mock_pos.side_effect = side_effect
        info = get_lunar_phase(datetime.date(2024, 1, 1))
        assert info.phase == LunarPhase.FULL_MOON

    def test_all_phases_have_scores(self):
        for phase in LunarPhase:
            assert phase in PHASE_SCORES
