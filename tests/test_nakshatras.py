from src.astrology.nakshatras import (
    NAKSHATRA_DATA, NAKSHATRA_SPAN, NakshatraInfo,
    get_nakshatra, get_graha_nakshatras,
)
from src.data.ephemeris import Graha, GrahaPosition


class TestNakshatras:
    def test_all_27_defined(self):
        assert len(NAKSHATRA_DATA) == 27

    def test_ashwini_at_zero(self):
        nak = get_nakshatra(0.0)
        assert nak.name == "Ashwini"
        assert nak.index == 0
        assert nak.pada == 1

    def test_last_nakshatra(self):
        nak = get_nakshatra(359.0)
        assert nak.name == "Revati"
        assert nak.index == 26

    def test_pada_calculation(self):
        # Each nakshatra is 13°20', each pada is 3°20'
        nak1 = get_nakshatra(1.0)
        assert nak1.pada == 1

        nak2 = get_nakshatra(5.0)
        assert nak2.pada == 2

        nak3 = get_nakshatra(8.0)
        assert nak3.pada == 3

        nak4 = get_nakshatra(12.0)
        assert nak4.pada == 4

    def test_pushya_is_auspicious(self):
        # Pushya is at index 7, starts at ~93.33°
        nak = get_nakshatra(95.0)
        assert nak.name == "Pushya"
        assert nak.market_score > 0

    def test_mula_is_destructive(self):
        # Mula is at index 18, starts at ~240°
        nak = get_nakshatra(242.0)
        assert nak.name == "Mula"
        assert nak.market_score < 0

    def test_nakshatra_lords(self):
        ashwini = get_nakshatra(0.0)
        assert ashwini.lord == Graha.KETU

        rohini = get_nakshatra(45.0)
        assert rohini.lord == Graha.CHANDRA

    def test_all_have_lords(self):
        for i in range(27):
            lon = i * NAKSHATRA_SPAN + 1.0
            nak = get_nakshatra(lon)
            assert nak.lord is not None


class TestGrahaNakshatras:
    def test_maps_all_grahas(self):
        positions = {
            g: GrahaPosition(
                graha=g, longitude=float(i * 40), latitude=0.0, speed=1.0,
                rashi_index=int(i * 40 // 30), rashi="Mesha",
                rashi_en="Aries", degree_in_rashi=float(i * 40 % 30),
            )
            for i, g in enumerate(Graha)
        }
        result = get_graha_nakshatras(positions)
        assert len(result) == len(Graha)
