from src.astrology.bhavas import build_bhava_chart, analyze_bhavas, BHAVA_NAMES
from src.data.ephemeris import Graha, GrahaPosition


def _pos(graha: Graha, longitude: float) -> GrahaPosition:
    rashi_idx = int(longitude // 30)
    return GrahaPosition(
        graha=graha, longitude=longitude, latitude=0.0, speed=1.0,
        rashi_index=rashi_idx, rashi="Test", rashi_en="Test",
        degree_in_rashi=longitude % 30,
    )


class TestBhavas:
    def test_twelve_houses(self):
        assert len(BHAVA_NAMES) == 12

    def test_build_chart(self):
        positions = {
            Graha.SURYA: _pos(Graha.SURYA, 15.0),     # Mesha (lagna)
            Graha.CHANDRA: _pos(Graha.CHANDRA, 45.0),  # Vrishabha (2nd house)
            Graha.GURU: _pos(Graha.GURU, 135.0),       # Simha (5th house)
            Graha.SHANI: _pos(Graha.SHANI, 315.0),     # Kumbha (11th house)
            Graha.MANGAL: _pos(Graha.MANGAL, 195.0),
            Graha.BUDHA: _pos(Graha.BUDHA, 25.0),
            Graha.SHUKRA: _pos(Graha.SHUKRA, 55.0),
            Graha.RAHU: _pos(Graha.RAHU, 250.0),
            Graha.KETU: _pos(Graha.KETU, 70.0),
        }
        chart = build_bhava_chart(positions)
        assert chart.lagna_rashi == 0  # Mesha
        assert chart.graha_houses[Graha.SURYA] == 1
        assert chart.graha_houses[Graha.CHANDRA] == 2

    def test_guru_in_fifth(self):
        positions = {
            Graha.SURYA: _pos(Graha.SURYA, 15.0),
            Graha.GURU: _pos(Graha.GURU, 135.0),  # 5th from Mesha
            Graha.CHANDRA: _pos(Graha.CHANDRA, 100.0),
            Graha.MANGAL: _pos(Graha.MANGAL, 200.0),
            Graha.BUDHA: _pos(Graha.BUDHA, 25.0),
            Graha.SHUKRA: _pos(Graha.SHUKRA, 55.0),
            Graha.SHANI: _pos(Graha.SHANI, 270.0),
            Graha.RAHU: _pos(Graha.RAHU, 300.0),
            Graha.KETU: _pos(Graha.KETU, 120.0),
        }
        chart = build_bhava_chart(positions)
        assert chart.graha_houses[Graha.GURU] == 5

    def test_analyze_returns_score(self):
        positions = {
            Graha.SURYA: _pos(Graha.SURYA, 15.0),
            Graha.GURU: _pos(Graha.GURU, 45.0),  # 2nd house — wealth
            Graha.CHANDRA: _pos(Graha.CHANDRA, 100.0),
            Graha.MANGAL: _pos(Graha.MANGAL, 200.0),
            Graha.BUDHA: _pos(Graha.BUDHA, 25.0),
            Graha.SHUKRA: _pos(Graha.SHUKRA, 315.0),  # 11th — gains
            Graha.SHANI: _pos(Graha.SHANI, 345.0),     # 12th — loss
            Graha.RAHU: _pos(Graha.RAHU, 250.0),
            Graha.KETU: _pos(Graha.KETU, 70.0),
        }
        chart = build_bhava_chart(positions)
        analysis = analyze_bhavas(chart, positions)
        assert -5.0 <= analysis.total_financial_score <= 5.0
        assert analysis.wealth_house_score > 0  # Guru in 2nd
