import datetime
from src.astrology.aspects import Drishti, DrishtiType
from src.astrology.scoring import score_transit_report
from src.astrology.transits import TransitAspect, TransitReport
from src.data.ephemeris import Graha, GrahaPosition


def _make_transit_aspect(
    drishti_type: DrishtiType,
    weight: int,
    orb: float = 0.0,
) -> TransitAspect:
    return TransitAspect(
        transit_planet=Graha.GURU,
        natal_planet=Graha.SURYA,
        aspect=Drishti(
            drishti_type=drishti_type,
            natal_longitude=0.0,
            transit_longitude=180.0,
            orb_actual=orb,
            weight=weight,
            graha=Graha.GURU,
        ),
    )


def _make_report(aspects: list[TransitAspect]) -> TransitReport:
    return TransitReport(
        date=datetime.date(2024, 1, 1),
        ticker="TEST",
        transit_positions={},
        aspects=aspects,
    )


class TestScoring:
    def test_empty_aspects(self):
        report = _make_report([])
        score = score_transit_report(report)
        assert score.aspect_count == 0

    def test_single_benefic_aspect(self):
        ta = _make_transit_aspect(DrishtiType.FULL, weight=3)
        report = _make_report([ta])
        score = score_transit_report(report)
        assert score.drishti_score > 0

    def test_single_malefic_aspect(self):
        ta = _make_transit_aspect(DrishtiType.FULL, weight=-3)
        report = _make_report([ta])
        score = score_transit_report(report)
        assert score.drishti_score < 0

    def test_score_clamped(self):
        aspects = [_make_transit_aspect(DrishtiType.FULL, weight=3) for _ in range(20)]
        report = _make_report(aspects)
        score = score_transit_report(report)
        assert score.clamped_score <= 10.0
        assert score.clamped_score >= -10.0

    def test_vedic_components_present(self):
        report = _make_report([])
        score = score_transit_report(report)
        assert hasattr(score, "drishti_score")
        assert hasattr(score, "dasha_score")
        assert hasattr(score, "nakshatra_score")
        assert hasattr(score, "yoga_score")
        assert hasattr(score, "bhava_score")
