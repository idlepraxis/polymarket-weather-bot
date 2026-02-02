"""Database for storing historical market data for backtesting."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from bot.utils.logger import get_logger


class BacktestDatabase:
    """SQLite database for backtesting historical data.

    Stores:
    - Market snapshots (prices at various times)
    - Weather forecasts at snapshot time
    - Resolution outcomes

    This allows replaying strategy logic with different parameters.
    """

    def __init__(self, db_path: str = "data/backtest.db"):
        self.db_path = db_path
        self.logger = get_logger()
        self._ensure_db_exists()
        self._init_db()

    def _ensure_db_exists(self):
        """Create database directory if needed."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Market snapshots - captures market state at a point in time
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_time TIMESTAMP NOT NULL,
                platform TEXT NOT NULL,
                market_id TEXT NOT NULL,
                question TEXT,
                yes_price REAL,
                no_price REAL,
                volume REAL,
                end_date TIMESTAMP,
                -- Parsed market info
                location TEXT,
                threshold REAL,
                threshold_type TEXT,
                threshold_direction TEXT,
                range_low REAL,
                range_high REAL,
                is_range BOOLEAN,
                market_date DATE,
                -- Weather forecast at snapshot time
                forecast_high_f REAL,
                forecast_low_f REAL,
                forecast_source TEXT,
                -- Calculated probability at snapshot
                fair_probability REAL,
                edge REAL,
                -- Resolution (filled in later)
                resolved BOOLEAN DEFAULT 0,
                resolution_time TIMESTAMP,
                yes_won BOOLEAN,
                actual_temp REAL,
                -- Metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(snapshot_time, platform, market_id)
            )
        ''')

        # Indices for efficient querying
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_snapshots_time
            ON market_snapshots(snapshot_time)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_snapshots_market
            ON market_snapshots(market_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_snapshots_resolved
            ON market_snapshots(resolved)
        ''')

        # Strategy results - stores backtest results for comparison
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                run_name TEXT,
                -- Strategy parameters used
                params_json TEXT,
                -- Results
                total_trades INTEGER,
                wins INTEGER,
                losses INTEGER,
                win_rate REAL,
                total_pnl REAL,
                total_invested REAL,
                roi REAL,
                -- Breakdown
                results_json TEXT
            )
        ''')

        conn.commit()
        conn.close()
        self.logger.info(f"Backtest database initialized at {self.db_path}")

    def record_market_snapshot(
        self,
        platform: str,
        market_id: str,
        question: str,
        yes_price: float,
        no_price: float,
        end_date: datetime,
        parsed_info: Dict[str, Any],
        forecast: Optional[Dict[str, Any]] = None,
        fair_probability: Optional[float] = None,
        edge: Optional[float] = None,
        volume: Optional[float] = None,
        snapshot_time: Optional[datetime] = None,
    ) -> int:
        """Record a market snapshot for backtesting.

        Args:
            platform: Trading platform (kalshi, polymarket)
            market_id: Unique market identifier
            question: Market question text
            yes_price: Current YES price
            no_price: Current NO price
            end_date: Market resolution date
            parsed_info: Parsed market info (location, threshold, etc.)
            forecast: Weather forecast data
            fair_probability: Calculated fair probability
            edge: Calculated edge
            volume: Market volume/liquidity
            snapshot_time: Time of snapshot (defaults to now)

        Returns:
            Snapshot ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        snapshot_time = snapshot_time or datetime.utcnow()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO market_snapshots (
                    snapshot_time, platform, market_id, question,
                    yes_price, no_price, volume, end_date,
                    location, threshold, threshold_type, threshold_direction,
                    range_low, range_high, is_range, market_date,
                    forecast_high_f, forecast_low_f, forecast_source,
                    fair_probability, edge
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                snapshot_time.isoformat(),
                platform,
                market_id,
                question,
                yes_price,
                no_price,
                volume,
                end_date.isoformat() if end_date else None,
                parsed_info.get("location"),
                parsed_info.get("threshold"),
                parsed_info.get("threshold_type"),
                parsed_info.get("threshold_direction"),
                parsed_info.get("range_low"),
                parsed_info.get("range_high"),
                parsed_info.get("is_range", False),
                parsed_info.get("date").date().isoformat() if parsed_info.get("date") else None,
                forecast.get("temp_high_f") if forecast else None,
                forecast.get("temp_low_f") if forecast else None,
                forecast.get("source") if forecast else None,
                fair_probability,
                edge,
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_resolution(
        self,
        market_id: str,
        yes_won: bool,
        actual_temp: Optional[float] = None,
        resolution_time: Optional[datetime] = None,
    ):
        """Update a market snapshot with resolution data.

        Args:
            market_id: Market to update
            yes_won: Whether YES won
            actual_temp: Actual temperature (if known)
            resolution_time: When market resolved
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        resolution_time = resolution_time or datetime.utcnow()

        try:
            cursor.execute('''
                UPDATE market_snapshots
                SET resolved = 1,
                    resolution_time = ?,
                    yes_won = ?,
                    actual_temp = ?
                WHERE market_id = ?
            ''', (
                resolution_time.isoformat(),
                yes_won,
                actual_temp,
                market_id,
            ))
            conn.commit()
        finally:
            conn.close()

    def get_snapshots_for_backtest(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        resolved_only: bool = True,
        platform: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get market snapshots for backtesting.

        Args:
            start_date: Start of date range
            end_date: End of date range
            resolved_only: Only include resolved markets
            platform: Filter by platform

        Returns:
            List of snapshot dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM market_snapshots WHERE 1=1"
        params = []

        if resolved_only:
            query += " AND resolved = 1"
        if start_date:
            query += " AND snapshot_time >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND snapshot_time <= ?"
            params.append(end_date.isoformat())
        if platform:
            query += " AND platform = ?"
            params.append(platform)

        query += " ORDER BY snapshot_time"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def save_backtest_run(
        self,
        run_name: str,
        params: Dict[str, Any],
        results: Dict[str, Any],
    ) -> int:
        """Save backtest results for later comparison.

        Args:
            run_name: Name for this backtest run
            params: Strategy parameters used
            results: Backtest results

        Returns:
            Run ID
        """
        import json

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO backtest_runs (
                    run_name, params_json,
                    total_trades, wins, losses, win_rate,
                    total_pnl, total_invested, roi,
                    results_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                run_name,
                json.dumps(params),
                results.get("total_trades", 0),
                results.get("wins", 0),
                results.get("losses", 0),
                results.get("win_rate", 0),
                results.get("total_pnl", 0),
                results.get("total_invested", 0),
                results.get("roi", 0),
                json.dumps(results),
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_backtest_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent backtest runs for comparison.

        Args:
            limit: Max runs to return

        Returns:
            List of backtest run dictionaries
        """
        import json

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM backtest_runs
            ORDER BY run_time DESC
            LIMIT ?
        ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            d = dict(row)
            d["params"] = json.loads(d.pop("params_json", "{}"))
            d["results"] = json.loads(d.pop("results_json", "{}"))
            results.append(d)

        return results

    def import_from_trades_db(self, trades_db_path: str = "data/trades.db"):
        """Import historical trades into backtest database.

        This allows backtesting against past trading activity.

        Args:
            trades_db_path: Path to trades database
        """
        trades_conn = sqlite3.connect(trades_db_path)
        trades_conn.row_factory = sqlite3.Row
        trades_cursor = trades_conn.cursor()

        trades_cursor.execute('''
            SELECT * FROM trades WHERE resolved = 1
        ''')
        trades = trades_cursor.fetchall()
        trades_conn.close()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        imported = 0
        for trade in trades:
            # Parse market type from market_id
            market_id = trade["market_id"]
            is_range = "-B" in market_id
            is_threshold = "-T" in market_id

            # Determine if YES won based on trade outcome
            token_id = trade["token_id"] or ""
            is_yes_trade = "_YES" in token_id
            trade_won = trade["won"]

            # If we bought YES and won, YES won. If we bought NO and won, NO won (YES lost).
            yes_won = trade_won if is_yes_trade else not trade_won

            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO market_snapshots (
                        snapshot_time, platform, market_id, question,
                        yes_price, no_price, is_range,
                        fair_probability, edge,
                        resolved, yes_won
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ''', (
                    trade["timestamp"],
                    trade["platform"],
                    market_id,
                    trade["question"],
                    trade["price"] if is_yes_trade else 1 - trade["price"],
                    1 - trade["price"] if is_yes_trade else trade["price"],
                    is_range,
                    trade["fair_probability"],
                    trade["edge"],
                    yes_won,
                ))
                imported += 1
            except Exception as e:
                self.logger.debug(f"Skip importing {market_id}: {e}")

        conn.commit()
        conn.close()
        self.logger.info(f"Imported {imported} trades into backtest database")
        return imported
