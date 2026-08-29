import datetime

from src.astrology.panchang import (
    TITHI_NAMES, YOGA_NAMES, KARANA_NAMES,
    compute_tithi, compute_panchang_yoga, compute_karana, compute_panchang,
)
from src.data.ephemeris import Graha


class TestTithi:
    def test_30_tithis(self):
        assert len(TITHI_NAMES) == 30

    def test_new_moon_is_pratipada(self):
        # Moon and Sun at same longitude = Shukla Pratipada (index 0)
        tithi = compute_tithi(moon_lon=10.0, sun_lon=10.0)
        assert tithi.index == 0
        assert tithi.name == "Pratipada"
        assert tithi.paksha == "Shukla"

    def test_full_moon(self):
        # Moon 180 degrees from Sun = Purnima (index 14)
        tithi = compute_tithi(moon_lon=190.0, sun_lon=10.0)
        assert tithi.index == 14 or tithi.index == 15  # boundary

    def test_amavasya(self):
        # Moon just before catching up to Sun = Amavasya (index 29)
        tithi = compute_tithi(moon_lon=8.0, sun_lon=10.0)
        assert tithi.index == 29
        assert tithi.name == "Amavasya"
        assert tithi.score < 0


class TestPanchangYoga:
    def test_27_yogas(self):
        assert len(YOGA_NAMES) == 27

    def test_yoga_from_longitudes(self):
        yoga = compute_panchang_yoga(moon_lon=100.0, sun_lon=50.0)
        assert yoga.name in YOGA_NAMES
        assert 0 <= yoga.index < 27

    def test_saubhagya_is_best(self):
        from src.astrology.panchang import YOGA_SCORES
        assert YOGA_SCORES[3] == 2.0  # Saubhagya


class TestKarana:
    def test_karana_names(self):
        assert len(KARANA_NAMES) == 11

    def test_karana_from_longitudes(self):
        karana = compute_karana(moon_lon=100.0, sun_lon=50.0)
        assert karana.name in KARANA_NAMES

    def test_vishti_is_worst(self):
        from src.astrology.panchang import KARANA_SCORES
        assert KARANA_SCORES["Vishti"] == -2.0

    def test_vanija_is_best(self):
        from src.astrology.panchang import KARANA_SCORES
        assert KARANA_SCORES["Vanija"] == 2.0


class TestPanchang:
    def test_compute_panchang(self):
        p = compute_panchang(datetime.date(2024, 6, 20))
        assert p.date == datetime.date(2024, 6, 20)
        assert p.tithi.name in TITHI_NAMES
        assert p.yoga.name in YOGA_NAMES
        assert p.karana.name in KARANA_NAMES
        assert p.moon_nakshatra != ""
        assert isinstance(p.composite_score, float)
        assert isinstance(p.is_auspicious, bool)
        assert isinstance(p.warnings, list)

    def test_panchang_has_vara(self):
        p = compute_panchang(datetime.date(2024, 6, 20))  # Thursday
        assert p.vara_ruler == Graha.GURU

    def test_warnings_on_bad_day(self):
        # Can't guarantee a specific bad day, but verify structure
        for day_offset in range(30):
            date = datetime.date(2024, 6, 1) + datetime.timedelta(days=day_offset)
            p = compute_panchang(date)
            assert isinstance(p.warnings, list)
            for w in p.warnings:
                assert isinstance(w, str)
