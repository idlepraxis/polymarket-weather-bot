"""Script to analyze successful trader's strategy by fetching their trade history."""

import json
import time
from collections import defaultdict
from datetime import datetime

import httpx
from web3 import Web3

# Target wallet
TRADER_ADDRESS = "0x8278252ebbf354eca8ce316e680a0eaf02859464"

# Polymarket API endpoints
CLOB_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"


def fetch_trader_history(address: str, limit: int = 1000):
    """Fetch trade history for a specific address."""
    print(f"Fetching trades for {address}...")

    # Use CLOB API to get trades
    url = f"{CLOB_API}/trades"
    params = {
        "maker": address,
        "limit": limit,
    }

    try:
        response = httpx.get(url, params=params, timeout=30.0)
        if response.status_code == 200:
            trades = response.json()
            print(f"Found {len(trades)} trades")
            return trades
        else:
            print(f"Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching trades: {e}")
        return []


def analyze_price_distribution(trades):
    """Analyze the price distribution of trades."""
    yes_prices = []
    no_prices = []

    for trade in trades:
        price = float(trade.get("price", 0))
        side = trade.get("side")

        if side == "BUY":
            yes_prices.append(price)
        elif side == "SELL":
            # SELL = buying NO shares
            no_prices.append(price)

    print("\n=== PRICE DISTRIBUTION ===")
    print(f"YES trades: {len(yes_prices)}")
    if yes_prices:
        print(f"  Min: {min(yes_prices):.3f}")
        print(f"  Max: {max(yes_prices):.3f}")
        print(f"  Avg: {sum(yes_prices)/len(yes_prices):.3f}")
        print(f"  Below 0.15: {sum(1 for p in yes_prices if p < 0.15)}")
        print(f"  Below 0.10: {sum(1 for p in yes_prices if p < 0.10)}")

    print(f"\nNO trades: {len(no_prices)}")
    if no_prices:
        print(f"  Min: {min(no_prices):.3f}")
        print(f"  Max: {max(no_prices):.3f}")
        print(f"  Avg: {sum(no_prices)/len(no_prices):.3f}")
        # For NO shares, we care about YES price being high (so NO is cheap)
        # NO price = 1 - YES price
        yes_implied = [1 - p for p in no_prices]
        print(f"  YES implied above 0.40: {sum(1 for p in yes_implied if p > 0.40)}")
        print(f"  YES implied above 0.50: {sum(1 for p in yes_implied if p > 0.50)}")


def analyze_position_sizes(trades):
    """Analyze position size distribution."""
    sizes = []

    for trade in trades:
        size = float(trade.get("size", 0))
        sizes.append(size)

    print("\n=== POSITION SIZES ===")
    if sizes:
        print(f"Total trades: {len(sizes)}")
        print(f"Min: ${min(sizes):.2f}")
        print(f"Max: ${max(sizes):.2f}")
        print(f"Avg: ${sum(sizes)/len(sizes):.2f}")
        print(f"Median: ${sorted(sizes)[len(sizes)//2]:.2f}")
        print(f"Below $1: {sum(1 for s in sizes if s < 1)}")
        print(f"Below $5: {sum(1 for s in sizes if s < 5)}")


def analyze_weather_markets(trades):
    """Filter and analyze weather-specific trades."""
    weather_keywords = [
        'temperature', 'rain', 'snow', 'weather', 'degrees',
        'fahrenheit', 'celsius', 'high temp', 'low temp'
    ]

    weather_trades = []

    for trade in trades:
        market = trade.get("market", "").lower()
        if any(keyword in market for keyword in weather_keywords):
            weather_trades.append(trade)

    print(f"\n=== WEATHER MARKETS ===")
    print(f"Weather trades: {len(weather_trades)} / {len(trades)} ({len(weather_trades)/len(trades)*100:.1f}%)")

    return weather_trades


def extract_strategy_rules(trades):
    """Extract the core strategy rules from trades."""
    print("\n=== STRATEGY EXTRACTION ===")

    yes_buys = []
    no_buys = []

    for trade in trades:
        price = float(trade.get("price", 0))
        side = trade.get("side")
        size = float(trade.get("size", 0))

        if side == "BUY":
            yes_buys.append({"price": price, "size": size})
        elif side == "SELL":
            no_buys.append({"price": price, "size": size})

    # Analyze YES buys
    print("\nYES Buy Rules:")
    if yes_buys:
        prices = [t["price"] for t in yes_buys]
        avg_price = sum(prices) / len(prices)
        max_price = max(prices)
        pct_below_15 = sum(1 for p in prices if p < 0.15) / len(prices)
        pct_below_10 = sum(1 for p in prices if p < 0.10) / len(prices)

        print(f"  Average price: {avg_price:.3f}")
        print(f"  Max price: {max_price:.3f}")
        print(f"  % below 0.15: {pct_below_15*100:.1f}%")
        print(f"  % below 0.10: {pct_below_10*100:.1f}%")
        print(f"  → RULE: Buy YES when price < {max_price:.2f} (prefer < 0.15)")

    # Analyze NO buys (SELL side)
    print("\nNO Buy Rules (via SELL):")
    if no_buys:
        prices = [t["price"] for t in no_buys]
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)

        # NO price = 1 - YES price
        yes_implied = [1 - p for p in prices]
        avg_yes = sum(yes_implied) / len(yes_implied)
        min_yes = min(yes_implied)

        pct_above_40 = sum(1 for p in yes_implied if p > 0.40) / len(yes_implied)
        pct_above_50 = sum(1 for p in yes_implied if p > 0.50) / len(yes_implied)

        print(f"  Average NO price: {avg_price:.3f}")
        print(f"  Min NO price: {min_price:.3f}")
        print(f"  Average YES implied: {avg_yes:.3f}")
        print(f"  Min YES implied: {min_yes:.3f}")
        print(f"  % YES implied > 0.40: {pct_above_40*100:.1f}%")
        print(f"  % YES implied > 0.50: {pct_above_50*100:.1f}%")
        print(f"  → RULE: Buy NO when YES price > {min_yes:.2f} (prefer > 0.40)")


def main():
    """Main analysis function."""
    print("=" * 60)
    print("POLYMARKET WEATHER TRADER ANALYSIS")
    print(f"Wallet: {TRADER_ADDRESS}")
    print("=" * 60)

    # Fetch trades
    trades = fetch_trader_history(TRADER_ADDRESS)

    if not trades:
        print("\nTrying alternative API endpoints...")
        # Try getting data from Gamma API
        # Note: This might require different approach
        return

    # Analyze
    analyze_price_distribution(trades)
    analyze_position_sizes(trades)
    weather_trades = analyze_weather_markets(trades)
    extract_strategy_rules(trades)

    # Save raw data
    with open("trader_analysis.json", "w") as f:
        json.dump(trades, f, indent=2)

    print("\n✓ Analysis complete. Data saved to trader_analysis.json")


if __name__ == "__main__":
    main()
