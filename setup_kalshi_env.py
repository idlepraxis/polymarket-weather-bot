#!/usr/bin/env python3
"""Helper script to set up Kalshi credentials in .env file."""

import os

print("=" * 60)
print("Kalshi .env Setup Helper")
print("=" * 60)

# Get API key ID
print("\n1. Enter your Kalshi API Key ID (UUID format):")
print("   Example: 5006d09c-49e7-4196-a883-738dc3d0a0e9")
api_key_id = input("   > ").strip()

if not api_key_id:
    print("\n✗ API Key ID is required!")
    exit(1)

# Get private key
print("\n2. Paste your ENTIRE RSA Private Key (including BEGIN/END markers).")
print("   Press Enter, then paste the key, then press Enter twice when done:")
print()

lines = []
while True:
    line = input()
    if line == "" and lines:  # Empty line after some content = done
        break
    if line:  # Non-empty line
        lines.append(line)

private_key = "\n".join(lines)

if not private_key:
    print("\n✗ Private key is required!")
    exit(1)

# Validate the key format
if "-----BEGIN RSA PRIVATE KEY-----" not in private_key:
    print("\n⚠ WARNING: Private key doesn't contain BEGIN marker!")
    print("Make sure you pasted the complete key including:")
    print("  -----BEGIN RSA PRIVATE KEY-----")

if "-----END RSA PRIVATE KEY-----" not in private_key:
    print("\n⚠ WARNING: Private key doesn't contain END marker!")
    print("Make sure you pasted the complete key including:")
    print("  -----END RSA PRIVATE KEY-----")

print("\n" + "=" * 60)
print("Creating .env file...")
print("=" * 60)

# For .env files, we need to escape the newlines
# The private key should be stored with literal \n characters
private_key_escaped = private_key.replace('\n', '\\n')

# Create .env content
env_content = f"""# Kalshi API Configuration
KALSHI_API_KEY_ID="{api_key_id}"
KALSHI_API_PRIVATE_KEY="{private_key_escaped}"
KALSHI_USE_DEMO=false

# Conservative $100 Strategy: Small bets, high volume
EXTREME_MIN_POSITION=0.50
EXTREME_MAX_POSITION=2.00
EXTREME_AGGRESSIVE_MAX=3.00
EXTREME_YES_MAX_PRICE=0.15
EXTREME_NO_MIN_YES_PRICE=0.40

# Trading Parameters
MAX_POSITION_SIZE_USDC=5.0
MIN_EDGE_THRESHOLD=0.05
MIN_CONFIDENCE=0.70
MAX_DAILY_TRADES=50
MAX_OPEN_POSITIONS=20

# Bot Behavior
POLL_INTERVAL_MINUTES=15
SIMULATION_MODE=true
LOG_LEVEL=INFO

# Data Storage
CACHE_DIR=./data/cache
WEATHER_DB_DIR=./data/weather_db
LOG_DIR=./logs

# Placeholder values for optional features (not needed for Kalshi-only usage)
POLYGON_WALLET_PRIVATE_KEY="not-needed-for-kalshi-only"
CHAINSTACK_RPC_URL="not-needed-for-kalshi-only"
CHAINSTACK_WS_URL="not-needed-for-kalshi-only"
OPENWEATHER_API_KEY="not-needed-for-kalshi-only"
"""

# Write to .env file
with open(".env", "w") as f:
    f.write(env_content)

print("\n✓ Successfully created .env file!")
print("\nYour .env file has been configured with:")
print(f"  - API Key ID: {api_key_id[:20]}...")
print(f"  - Private Key: {len(private_key)} characters")
print(f"  - Conservative strategy: $0.50-$3.00 bets")
print("\nYou can now run:")
print("  python bot.py balance --platform kalshi")

print("\n" + "=" * 60)
