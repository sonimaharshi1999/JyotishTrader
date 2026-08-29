import tempfile
from pathlib import Path

from src.signals.correlation import CorrelationTracker, SignalOutcome


class TestCorrelationTracker:
    def test_record_and_query(self):
        tracker = CorrelationTracker()
        outcome = SignalOutcome(
            ticker="AAPL", date="2024-01-15", direction="BUY",
            composite_score=5.0, dominant_aspect="JUPITER TRINE SUN",
            entry_price=150.0, exit_price=160.0,
            holding_days=10, actual_return_pct=6.67,
        )
        tracker.record_outcome(outcome)

        assert len(tracker.outcomes) == 1
        assert "JUPITER TRINE SUN" in tracker.aspect_stats

    def test_accuracy(self):
        tracker = CorrelationTracker()
        for i in range(20):
            pct = 5.0 if i % 2 == 0 else -3.0
            tracker.record_outcome(SignalOutcome(
                ticker="TEST", date=f"2024-01-{i+1:02d}", direction="BUY",
                composite_score=4.0, dominant_aspect="JUPITER CONJ SUN",
                entry_price=100.0, exit_price=100 + pct,
                holding_days=5, actual_return_pct=pct,
            ))

        stats = tracker.aspect_stats["JUPITER CONJ SUN"]
        assert stats.total_signals == 20
        assert stats.accuracy == 0.5

    def test_save_and_load(self):
        tracker = CorrelationTracker()
        tracker.record_outcome(SignalOutcome(
            ticker="AAPL", date="2024-01-15", direction="BUY",
            composite_score=5.0, dominant_aspect="MARS SQUARE MOON",
            actual_return_pct=3.0,
        ))

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        tracker.save(path)
        loaded = CorrelationTracker.load(path)
        assert len(loaded.outcomes) == 1
        assert "MARS SQUARE MOON" in loaded.aspect_stats
        path.unlink()

    def test_weight_adjustment(self):
        tracker = CorrelationTracker()
        for i in range(15):
            tracker.record_outcome(SignalOutcome(
                ticker="TEST", date=f"2024-01-{i+1:02d}", direction="BUY",
                composite_score=4.0, dominant_aspect="HIGH_ACC",
                actual_return_pct=5.0,
            ))
        adj = tracker.get_aspect_weight_adjustment("HIGH_ACC")
        assert adj > 1.0

    def test_unknown_aspect(self):
        tracker = CorrelationTracker()
        adj = tracker.get_aspect_weight_adjustment("UNKNOWN")
        assert adj == 1.0
