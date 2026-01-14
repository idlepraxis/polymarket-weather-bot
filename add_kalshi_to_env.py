#!/usr/bin/env python3
"""Add Kalshi credentials to existing .env file WITHOUT overwriting it."""

import os

print("=" * 60)
print("Add Kalshi to Existing .env")
print("=" * 60)

# Check if .env exists
if not os.path.exists(".env"):
    print("\n✗ No .env file found!")
    print("Please create one first with your Polymarket credentials.")
    exit(1)

# Read existing .env
with open(".env", "r") as f:
    existing_content = f.read()

# Check if Kalshi is already configured
if "KALSHI_API_KEY_ID" in existing_content:
    print("\n⚠ Kalshi credentials already exist in .env!")
    overwrite = input("Do you want to replace them? (yes/no): ").strip().lower()
    if overwrite != "yes":
        print("Aborted.")
        exit(0)
    # Remove existing Kalshi lines
    lines = existing_content.split('\n')
    filtered_lines = [l for l in lines if not l.startswith('KALSHI_')]
    existing_content = '\n'.join(filtered_lines)

# Get API key ID
print("\n1. Enter your Kalshi API Key ID (UUID format):")
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
    if line == "" and lines:
        break
    if line:
        lines.append(line)

private_key = "\n".join(lines)

if not private_key or "BEGIN RSA PRIVATE KEY" not in private_key:
    print("\n✗ Invalid private key!")
    exit(1)

# Escape newlines for .env format
private_key_escaped = private_key.replace('\n', '\\n')

# Add Kalshi configuration
kalshi_config = f"""

# Kalshi API (US-legal prediction market)
KALSHI_API_KEY_ID="{api_key_id}"
KALSHI_API_PRIVATE_KEY="{private_key_escaped}"
KALSHI_USE_DEMO=false
"""

# Append to existing .env
with open(".env", "w") as f:
    f.write(existing_content.rstrip() + kalshi_config)

print("\n✓ Kalshi credentials added to .env!")
print("\nYour existing Polymarket settings were preserved.")
print("\nYou can now run:")
print("  python bot.py balance --platform polymarket  # Test Polymarket")
print("  python bot.py balance --platform kalshi       # Test Kalshi")
