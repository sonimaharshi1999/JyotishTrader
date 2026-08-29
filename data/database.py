from __future__ import annotations

import datetime
import json
import logging
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/astro_trader.db")


@contextmanager
def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                direction TEXT NOT NULL,
                astro_score REAL NOT NULL,
                trend_signal INTEGER NOT NULL,
                composite_score REAL NOT NULL,
                dominant_aspect TEXT,
                confidence INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(ticker, date)
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                entry_price TEXT NOT NULL,
                exit_date TEXT,
                exit_price TEXT,
                shares INTEGER NOT NULL,
                side TEXT NOT NULL DEFAULT 'buy',
                pnl_pct REAL,
                order_id TEXT,
                signal_id INTEGER REFERENCES signals(id),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                cash TEXT NOT NULL,
                total_value TEXT NOT NULL,
                exposure_pct REAL NOT NULL,
                positions_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(date)
            );

            CREATE TABLE IF NOT EXISTS correlation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                direction TEXT NOT NULL,
                composite_score REAL NOT NULL,
                dominant_aspect TEXT,
                entry_price REAL,
                exit_price REAL,
                holding_days INTEGER,
                actual_return_pct REAL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_signals_ticker_date ON signals(ticker, date);
            CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
            CREATE INDEX IF NOT EXISTS idx_trades_side_exit ON trades(side, exit_date);
            CREATE INDEX IF NOT EXISTS idx_snapshots_date ON portfolio_snapshots(date);
        """)


def save_signal(
    conn: sqlite3.Connection,
    ticker: str,
    date: datetime.date,
    direction: str,
    astro_score: float,
    trend_signal: int,
    composite_score: float,
    dominant_aspect: str | None = None,
    confidence: int | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT OR REPLACE INTO signals
           (ticker, date, direction, astro_score, trend_signal, composite_score, dominant_aspect, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (ticker, str(date), direction, astro_score, trend_signal, composite_score, dominant_aspect, confidence),
    )
    return cursor.lastrowid


def save_trade(
    conn: sqlite3.Connection,
    ticker: str,
    entry_date: datetime.date,
    entry_price: Decimal,
    shares: int,
    side: str = "buy",
    signal_id: int | None = None,
    exit_date: datetime.date | None = None,
    exit_price: Decimal | None = None,
    pnl_pct: float | None = None,
    order_id: str | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO trades
           (ticker, entry_date, entry_price, shares, side, signal_id, exit_date, exit_price, pnl_pct, order_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ticker, str(entry_date), str(entry_price), shares, side, signal_id,
         str(exit_date) if exit_date else None,
         str(exit_price) if exit_price else None,
         pnl_pct, order_id),
    )
    return cursor.lastrowid


def update_trade_exit(
    conn: sqlite3.Connection,
    trade_id: int,
    exit_date: datetime.date,
    exit_price: Decimal,
    pnl_pct: float,
) -> None:
    conn.execute(
        """UPDATE trades SET exit_date=?, exit_price=?, pnl_pct=?, updated_at=datetime('now')
           WHERE id=?""",
        (str(exit_date), str(exit_price), pnl_pct, trade_id),
    )


def get_open_trades(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM trades WHERE exit_date IS NULL ORDER BY entry_date DESC",
    ).fetchall()
    return [dict(r) for r in rows]


def save_portfolio_snapshot(
    conn: sqlite3.Connection,
    date: datetime.date,
    cash: Decimal,
    total_value: Decimal,
    exposure_pct: float,
    positions: dict,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO portfolio_snapshots
           (date, cash, total_value, exposure_pct, positions_json)
           VALUES (?, ?, ?, ?, ?)""",
        (str(date), str(cash), str(total_value), exposure_pct, json.dumps(positions)),
    )


def load_latest_snapshot(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT * FROM portfolio_snapshots ORDER BY date DESC LIMIT 1",
    ).fetchone()
    return dict(row) if row else None


def get_signals_for_date(conn: sqlite3.Connection, date: datetime.date) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM signals WHERE date = ? ORDER BY composite_score DESC",
        (str(date),),
    ).fetchall()
    return [dict(r) for r in rows]


def get_trade_history(conn: sqlite3.Connection, ticker: str | None = None, limit: int = 100) -> list[dict]:
    if ticker:
        rows = conn.execute(
            "SELECT * FROM trades WHERE ticker = ? ORDER BY entry_date DESC LIMIT ?",
            (ticker, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY entry_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_portfolio_history(conn: sqlite3.Connection, limit: int = 365) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM portfolio_snapshots ORDER BY date DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_closed_trade_pnls(conn: sqlite3.Connection, limit: int = 100) -> list[float]:
    rows = conn.execute(
        "SELECT pnl_pct FROM trades WHERE pnl_pct IS NOT NULL ORDER BY entry_date DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [r["pnl_pct"] for r in rows]
