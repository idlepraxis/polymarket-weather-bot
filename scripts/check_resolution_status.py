"""Quick check of resolution status - minimal dependencies."""

import sys
import os

# Try to find the database
possible_db_paths = [
    'data/trades.db',
    '/root/trading-bots/polymarket-weather-bot/data/trades.db',
    '../data/trades.db',
]

db_path = None
for path in possible_db_paths:
    if os.path.exists(path):
        db_path = path
        break

if not db_path:
    print("❌ Could not find trades.db")
    print(f"Searched: {possible_db_paths}")
    print(f"Current directory: {os.getcwd()}")
    sys.exit(1)

print(f"✅ Found database at: {db_path}")
print()

try:
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check open simulation trades
    cursor.execute("""
        SELECT COUNT(*) FROM trades
        WHERE simulation=1 AND resolved=0
    """)
    open_count = cursor.fetchone()[0]

    # Check resolved simulation trades
    cursor.execute("""
        SELECT COUNT(*) FROM trades
        WHERE simulation=1 AND resolved=1
    """)
    resolved_count = cursor.fetchone()[0]

    # Get sample open trades
    cursor.execute("""
        SELECT market_id, timestamp
        FROM trades
        WHERE simulation=1 AND resolved=0
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    open_trades = cursor.fetchall()

    # Get sample resolved trades (if any)
    cursor.execute("""
        SELECT market_id, timestamp, won, pnl
        FROM trades
        WHERE simulation=1 AND resolved=1
        ORDER BY resolution_date DESC
        LIMIT 5
    """)
    resolved_trades = cursor.fetchall()

    conn.close()

    print("=" * 80)
    print("TRADE RESOLUTION STATUS")
    print("=" * 80)
    print()
    print(f"📊 Open simulation trades: {open_count}")
    print(f"✅ Resolved simulation trades: {resolved_count}")
    print()

    if open_trades:
        print("Sample open trades:")
        for trade in open_trades:
            market_id, timestamp = trade
            print(f"  - {market_id} (placed: {timestamp})")
        print()

    if resolved_trades:
        print("Sample resolved trades:")
        for trade in resolved_trades:
            market_id, timestamp, won, pnl = trade
            result = "WON" if won else "LOST"
            print(f"  - {market_id}: {result} (P&L: ${pnl:+.2f})")
        print()
    else:
        print("❌ No resolved trades yet")
        print()

    # Extract dates from open trades
    if open_trades:
        print("Trade dates found:")
        dates_seen = set()
        for trade in open_trades:
            market_id = trade[0]
            # Extract date from ticker (e.g., KXLOWTLAX-26JAN24-B47.5)
            parts = market_id.split('-')
            if len(parts) >= 2:
                date_part = parts[1]
                dates_seen.add(date_part)

        for date in sorted(dates_seen):
            print(f"  - {date}")
        print()

    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Check if your Jan 24 markets have finalized on Kalshi website")
    print("2. Run: python scripts/check_simulation_resolution.py")
    print("3. Check bot logs: tail -f logs/bot.log")
    print("4. Manually trigger resolution check if needed")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
