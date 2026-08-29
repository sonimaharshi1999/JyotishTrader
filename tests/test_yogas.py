from src.astrology.yogas import detect_yogas, score_yogas
from src.data.ephemeris import Graha, GrahaPosition


def _pos(graha: Graha, longitude: float) -> GrahaPosition:
    rashi_idx = int(longitude // 30)
    return GrahaPosition(
        graha=graha, longitude=longitude, latitude=0.0, speed=1.0,
        rashi_index=rashi_idx, rashi="Test", rashi_en="Test",
        degree_in_rashi=longitude % 30,
    )


class TestYogas:
    def test_gaja_kesari(self):
        # Jupiter in kendra (same sign) from Moon
        positions = {
            Graha.CHANDRA: _pos(Graha.CHANDRA, 15.0),  # Mesha
            Graha.GURU: _pos(Graha.GURU, 10.0),         # Mesha (1st from Moon = kendra)
            Graha.SURYA: _pos(Graha.SURYA, 50.0),
            Graha.MANGAL: _pos(Graha.MANGAL, 200.0),
            Graha.BUDHA: _pos(Graha.BUDHA, 100.0),
            Graha.SHUKRA: _pos(Graha.SHUKRA, 150.0),
            Graha.SHANI: _pos(Graha.SHANI, 250.0),
            Graha.RAHU: _pos(Graha.RAHU, 300.0),
            Graha.KETU: _pos(Graha.KETU, 120.0),
        }
        yogas = detect_yogas(positions)
        names = [y.name for y in yogas]
        assert "Gaja Kesari" in names

    def test_budhaditya(self):
        # Mercury and Sun in same sign
        positions = {
            Graha.SURYA: _pos(Graha.SURYA, 45.0),    # Vrishabha
            Graha.BUDHA: _pos(Graha.BUDHA, 50.0),     # Vrishabha
            Graha.CHANDRA: _pos(Graha.CHANDRA, 100.0),
            Graha.MANGAL: _pos(Graha.MANGAL, 200.0),
            Graha.GURU: _pos(Graha.GURU, 150.0),
            Graha.SHUKRA: _pos(Graha.SHUKRA, 250.0),
            Graha.SHANI: _pos(Graha.SHANI, 300.0),
            Graha.RAHU: _pos(Graha.RAHU, 20.0),
            Graha.KETU: _pos(Graha.KETU, 200.0),
        }
        yogas = detect_yogas(positions)
        names = [y.name for y in yogas]
        assert "Budhaditya" in names

    def test_shani_mangal_malefic(self):
        # Saturn and Mars in same sign
        positions = {
            Graha.SHANI: _pos(Graha.SHANI, 100.0),   # Karka
            Graha.MANGAL: _pos(Graha.MANGAL, 105.0),  # Karka
            Graha.SURYA: _pos(Graha.SURYA, 200.0),
            Graha.CHANDRA: _pos(Graha.CHANDRA, 50.0),
            Graha.BUDHA: _pos(Graha.BUDHA, 150.0),
            Graha.GURU: _pos(Graha.GURU, 250.0),
            Graha.SHUKRA: _pos(Graha.SHUKRA, 300.0),
            Graha.RAHU: _pos(Graha.RAHU, 20.0),
            Graha.KETU: _pos(Graha.KETU, 200.0),
        }
        yogas = detect_yogas(positions)
        names = [y.name for y in yogas]
        assert "Shani-Mangal" in names
        scores = [y.market_score for y in yogas if y.name == "Shani-Mangal"]
        assert scores[0] < 0

    def test_score_yogas(self):
        from src.astrology.yogas import Yoga
        yogas = [
            Yoga("Test Bull", "", "", 2.0, []),
            Yoga("Test Bear", "", "", -1.0, []),
        ]
        assert score_yogas(yogas) == 1.0

    def test_empty_yogas(self):
        assert score_yogas([]) == 0.0
