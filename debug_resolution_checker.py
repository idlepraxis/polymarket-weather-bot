"""Debug script to check why resolution checker isn't finding resolved markets."""

import sqlite3
from datetime import datetime, timezone
from bot.connectors.kalshi import KalshiClient
from bot.utils.config import get_config

def main():
    print("=" * 80)
    print("RESOLUTION CHECKER DEBUG")
    print("=" * 80)

    # Initialize Kalshi client
    config = get_config()
    client = KalshiClient(config)

    # Get 5 random open trades from database
    conn = sqlite3.connect('data/trades.db')
    cursor = conn.execute("""
        SELECT trade_id, market_id, question, token_id, timestamp
        FROM trades
        WHERE simulation=1 AND resolved=0
        ORDER BY timestamp DESC
        LIMIT 5
    """)

    trades = cursor.fetchall()
    conn.close()

    if not trades:
        print("No open trades found!")
        return

    print(f"\nFound {len(trades)} open trades to check\n")

    for trade_id, market_id, question, token_id, timestamp in trades:
        print("-" * 80)
        print(f"Trade ID: {trade_id}")
        print(f"Market ID: {market_id}")
        print(f"Question: {question[:60]}...")
        print(f"Token: {token_id}")
        print(f"Placed: {timestamp}")
        print()

        # Query Kalshi API for market status
        try:
            url = f"{client.api_base}/markets/{market_id}"
            response = client._make_request("GET", url)

            print(f"API Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                if 'market' in data:
                    market = data['market']
                    status = market.get('status', 'UNKNOWN')
                    result = market.get('result', 'UNKNOWN')
                    close_time = market.get('close_time', 'UNKNOWN')
                    expiration_time = market.get('expiration_time', 'UNKNOWN')

                    print(f"✓ Market Status: {status}")
                    print(f"  Result: {result}")
                    print(f"  Close Time: {close_time}")
                    print(f"  Expiration Time: {expiration_time}")

                    # Check if it should be resolved
                    is_resolved = status == 'finalized'
                    print(f"  Is Resolved? {is_resolved}")

                    if is_resolved:
                        print(f"  🎉 MARKET IS FINALIZED!")
                        print(f"  Outcome: {result}")
                        # Check if token matches
                        if 'yes' in token_id.lower():
                            won = result == 'yes'
                        else:
                            won = result == 'no'
                        print(f"  Trade would be: {'WON' if won else 'LOST'}")
                    else:
                        print(f"  ⏳ Market not finalized yet (status={status})")
                else:
                    print("ERROR: No 'market' key in response")
                    print(f"Response keys: {data.keys()}")
                    print(f"Full response: {data}")
            else:
                print(f"ERROR: API returned {response.status_code}")
                print(f"Response: {response.text[:500]}")

        except Exception as e:
            print(f"ERROR querying market: {e}")
            import traceback
            traceback.print_exc()

        print()

    print("=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
