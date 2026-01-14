#!/usr/bin/env python3
"""Debug script to see what markets Kalshi API returns."""

from bot.connectors.kalshi import KalshiClient
from bot.utils.config import Config

config = Config()
client = KalshiClient(config)

print("1. Trying category=climate filter...")
response = client._make_request("GET", "/markets", params={"limit": 100, "status": "open", "category": "climate"})

if response and response.status_code == 200:
    data = response.json()
    markets = data.get("markets", [])
    print(f"Found {len(markets)} climate markets")

    for i, market in enumerate(markets[:5], 1):
        print(f"\n{i}. {market.get('ticker', 'N/A')}")
        print(f"   {market.get('title', 'N/A')[:100]}")
else:
    print(f"Failed: {response.status_code if response else 'No response'}")

print("\n" + "="*80)
print("2. Searching 500 markets for 'temperature' keyword...")
response = client._make_request("GET", "/markets", params={"limit": 500, "status": "open"})

if response and response.status_code == 200:
    data = response.json()
    markets = data.get("markets", [])

    temp_markets = [m for m in markets if "temp" in m.get("title", "").lower() or "temperature" in m.get("title", "").lower()]
    print(f"Found {len(temp_markets)} temperature markets out of {len(markets)} total")

    for i, market in enumerate(temp_markets[:5], 1):
        print(f"\n{i}. {market.get('ticker', 'N/A')}")
        print(f"   {market.get('title', 'N/A')[:100]}")
        print(f"   Series: {market.get('series_ticker', 'N/A')}")
else:
    print(f"Failed: {response.status_code if response else 'No response'}")
