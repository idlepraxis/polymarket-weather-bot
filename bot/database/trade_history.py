"""SQLite database for trade history and P&L tracking."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from bot.utils.models import Trade
from bot.utils.logger import setup_logger


class TradeHistoryDB:
    """SQLite database for storing and querying trade history."""

    def __init__(self, db_path: str = "./data/trades.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.logger = setup_logger(__name__)

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Create trades table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,

                    -- Platform
                    platform TEXT NOT NULL,

                    -- Market info
                    market_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    token_id TEXT NOT NULL,

                    -- Trade details
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    cost REAL NOT NULL,

                    -- Status
                    simulation INTEGER NOT NULL,
                    tx_hash TEXT,
                    status TEXT NOT NULL,

                    -- Analysis
                    fair_probability REAL NOT NULL,
                    edge REAL NOT NULL,
                    reasoning TEXT NOT NULL,

                    -- Resolution (populated when market resolves)
                    resolved INTEGER DEFAULT 0,
                    resolution_date TEXT,
                    won INTEGER,
                    pnl REAL,

                    -- Metadata
                    created_at TEXT NOT NULL
                )
            """)

            # Create indices for common queries
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON trades(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_simulation ON trades(simulation)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_platform ON trades(platform)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resolved ON trades(resolved)"
            )

            conn.commit()

        self.logger.info(f"Trade history database initialized at {self.db_path}")

    def log_trade(
        self,
        trade: Trade,
        platform: str,
    ) -> bool:
        """Log a trade to the database.

        Args:
            trade: Trade object to log
            platform: Platform name (polymarket, kalshi)

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO trades (
                        trade_id, timestamp, platform,
                        market_id, question, token_id,
                        side, price, size, cost,
                        simulation, tx_hash, status,
                        fair_probability, edge, reasoning,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trade_id,
                    trade.timestamp.isoformat(),
                    platform.lower(),
                    trade.market_id,
                    trade.question,
                    trade.token_id,
                    trade.side,
                    trade.price,
                    trade.size,
                    trade.cost,
                    1 if trade.simulation else 0,
                    trade.tx_hash,
                    trade.status,
                    trade.fair_probability,
                    trade.edge,
                    trade.reasoning,
                    datetime.now(timezone.utc).isoformat()
                ))
                conn.commit()

            mode = "SIMULATION" if trade.simulation else "LIVE"
            self.logger.info(
                f"Logged {mode} trade {trade.trade_id} to database "
                f"({platform}, {trade.side}, {trade.size:.2f} USDC)"
            )
            return True

        except sqlite3.IntegrityError as e:
            self.logger.warning(f"Trade {trade.trade_id} already exists in database")
            return False
        except Exception as e:
            self.logger.error(f"Failed to log trade: {e}")
            return False

    def get_trades(
        self,
        simulation: Optional[bool] = None,
        platform: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get trades from database.

        Args:
            simulation: Filter by simulation mode (None = all trades)
            platform: Filter by platform (None = all platforms)
            limit: Maximum number of trades to return

        Returns:
            List of trade dictionaries
        """
        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if simulation is not None:
            query += " AND simulation = ?"
            params.append(1 if simulation else 0)

        if platform:
            query += " AND platform = ?"
            params.append(platform.lower())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_pnl_summary(
        self,
        simulation: Optional[bool] = None,
        platform: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate P&L summary statistics.

        Args:
            simulation: Filter by simulation mode (None = all trades)
            platform: Filter by platform (None = all platforms)

        Returns:
            Dictionary with P&L statistics
        """
        query = """
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN won = 1 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN won = 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(CASE WHEN resolved = 1 THEN pnl ELSE 0 END) as realized_pnl,
                SUM(cost) as total_invested,
                AVG(CASE WHEN resolved = 1 THEN pnl END) as avg_pnl_per_trade,
                MAX(CASE WHEN resolved = 1 THEN pnl END) as best_trade,
                MIN(CASE WHEN resolved = 1 THEN pnl END) as worst_trade,
                AVG(price) as avg_entry_price,
                AVG(edge) as avg_edge
            FROM trades
            WHERE 1=1
        """
        params = []

        if simulation is not None:
            query += " AND simulation = ?"
            params.append(1 if simulation else 0)

        if platform:
            query += " AND platform = ?"
            params.append(platform.lower())

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            result = dict(cursor.fetchone())

        # Calculate win rate
        total = result['total_trades'] or 0
        wins = result['winning_trades'] or 0
        win_rate = (wins / total * 100) if total > 0 else 0.0

        # Calculate ROI
        invested = result['total_invested'] or 0
        realized = result['realized_pnl'] or 0
        roi = (realized / invested * 100) if invested > 0 else 0.0

        return {
            'total_trades': total,
            'winning_trades': wins,
            'losing_trades': result['losing_trades'] or 0,
            'win_rate': win_rate,
            'realized_pnl': realized,
            'total_invested': invested,
            'roi': roi,
            'avg_pnl_per_trade': result['avg_pnl_per_trade'] or 0.0,
            'best_trade': result['best_trade'] or 0.0,
            'worst_trade': result['worst_trade'] or 0.0,
            'avg_entry_price': result['avg_entry_price'] or 0.0,
            'avg_edge': result['avg_edge'] or 0.0,
        }

    def update_resolution(
        self,
        trade_id: str,
        won: bool,
        pnl: float,
        resolution_date: Optional[datetime] = None
    ) -> bool:
        """Update trade with resolution outcome.

        Args:
            trade_id: Trade ID to update
            won: Whether the trade won
            pnl: Profit/loss amount
            resolution_date: When market resolved (default: now)

        Returns:
            True if successful, False otherwise
        """
        if resolution_date is None:
            resolution_date = datetime.now(timezone.utc)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE trades
                    SET resolved = 1,
                        won = ?,
                        pnl = ?,
                        resolution_date = ?
                    WHERE trade_id = ?
                """, (
                    1 if won else 0,
                    pnl,
                    resolution_date.isoformat(),
                    trade_id
                ))
                conn.commit()

            self.logger.info(
                f"Updated trade {trade_id} resolution: "
                f"{'WON' if won else 'LOST'}, P&L: ${pnl:.2f}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to update trade resolution: {e}")
            return False

    def get_open_trades(
        self,
        simulation: Optional[bool] = None,
        platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get trades that haven't resolved yet.

        Args:
            simulation: Filter by simulation mode (None = all trades)
            platform: Filter by platform (None = all platforms)

        Returns:
            List of open trade dictionaries
        """
        query = "SELECT * FROM trades WHERE resolved = 0"
        params = []

        if simulation is not None:
            query += " AND simulation = ?"
            params.append(1 if simulation else 0)

        if platform:
            query += " AND platform = ?"
            params.append(platform.lower())

        query += " ORDER BY timestamp DESC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_open_market_ids(
        self,
        simulation: Optional[bool] = None,
        platform: Optional[str] = None
    ) -> set:
        """Get set of market IDs that have open (unresolved) positions.

        This is used to prevent duplicate trades on the same market.

        Args:
            simulation: Filter by simulation mode (None = all trades)
            platform: Filter by platform (None = all platforms)

        Returns:
            Set of market IDs with open positions
        """
        query = "SELECT DISTINCT market_id FROM trades WHERE resolved = 0"
        params = []

        if simulation is not None:
            query += " AND simulation = ?"
            params.append(1 if simulation else 0)

        if platform:
            query += " AND platform = ?"
            params.append(platform.lower())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return {row[0] for row in cursor.fetchall()}

    def get_stats_by_platform(self, simulation: Optional[bool] = None) -> Dict[str, Dict[str, Any]]:
        """Get P&L statistics grouped by platform.

        Args:
            simulation: Filter by simulation mode (None = all trades)

        Returns:
            Dictionary mapping platform name to stats
        """
        stats = {}
        platforms = ["polymarket", "kalshi"]

        for platform in platforms:
            platform_stats = self.get_pnl_summary(simulation=simulation, platform=platform)
            if platform_stats['total_trades'] > 0:
                stats[platform] = platform_stats

        return stats
