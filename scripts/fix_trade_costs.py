#!/usr/bin/env python3
"""Fix incorrect cost calculations in trade history database.

The bot was incorrectly calculating cost as (size * price) instead of just size.
This script updates all trades to have the correct cost = size.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.utils.logger import get_logger

logger = get_logger()

def fix_trade_costs(db_path: str = "data/trades.db"):
    """Fix trade costs in the database."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get all trades with incorrect costs (where cost != size)
        cursor.execute("""
            SELECT trade_id, market_id, size, price, cost
            FROM trades
            WHERE cost != size
            ORDER BY timestamp
        """)

        trades = cursor.fetchall()

        if not trades:
            logger.info("No trades need fixing. All costs are correct.")
            return

        logger.info(f"Found {len(trades)} trades with incorrect costs")

        # Show before/after for first few trades
        logger.info("\nExample corrections:")
        for trade in trades[:5]:
            trade_id, market_id, size, price, old_cost = trade
            logger.info(f"  Trade {trade_id[:8]}... - Size: ${size:.2f}, Price: {price:.1%}")
            logger.info(f"    Before: cost = ${old_cost:.2f} (WRONG: size * price)")
            logger.info(f"    After:  cost = ${size:.2f} (CORRECT: just size)")

        if len(trades) > 5:
            logger.info(f"  ... and {len(trades) - 5} more trades")

        # Update all trades: set cost = size
        cursor.execute("""
            UPDATE trades
            SET cost = size
            WHERE cost != size
        """)

        conn.commit()

        logger.info(f"\n✅ Successfully fixed {len(trades)} trades")

        # Show summary
        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(size) as total_invested,
                AVG(size) as avg_size,
                AVG(price) as avg_price
            FROM trades
            WHERE status != 'cancelled'
        """)

        stats = cursor.fetchone()
        logger.info("\nUpdated Database Summary:")
        logger.info(f"  Total Trades: {stats[0]}")
        logger.info(f"  Total Invested: ${stats[1]:.2f}")
        logger.info(f"  Avg Trade Size: ${stats[2]:.2f}")
        logger.info(f"  Avg Entry Price: {stats[3]:.1%}")

    except Exception as e:
        logger.error(f"Error fixing trade costs: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fix incorrect trade costs in database")
    parser.add_argument("--db", default="data/trades.db", help="Path to database file")
    args = parser.parse_args()

    fix_trade_costs(args.db)
