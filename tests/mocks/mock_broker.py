"""Re-export PaperBroker as the test mock — it already implements the Broker protocol."""
from src.trading.broker import PaperBroker as MockBroker

__all__ = ["MockBroker"]
