#!/usr/bin/env python3
"""Check what Kalshi API returns for market questions."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.connectors.kalshi import KalshiClient
from bot.utils.logger import get_logger

def main():
    logger = get_logger()

    # Initialize client (will use API key from environment)
    client = KalshiClient()

    print("\n" + "="*80)
    print("Fetching weather markets from Kalshi API")
    print("="*80 + "\n")

    # Get weather markets
    raw_markets = client.get_weather_markets_direct(limit=5)

    if not raw_markets:
        print("No markets found")
        return

    print(f"Found {len(raw_markets)} markets\n")

    # Show first 5 markets with full details
    for i, market in enumerate(raw_markets[:5], 1):
        ticker = market.get('ticker', 'N/A')
        title = market.get('title', 'N/A')
        subtitle = market.get('subtitle', 'N/A')

        print(f"\n{'='*80}")
        print(f"Market {i}: {ticker}")
        print(f"{'='*80}")
        print(f"Title:    {title}")
        print(f"Subtitle: {subtitle}")
        print(f"Full question would be: {title} - {subtitle}" if subtitle else f"Full question would be: {title}")
        print()

    # Now parse them into WeatherMarket objects and show the questions
    print("\n" + "="*80)
    print("After parsing into WeatherMarket objects:")
    print("="*80 + "\n")

    weather_markets = client._parse_weather_markets(raw_markets[:5])

    for market in weather_markets:
        print(f"Market ID: {market.market_id}")
        print(f"Question:  {market.question}")
        print(f"Location:  {market.location}")
        print(f"{'-'*80}")

if __name__ == "__main__":
    main()
