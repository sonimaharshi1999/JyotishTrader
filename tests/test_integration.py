import datetime
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from src.data.company_registry import CompanyInfo
from src.data.database import (
    get_connection, get_signals_for_date, get_trade_history,
    get_portfolio_history, init_db,
)
from src.settings import PortfolioSettings
from src.signals.generator import SignalDirection, TradingSignal
from src.trading.broker import PaperBroker
from src.trading.executor import TradingExecutor


COMPANY = CompanyInfo(
    ticker="TEST", incorporation_date=datetime.date(2000, 1, 1),
    incorporation_location="New York NY", sector="Technology",
)


class TestFullPipeline:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self.tmp.name)
        self.tmp.close()
        init_db(self.db_path)
        self.broker = PaperBroker(100000)
        self.settings = PortfolioSettings()
        self.executor = TradingExecutor(
            broker=self.broker,
            settings=self.settings,
            db_path=self.db_path,
            company_registry={"TEST": COMPANY},
        )

    def teardown_method(self):
        self.db_path.unlink(missing_ok=True)

    def test_buy_signal_executes_and_persists(self):
        self.broker.update_price = lambda t, p: None
        signal = TradingSignal(
            ticker="TEST", date=datetime.date.today(),
            direction=SignalDirection.BUY,
            astro_score=5.0, trend_signal=1, composite_score=6.5,
            dominant_aspect="GURU FULL SURYA", confidence=75,
        )

        result = self.executor.execute_signal(signal, Decimal("150.00"))

        assert result is not None
        assert result.is_filled
        assert "TEST" in self.broker.get_positions()

        with get_connection(self.db_path) as conn:
            signals = get_signals_for_date(conn, datetime.date.today())
            assert len(signals) >= 1
            assert signals[0]["ticker"] == "TEST"

            trades = get_trade_history(conn, "TEST")
            assert len(trades) >= 1

    def test_sell_without_position_is_noop(self):
        signal = TradingSignal(
            ticker="TEST", date=datetime.date.today(),
            direction=SignalDirection.SELL,
            astro_score=-5.0, trend_signal=-1, composite_score=-6.5,
            dominant_aspect="SHANI FULL SURYA",
        )
        result = self.executor.execute_signal(signal, Decimal("150.00"))
        assert result is None

    def test_hold_does_not_trade(self):
        signal = TradingSignal(
            ticker="TEST", date=datetime.date.today(),
            direction=SignalDirection.HOLD,
            astro_score=0.0, trend_signal=0, composite_score=0.0,
            dominant_aspect=None,
        )
        result = self.executor.execute_signal(signal, Decimal("150.00"))
        assert result is None
        assert len(self.broker.get_positions()) == 0

    def test_trailing_stop_triggers_sell(self):
        self.broker.update_price("TEST", Decimal("150.00"))
        self.broker.submit_order("TEST", 10, "buy")
        # Entry at $150, trailing stop at 7% = $139.50

        self.executor.sync_positions()
        # Raise price so trailing stop ratchets up
        self.broker.update_price("TEST", Decimal("200.00"))
        self.executor.sync_positions()
        # Now stop is at $200 * 0.93 = $186

        # Drop well below stop
        self.broker.update_price("TEST", Decimal("180.00"))

        results = self.executor.check_trailing_stops()
        assert len(results) >= 1
        assert "TEST" not in self.broker.get_positions()

    def test_sector_limit_blocks_overconcentration(self):
        self.executor.settings.max_sector_pct = 0.01  # 1% — very low

        signal = TradingSignal(
            ticker="TEST", date=datetime.date.today(),
            direction=SignalDirection.BUY,
            astro_score=8.0, trend_signal=1, composite_score=10.0,
            dominant_aspect="GURU FULL SURYA",
        )
        result = self.executor.execute_signal(signal, Decimal("50000.00"))
        assert result is None  # blocked by sector limit

    def test_portfolio_snapshot_persists(self):
        self.executor.snapshot_portfolio()

        with get_connection(self.db_path) as conn:
            history = get_portfolio_history(conn)
        assert len(history) >= 1

    def test_max_exposure_blocks_buy(self):
        self.executor.settings.max_exposure_pct = 0.01  # 1%
        for i in range(5):
            self.broker.submit_order(f"POS{i}", 100, "buy")
            self.broker.update_price(f"POS{i}", Decimal("1000.00"))

        self.executor.sync_positions()

        signal = TradingSignal(
            ticker="TEST", date=datetime.date.today(),
            direction=SignalDirection.BUY,
            astro_score=8.0, trend_signal=1, composite_score=10.0,
            dominant_aspect="GURU FULL SURYA",
        )
        result = self.executor.execute_signal(signal, Decimal("150.00"))
        assert result is None


class TestBrokerProtocol:
    def test_paper_broker_implements_protocol(self):
        from src.trading.broker import Broker
        broker = PaperBroker()
        assert isinstance(broker, Broker)

    def test_paper_broker_buy_sell_cycle(self):
        broker = PaperBroker(100000)
        broker.update_price("AAPL", Decimal("150.00"))

        buy = broker.submit_order("AAPL", 10, "buy")
        assert buy.is_filled
        assert buy.filled_qty == 10
        assert "AAPL" in broker.get_positions()

        sell = broker.submit_order("AAPL", 10, "sell")
        assert sell.is_filled
        assert "AAPL" not in broker.get_positions()

    def test_paper_broker_insufficient_funds(self):
        broker = PaperBroker(10)
        broker.update_price("AAPL", Decimal("150.00"))
        result = broker.submit_order("AAPL", 10, "buy")
        assert result.status == "rejected"
