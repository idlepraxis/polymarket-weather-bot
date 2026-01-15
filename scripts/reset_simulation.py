#!/usr/bin/env python3
"""Reset simulation - clear all trades and start fresh.

Use this when you want to restart the simulation with new parameters.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.utils.logger import get_logger

logger = get_logger()

def reset_simulation(db_path: str = "data/trades.db", confirm: bool = False):
    """Delete all simulation trades from the database."""

    if not Path(db_path).exists():
        logger.info(f"Database {db_path} doesn't exist yet. Nothing to reset.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Count simulation trades
        cursor.execute("""
            SELECT COUNT(*) FROM trades WHERE simulation = 1
        """)
        count = cursor.fetchone()[0]

        if count == 0:
            logger.info("No simulation trades found. Nothing to reset.")
            return

        logger.info(f"Found {count} simulation trades")

        if not confirm:
            logger.warning("\n⚠️  This will DELETE all simulation trades!")
            logger.warning("   Run with --confirm to proceed")
            return

        # Delete all simulation trades
        cursor.execute("""
            DELETE FROM trades WHERE simulation = 1
        """)

        conn.commit()

        logger.info(f"✅ Successfully deleted {count} simulation trades")
        logger.info("\nYou can now start a fresh simulation with:")
        logger.info("  python bot.py bot-start --simulation --platform kalshi")

    except Exception as e:
        logger.error(f"Error resetting simulation: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Reset simulation trades")
    parser.add_argument("--db", default="data/trades.db", help="Path to database file")
    parser.add_argument("--confirm", action="store_true", help="Confirm deletion")
    args = parser.parse_args()

    reset_simulation(args.db, args.confirm)
