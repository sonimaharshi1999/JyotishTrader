from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SignalOutcome:
    ticker: str
    date: str
    direction: str
    composite_score: float
    dominant_aspect: str | None
    entry_price: float | None = None
    exit_price: float | None = None
    holding_days: int | None = None
    actual_return_pct: float | None = None

    @property
    def was_correct(self) -> bool | None:
        if self.actual_return_pct is None:
            return None
        if self.direction == "BUY":
            return self.actual_return_pct > 0
        elif self.direction == "SELL":
            return self.actual_return_pct < 0
        return None


@dataclass
class AspectPerformance:
    aspect_key: str
    total_signals: int = 0
    correct_signals: int = 0
    total_return_pct: float = 0.0

    @property
    def accuracy(self) -> float:
        if self.total_signals == 0:
            return 0.0
        return self.correct_signals / self.total_signals

    @property
    def avg_return(self) -> float:
        if self.total_signals == 0:
            return 0.0
        return self.total_return_pct / self.total_signals


@dataclass
class CorrelationTracker:
    outcomes: list[SignalOutcome] = field(default_factory=list)
    aspect_stats: dict[str, AspectPerformance] = field(default_factory=dict)

    def record_outcome(self, outcome: SignalOutcome) -> None:
        self.outcomes.append(outcome)

        if outcome.dominant_aspect and outcome.actual_return_pct is not None:
            key = outcome.dominant_aspect
            if key not in self.aspect_stats:
                self.aspect_stats[key] = AspectPerformance(aspect_key=key)

            stats = self.aspect_stats[key]
            stats.total_signals += 1
            stats.total_return_pct += outcome.actual_return_pct
            if outcome.was_correct:
                stats.correct_signals += 1

    def get_aspect_weight_adjustment(self, aspect_key: str) -> float:
        stats = self.aspect_stats.get(aspect_key)
        if stats is None or stats.total_signals < 10:
            return 1.0
        accuracy = stats.accuracy
        if accuracy >= 0.6:
            return 1.0 + (accuracy - 0.5) * 2
        elif accuracy <= 0.4:
            return max(0.2, accuracy * 2)
        return 1.0

    def get_top_aspects(self, n: int = 10) -> list[AspectPerformance]:
        valid = [s for s in self.aspect_stats.values() if s.total_signals >= 5]
        return sorted(valid, key=lambda s: s.accuracy, reverse=True)[:n]

    def get_worst_aspects(self, n: int = 10) -> list[AspectPerformance]:
        valid = [s for s in self.aspect_stats.values() if s.total_signals >= 5]
        return sorted(valid, key=lambda s: s.accuracy)[:n]

    def save(self, path: Path | str) -> None:
        path = Path(path)
        data = {
            "outcomes": [asdict(o) for o in self.outcomes],
            "aspect_stats": {k: asdict(v) for k, v in self.aspect_stats.items()},
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> CorrelationTracker:
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            tracker = cls()
            for o in data.get("outcomes", []):
                tracker.outcomes.append(SignalOutcome(**o))
            for k, v in data.get("aspect_stats", {}).items():
                tracker.aspect_stats[k] = AspectPerformance(**v)
            return tracker
        except Exception:
            logger.warning("Failed to load correlation data from %s", path, exc_info=True)
            return cls()
