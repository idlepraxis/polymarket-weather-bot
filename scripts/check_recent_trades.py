#!/usr/bin/env python3
"""Check recent trades for duplicates and missing location info."""

import sqlite3
import os
import sys
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

def main():
    # Try multiple possible database locations
    possible_paths = [
        "data/trades.db",
        "./data/trades.db",
        os.path.expanduser("~/trading-bots/polymarket-weather-bot/data/trades.db"),
        "/root/trading-bots/polymarket-weather-bot/data/trades.db",
        "/home/user/polymarket-weather-bot/data/trades.db",
    ]

    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break

    if not db_path:
        print("❌ Database not found. Checked locations:")
        for path in possible_paths:
            print(f"  - {path}")
        print("\nThe bot may not have created the database yet.")
        print("Try running: python bot.py status")
        sys.exit(1)

    print(f"✓ Found database at: {db_path}\n")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get trades from the last hour
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

        cursor.execute("""
            SELECT trade_id, market_id, question, token_id, created_at
            FROM trades
            WHERE simulation = 1
            AND created_at > ?
            ORDER BY created_at DESC
        """, (one_hour_ago,))

        trades = cursor.fetchall()

        if not trades:
            print("No trades found in the last hour")
            return

        print(f"\n{'='*80}")
        print(f"Found {len(trades)} trades in the last hour")
        print(f"{'='*80}\n")

        # Check for duplicate market_ids
        market_ids = [t[1] for t in trades]
        market_counts = Counter(market_ids)
        duplicates = {mid: count for mid, count in market_counts.items() if count > 1}

        if duplicates:
            print(f"⚠️  DUPLICATE MARKETS DETECTED:")
            for market_id, count in duplicates.items():
                print(f"  - {market_id}: {count} trades")
            print()
        else:
            print("✓ No duplicate markets found")
            print()

        # Show all trades with their full info
        print(f"\n{'='*80}")
        print("Recent Trades:")
        print(f"{'='*80}\n")

        for trade_id, market_id, question, token_id, created_at in trades[:10]:
            print(f"Market ID: {market_id}")
            print(f"Question:  {question}")
            print(f"Token:     {token_id}")
            print(f"Created:   {created_at}")
            print(f"{'-'*80}")

        conn.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
