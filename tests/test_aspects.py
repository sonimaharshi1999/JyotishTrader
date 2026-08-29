from src.astrology.aspects import DrishtiType, find_drishti, find_all_drishtis, GRAHA_WEIGHTS
from src.data.ephemeris import Graha


class TestFindDrishti:
    def test_seventh_house_aspect(self):
        # All grahas aspect the 7th house from themselves
        # Transit at 10° aspects natal at 190° (7 houses away)
        drishti = find_drishti(190.0, 10.0, Graha.SURYA)
        assert drishti is not None
        assert drishti.drishti_type == DrishtiType.FULL

    def test_jupiter_fifth_aspect(self):
        # Jupiter at 0° (Mesha) aspects 5th house = 120° (Simha)
        drishti = find_drishti(120.0, 0.0, Graha.GURU)
        assert drishti is not None

    def test_jupiter_ninth_aspect(self):
        # Jupiter at 0° (Mesha) aspects 9th house = 240° (Dhanu)
        drishti = find_drishti(240.0, 0.0, Graha.GURU)
        assert drishti is not None

    def test_saturn_third_aspect(self):
        # Saturn at 0° (Mesha) aspects 3rd house = 60° (Mithuna)
        drishti = find_drishti(60.0, 0.0, Graha.SHANI)
        assert drishti is not None

    def test_saturn_tenth_aspect(self):
        # Saturn at 0° (Mesha) aspects 10th house = 270° (Makara)
        drishti = find_drishti(270.0, 0.0, Graha.SHANI)
        assert drishti is not None

    def test_mars_fourth_aspect(self):
        # Mars at 0° (Mesha) aspects 4th house = 90° (Karka)
        drishti = find_drishti(90.0, 0.0, Graha.MANGAL)
        assert drishti is not None

    def test_mars_eighth_aspect(self):
        # Mars at 0° (Mesha) aspects 8th house = 210° (Vrischika)
        drishti = find_drishti(210.0, 0.0, Graha.MANGAL)
        assert drishti is not None

    def test_no_aspect_when_not_aspecting(self):
        # Sun only aspects 7th — should NOT aspect the 5th from itself
        # Sun at 0°, natal at 120° (5th house from Sun) — Sun doesn't aspect 5th
        drishti = find_drishti(120.0, 0.0, Graha.SURYA)
        assert drishti is None

    def test_graha_weights(self):
        assert GRAHA_WEIGHTS[Graha.GURU] > 0   # benefic
        assert GRAHA_WEIGHTS[Graha.SHANI] < 0  # malefic
        assert GRAHA_WEIGHTS[Graha.SHUKRA] > 0  # benefic

    def test_rahu_aspects_fifth(self):
        # Rahu at 0° aspects 5th house = 120°
        d5 = find_drishti(120.0, 0.0, Graha.RAHU)
        assert d5 is not None

    def test_rahu_aspects_seventh(self):
        # Rahu at 0° aspects 7th house = 180°
        d7 = find_drishti(180.0, 0.0, Graha.RAHU)
        assert d7 is not None


class TestFindAllDrishtis:
    def test_finds_drishtis(self):
        # Guru at 10° aspects natal Surya at 190° (7th house)
        natal = {"Surya": 190.0}
        transit = {"Guru": 10.0}
        grahas = {"Guru": Graha.GURU}
        results = find_all_drishtis(natal, transit, grahas)
        assert len(results) >= 1

    def test_empty_when_no_aspect(self):
        # Sun at 0° only aspects 7th (180°), natal at 120° is not aspected
        natal = {"Surya": 120.0}
        transit = {"Surya": 0.0}
        grahas = {"Surya": Graha.SURYA}
        results = find_all_drishtis(natal, transit, grahas)
        assert len(results) == 0
