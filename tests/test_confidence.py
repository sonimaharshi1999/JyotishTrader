import datetime
from unittest.mock import patch

from src.astrology.aspects import Drishti, DrishtiType
from src.astrology.scoring import AstroScore
from src.astrology.transits import TransitAspect, TransitReport
from src.data.ephemeris import Planet
from src.signals.confidence import compute_confidence


def _make_score(value: float) -> AstroScore:
    return AstroScore(
        ticker="TEST", raw_score=value, clamped_score=value,
        aspect_count=3, dominant_aspect="GURU FULL SURYA",
        drishti_score=value, dasha_score=0.0, nakshatra_score=0.0,
        yoga_score=0.0, bhava_score=0.0, active_yogas=[],
        current_dasha=None, moon_nakshatra=None,
    )


def _make_report(num_bullish: int = 2, num_bearish: int = 1) -> TransitReport:
    aspects = []
    for _ in range(num_bullish):
        aspects.append(TransitAspect(
            transit_planet=Planet.GURU, natal_planet=Planet.SURYA,
            aspect=Drishti(DrishtiType.FULL, 0.0, 180.0, 2.0, 3, graha=Planet.GURU),
        ))
    for _ in range(num_bearish):
        aspects.append(TransitAspect(
            transit_planet=Planet.SHANI, natal_planet=Planet.SURYA,
            aspect=Drishti(DrishtiType.FULL, 0.0, 180.0, 3.0, -3, graha=Planet.SHANI),
        ))
    return TransitReport(
        date=datetime.date(2024, 6, 17),
        ticker="TEST", transit_positions={}, aspects=aspects,
    )


class TestConfidence:
    @patch("src.signals.confidence.compute_eclipse_impact", return_value=[])
    @patch("src.signals.confidence.get_planetary_day_info")
    @patch("src.signals.confidence.get_lunar_phase")
    def test_score_range(self, mock_lunar, mock_day, mock_eclipse):
        from src.astrology.lunar import LunarInfo, LunarPhase
        from src.astrology.planetary_hours import PlanetaryDayInfo
        mock_lunar.return_value = LunarInfo(
            datetime.date(2024, 6, 17), LunarPhase.WAXING_CRESCENT,
            50.0, 30.0, 20.0, 1.0,
        )
        mock_day.return_value = PlanetaryDayInfo(
            datetime.date(2024, 6, 17), Planet.GURU, 1.0,
        )

        score = _make_score(5.0)
        report = _make_report()
        conf = compute_confidence(score, report, trend_signal=1)

        assert 0 <= conf.score <= 100
        assert conf.label in ("Very Low", "Low", "Moderate", "High", "Very High")

    @patch("src.signals.confidence.compute_eclipse_impact", return_value=[])
    @patch("src.signals.confidence.get_planetary_day_info")
    @patch("src.signals.confidence.get_lunar_phase")
    def test_no_aspects(self, mock_lunar, mock_day, mock_eclipse):
        from src.astrology.lunar import LunarInfo, LunarPhase
        from src.astrology.planetary_hours import PlanetaryDayInfo
        mock_lunar.return_value = LunarInfo(
            datetime.date(2024, 6, 17), LunarPhase.FIRST_QUARTER,
            50.0, 30.0, 90.0, 0.5,
        )
        mock_day.return_value = PlanetaryDayInfo(
            datetime.date(2024, 6, 17), Planet.SHANI, -0.8,
        )

        score = _make_score(0.0)
        report = TransitReport(
            date=datetime.date(2024, 6, 17),
            ticker="TEST", transit_positions={}, aspects=[],
        )
        conf = compute_confidence(score, report, trend_signal=0)
        assert conf.score >= 0
