#!/usr/bin/env python3
"""Debug script to see what markets Kalshi API returns."""

from bot.connectors.kalshi import KalshiClient
from bot.utils.config import Config
import json

config = Config()
client = KalshiClient(config)

print("Fetching 20 open markets...")
response = client._make_request("GET", "/markets", params={"limit": 20, "status": "open"})

if response and response.status_code == 200:
    data = response.json()
    markets = data.get("markets", [])

    print(f"\nFound {len(markets)} markets")
    print("\n" + "="*80)

    for i, market in enumerate(markets[:10], 1):
        print(f"\n{i}. Ticker: {market.get('ticker', 'N/A')}")
        print(f"   Title: {market.get('title', 'N/A')}")
        print(f"   Category: {market.get('category', 'N/A')}")
        print(f"   Series: {market.get('series_ticker', 'N/A')}")

else:
    print(f"Error: {response.status_code if response else 'No response'}")
    if response:
        print(response.text[:500])
