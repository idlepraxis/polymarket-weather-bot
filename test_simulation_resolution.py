"""Test script to verify simulation mode resolution checking works."""

import sqlite3
from datetime import datetime, timezone
from bot.connectors.kalshi import KalshiClient
from bot.utils.config import get_config

def main():
    print("=" * 80)
    print("SIMULATION MODE RESOLUTION CHECKER TEST")
    print("=" * 80)

    # Initialize Kalshi client
    config = get_config()
    client = KalshiClient(config)

    # Get open simulation trades from database
    print("\n1. Fetching open simulation trades from database...")
    print("-" * 80)

    conn = sqlite3.connect('data/trades.db')
    cursor = conn.execute("""
        SELECT trade_id, market_id, token_id, timestamp, cost
        FROM trades
        WHERE simulation=1 AND resolved=0
        ORDER BY timestamp DESC
        LIMIT 20
    """)

    open_trades = cursor.fetchall()
    conn.close()

    print(f"Open simulation trades: {len(open_trades)}")
    print()

    if not open_trades:
        print("No open simulation trades found. Nothing to test.")
        return

    # Extract unique series tickers
    print("\n2. Extracting series tickers from trades...")
    print("-" * 80)

    series_set = set()
    trade_map = {}  # ticker -> trade info

    for trade_id, market_id, token_id, timestamp, cost in open_trades:
        # Extract series ticker (part before hyphen)
        if '-' in market_id:
            series = market_id.split('-')[0]
            series_set.add(series)
        trade_map[market_id] = {
            'trade_id': trade_id,
            'token_id': token_id,
            'timestamp': timestamp,
            'cost': cost
        }

    series_list = sorted(series_set)
    print(f"Unique series: {len(series_list)}")
    print(f"Series list: {series_list[:10]}")
    if len(series_list) > 10:
        print(f"  ... and {len(series_list) - 10} more")
    print()

    # Query finalized markets for these series
    print("\n3. Querying finalized markets from Kalshi API...")
    print("-" * 80)

    finalized_markets = client.get_finalized_markets_by_series(series_list)

    print(f"Finalized markets found: {len(finalized_markets)}")
    print()

    if finalized_markets:
        print("Sample finalized markets:")
        for market in finalized_markets[:10]:
            ticker = market.get('ticker')
            result = market.get('result')
            status = market.get('status')
            print(f"  - {ticker}: status={status}, result={result}")
        if len(finalized_markets) > 10:
            print(f"  ... and {len(finalized_markets) - 10} more")
    else:
        print("⚠️  NO FINALIZED MARKETS FOUND!")
        print("This could mean:")
        print("  1. None of your simulation trades have resolved yet")
        print("  2. Markets resolved but haven't reached 'finalized' status")
        print("  3. API query issue")

    print()
    print("-" * 80)

    # Check for matches
    print("\n4. Matching finalized markets to open trades...")
    print("-" * 80)

    finalized_map = {m['ticker']: m for m in finalized_markets}

    matches = []
    for ticker in trade_map.keys():
        if ticker in finalized_map:
            matches.append({
                'ticker': ticker,
                'trade': trade_map[ticker],
                'market': finalized_map[ticker]
            })

    print(f"Matches found: {len(matches)}")
    print()

    if matches:
        print("✅ MATCHING RESOLUTIONS FOUND:")
        for match in matches:
            ticker = match['ticker']
            trade = match['trade']
            market = match['market']

            market_result = market.get('result', '').lower()
            token_id = trade['token_id']

            # Determine if trade won
            if 'yes' in token_id.lower():
                won = market_result == 'yes'
            else:
                won = market_result == 'no'

            print(f"\n  Ticker: {ticker}")
            print(f"    Trade token: {token_id}")
            print(f"    Market result: {market_result}")
            print(f"    Trade outcome: {'WON' if won else 'LOST'}")
            print(f"    Cost: ${trade['cost']}")

            # Calculate P&L (simplified - assumes $1 payout for wins)
            if won:
                pnl = 1.0 - trade['cost']
            else:
                pnl = -trade['cost']
            print(f"    P&L: ${pnl:+.2f}")
    else:
        print("❌ NO MATCHES FOUND")
        print()
        print("Sample trade tickers:")
        for ticker in list(trade_map.keys())[:5]:
            print(f"  - {ticker}")
        print()
        print("Sample finalized tickers:")
        for ticker in list(finalized_map.keys())[:5]:
            print(f"  - {ticker}")

    print()
    print("-" * 80)
    print("\n5. Summary...")
    print("-" * 80)
    print(f"Open simulation trades: {len(open_trades)}")
    print(f"Series queried: {len(series_list)}")
    print(f"Finalized markets found: {len(finalized_markets)}")
    print(f"Matches (resolvable trades): {len(matches)}")
    print()

    if matches:
        print("✅ SUCCESS: The new resolution checker should work!")
        print(f"   It will resolve {len(matches)} trade(s) on the next check.")
    else:
        print("ℹ️  No matches found yet.")
        print("   This is normal if markets haven't resolved yet.")
        print("   The resolution checker will find them once markets finalize.")

    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
