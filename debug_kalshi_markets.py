#!/usr/bin/env python3
"""Debug script to see what markets Kalshi API returns."""

from bot.connectors.kalshi import KalshiClient
from bot.utils.config import Config

config = Config()
client = KalshiClient(config)

# Try specific series with city codes (pattern: KXHIGH{CITY}, KXLOW{CITY})
print("Testing series tickers with city codes...")
test_series = ["KXHIGHTSEA", "KXLOWTSEA", "KXHIGHTNYC", "KXLOWTNYC", "KXHIGHTSFO", "KXLOWTSFO"]

for series in test_series:
    response = client._make_request("GET", "/markets", params={"series_ticker": series, "limit": 10})
    if response and response.status_code == 200:
        data = response.json()
        markets = data.get("markets", [])
        if markets:
            print(f"\n✓ Found {len(markets)} markets for series: {series}")
            for m in markets[:3]:
                print(f"  - {m.get('ticker')}: {m.get('title', '')[:100]}")
                print(f"    Status: {m.get('status')}")

print("\n" + "="*80)
print("Searching first 2000 markets by ticker pattern...")
response = client._make_request("GET", "/markets", params={"limit": 2000})

if response and response.status_code == 200:
    data = response.json()
    markets = data.get("markets", [])

    # Look for ticker patterns with city codes
    temp_tickers = [m for m in markets if m.get("ticker", "").upper().startswith(("KXHIGHT", "KXLOWT"))]
    print(f"Found {len(temp_tickers)} markets with KXHIGHT*/KXLOWT* ticker prefix")

    for i, m in enumerate(temp_tickers[:10], 1):
        print(f"\n{i}. {m.get('ticker')}")
        print(f"   {m.get('title', '')[:100]}")
        print(f"   Status: {m.get('status')}")
else:
    print(f"Failed: {response.status_code if response else 'No response'}")
