import datetime
import tempfile
from decimal import Decimal
from pathlib import Path

from src.data.database import (
    get_connection, init_db, save_signal, save_trade,
    save_portfolio_snapshot, get_signals_for_date, get_trade_history,
)


class TestDatabase:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self.tmp.name)
        self.tmp.close()
        init_db(self.db_path)

    def teardown_method(self):
        self.db_path.unlink(missing_ok=True)

    def test_init_creates_tables(self):
        with get_connection(self.db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            names = {r["name"] for r in tables}
        assert "signals" in names
        assert "trades" in names
        assert "portfolio_snapshots" in names

    def test_save_and_get_signal(self):
        with get_connection(self.db_path) as conn:
            save_signal(conn, "AAPL", datetime.date(2024, 6, 15),
                        "BUY", 5.0, 1, 6.5, "JUPITER TRINE SUN", 75)

        with get_connection(self.db_path) as conn:
            signals = get_signals_for_date(conn, datetime.date(2024, 6, 15))
        assert len(signals) == 1
        assert signals[0]["ticker"] == "AAPL"
        assert signals[0]["confidence"] == 75

    def test_save_and_get_trade(self):
        with get_connection(self.db_path) as conn:
            save_trade(conn, "MSFT", datetime.date(2024, 1, 1),
                       Decimal("350.00"), 10)

        with get_connection(self.db_path) as conn:
            trades = get_trade_history(conn, "MSFT")
        assert len(trades) == 1
        assert trades[0]["shares"] == 10

    def test_portfolio_snapshot(self):
        with get_connection(self.db_path) as conn:
            save_portfolio_snapshot(
                conn, datetime.date(2024, 6, 15),
                Decimal("90000"), Decimal("100000"), 0.10,
                {"AAPL": {"shares": 10, "price": "1000"}},
            )

        with get_connection(self.db_path) as conn:
            from src.data.database import get_portfolio_history
            history = get_portfolio_history(conn)
        assert len(history) == 1
