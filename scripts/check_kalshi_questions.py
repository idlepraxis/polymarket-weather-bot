#!/usr/bin/env python3
"""Check what Kalshi API returns for market questions."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

try:
    from bot.connectors.kalshi import KalshiClient
    from bot.utils.logger import get_logger
    from bot.utils.config import Config
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\nMake sure you're running this from the project root directory:")
    print("  cd /root/trading-bots/polymarket-weather-bot")
    print("  python3 scripts/check_kalshi_questions.py")
    sys.exit(1)

def main():
    logger = get_logger()

    try:
        # Initialize config (will load from .env)
        config = Config()

        # Initialize client
        client = KalshiClient(config)
    except Exception as e:
        print(f"❌ Failed to initialize Kalshi client: {e}")
        print("\nMake sure your .env file has KALSHI_API_KEY_ID and KALSHI_API_PRIVATE_KEY")
        sys.exit(1)

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
    print("After parsing into WeatherMarket objects (WITH LOCATION INJECTION):")
    print("="*80 + "\n")

    for market_data in raw_markets[:5]:
        market = client._parse_weather_market(market_data)
        if market:
            print(f"Market ID: {market.market_id}")
            print(f"Question:  {market.question}")
            print(f"Location:  {market.location}")
            print(f"{'-'*80}")

if __name__ == "__main__":
    main()
