from __future__ import annotations

import logging
from collections import defaultdict

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

market_data_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

broker_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=1, max=60),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class CircuitBreaker:
    def __init__(self, max_failures: int = 3) -> None:
        self.max_failures = max_failures
        self._failures: dict[str, int] = defaultdict(int)

    def record_failure(self, key: str) -> None:
        self._failures[key] += 1

    def record_success(self, key: str) -> None:
        self._failures[key] = 0

    def is_open(self, key: str) -> bool:
        return self._failures[key] >= self.max_failures

    def reset(self) -> None:
        self._failures.clear()
