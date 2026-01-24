"""Debug script to check Kalshi settlements API and verify resolution matching."""

import sqlite3
from datetime import datetime, timezone, timedelta
from bot.connectors.kalshi import KalshiClient
from bot.utils.config import get_config

def main():
    print("=" * 80)
    print("SETTLEMENTS API DEBUG")
    print("=" * 80)

    # Initialize Kalshi client
    config = get_config()
    client = KalshiClient(config)

    # Get settlements from Kalshi
    print("\n1. Fetching settlements from Kalshi API...")
    print("-" * 80)

    # Try different time ranges
    now = int(datetime.now(timezone.utc).timestamp())
    yesterday = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
    two_days_ago = int((datetime.now(timezone.utc) - timedelta(days=2)).timestamp())

    print(f"Current timestamp: {now}")
    print(f"Yesterday: {yesterday}")
    print(f"Two days ago: {two_days_ago}")
    print()

    # Fetch settlements
    settlements_all = client.get_settlements(limit=200)
    settlements_recent = client.get_settlements(limit=200, min_ts=yesterday)

    print(f"Total settlements (all time, limit 200): {len(settlements_all)}")
    print(f"Recent settlements (last 24h): {len(settlements_recent)}")
    print()

    if settlements_all:
        print("Sample settlement structure:")
        print(f"  Keys: {settlements_all[0].keys()}")
        print(f"  Sample: {settlements_all[0]}")
        print()

        print("All settlement tickers:")
        for s in settlements_all[:20]:  # Show first 20
            print(f"  - {s['ticker']}: result={s.get('market_result')} settled={s.get('settled_time')}")
        if len(settlements_all) > 20:
            print(f"  ... and {len(settlements_all) - 20} more")
    else:
        print("⚠️  NO SETTLEMENTS FOUND!")
        print("This means either:")
        print("  1. No markets have settled yet")
        print("  2. API authentication issue")
        print("  3. Account has no trading history")

    print()
    print("-" * 80)

    # Get open trades from database
    print("\n2. Checking open trades from database...")
    print("-" * 80)

    conn = sqlite3.connect('data/trades.db')
    cursor = conn.execute("""
        SELECT trade_id, market_id, token_id, timestamp, cost
        FROM trades
        WHERE simulation=1 AND resolved=0
        ORDER BY timestamp DESC
        LIMIT 10
    """)

    open_trades = cursor.fetchall()
    conn.close()

    print(f"Open trades in database: {len(open_trades)}")
    print()

    if open_trades:
        print("Sample open trades:")
        for trade_id, market_id, token_id, timestamp, cost in open_trades:
            print(f"  - {market_id} ({token_id}) - ${cost}")

    print()
    print("-" * 80)

    # Check for matches
    print("\n3. Checking for ticker matches...")
    print("-" * 80)

    if settlements_all and open_trades:
        settlement_tickers = {s['ticker'] for s in settlements_all}
        trade_tickers = {t[1] for t in open_trades}  # market_id is index 1

        matches = settlement_tickers & trade_tickers
        in_settlements_not_trades = settlement_tickers - trade_tickers
        in_trades_not_settlements = trade_tickers - settlement_tickers

        print(f"Tickers in settlements: {len(settlement_tickers)}")
        print(f"Tickers in open trades: {len(trade_tickers)}")
        print(f"MATCHES: {len(matches)}")
        print()

        if matches:
            print("✅ MATCHING TICKERS FOUND:")
            for ticker in list(matches)[:10]:
                settlement = next(s for s in settlements_all if s['ticker'] == ticker)
                trade = next(t for t in open_trades if t[1] == ticker)
                print(f"  - {ticker}")
                print(f"    Settlement result: {settlement.get('market_result')}")
                print(f"    Trade token: {trade[2]}")  # token_id
                print(f"    Settled time: {settlement.get('settled_time')}")
        else:
            print("❌ NO MATCHES FOUND")
            print()
            print("Sample settlement tickers:")
            for ticker in list(settlement_tickers)[:5]:
                print(f"  - {ticker}")
            print()
            print("Sample trade tickers:")
            for ticker in list(trade_tickers)[:5]:
                print(f"  - {ticker}")

    print()
    print("-" * 80)

    # Check if bot is in simulation mode
    print("\n4. Checking simulation mode...")
    print("-" * 80)

    conn = sqlite3.connect('data/trades.db')
    cursor = conn.execute("SELECT simulation, COUNT(*) FROM trades GROUP BY simulation")
    for simulation, count in cursor.fetchall():
        mode = "SIMULATION" if simulation == 1 else "LIVE"
        print(f"  {mode}: {count} trades")
    conn.close()

    print()
    print("=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)
    print()
    print("INTERPRETATION:")
    print("- If settlements list is empty: Markets haven't settled yet OR API issue")
    print("- If no matches found: Ticker format mismatch OR wrong trades in database")
    print("- If matches found: Resolution checker should be working - check bot logs")

if __name__ == "__main__":
    main()
