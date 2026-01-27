#!/usr/bin/env python3
"""Check for duplicate trades in the most recent scan."""

import sqlite3
import os
import sys
from datetime import datetime, timedelta
from collections import Counter

def main():
    # Try to find database
    possible_paths = [
        "data/trades.db",
        "./data/trades.db",
        "/root/trading-bots/polymarket-weather-bot/data/trades.db",
    ]

    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break

    if not db_path:
        print("❌ Database not found")
        sys.exit(1)

    print(f"✓ Found database at: {db_path}\n")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get trades from the last 30 minutes (latest scan)
    thirty_mins_ago = (datetime.now() - timedelta(minutes=30)).isoformat()

    cursor.execute("""
        SELECT market_id, question, created_at, COUNT(*) as count
        FROM trades
        WHERE simulation=1
        AND created_at > ?
        GROUP BY market_id
        ORDER BY count DESC, created_at DESC
    """, (thirty_mins_ago,))

    trades = cursor.fetchall()

    print("="*80)
    print(f"TRADES FROM LATEST SCAN (last 30 minutes)")
    print("="*80)
    print(f"\nTotal unique markets: {len(trades)}")

    duplicates = [t for t in trades if t[3] > 1]
    if duplicates:
        print(f"\n⚠️  DUPLICATES FOUND:")
        for market_id, question, created_at, count in duplicates:
            print(f"  {market_id}: {count} trades")
            print(f"    Question: {question[:60]}...")
            print(f"    Created: {created_at}")
    else:
        print("\n✅ No duplicates in latest scan")

    print(f"\n{'='*80}")
    print("All trades in latest scan:")
    print(f"{'='*80}\n")

    for market_id, question, created_at, count in trades:
        dup_marker = " ⚠️ DUPLICATE" if count > 1 else ""
        print(f"{market_id}{dup_marker}")

    print(f"\nTotal: {len(trades)} unique markets, {sum(t[3] for t in trades)} total trades")

    conn.close()

if __name__ == "__main__":
    main()
