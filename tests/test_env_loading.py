#!/usr/bin/env python3
"""Debug script to check .env file loading."""

import os
from dotenv import load_dotenv

print("=" * 60)
print("Testing .env File Loading")
print("=" * 60)

# Load .env file
env_file = ".env"
if os.path.exists(env_file):
    print(f"\n✓ Found .env file at: {os.path.abspath(env_file)}")
    load_dotenv(env_file)
else:
    print(f"\n✗ .env file not found at: {os.path.abspath(env_file)}")
    print("Please create a .env file in the project root directory")
    exit(1)

print("\n" + "=" * 60)
print("Kalshi Credentials Check")
print("=" * 60)

# Check API Key ID
api_key_id = os.getenv("KALSHI_API_KEY_ID")
print(f"\nKALSHI_API_KEY_ID:")
if api_key_id:
    print(f"  ✓ Loaded: {api_key_id[:20]}...")
    print(f"  Length: {len(api_key_id)} characters")
else:
    print("  ✗ NOT LOADED (empty or missing)")

# Check Private Key
private_key = os.getenv("KALSHI_API_PRIVATE_KEY")
print(f"\nKALSHI_API_PRIVATE_KEY:")
if private_key:
    # Show first 50 chars with escaped newlines
    preview = private_key[:80].replace('\n', '\\n')
    print(f"  ✓ Loaded: {preview}...")
    print(f"  Total length: {len(private_key)} characters")
    print(f"  Contains 'BEGIN RSA': {('BEGIN RSA' in private_key)}")
    print(f"  Contains 'END RSA': {('END RSA' in private_key)}")
    print(f"  Number of newlines: {private_key.count(chr(10))}")

    # Check if it looks like a valid PEM key
    is_valid = (
        '-----BEGIN RSA PRIVATE KEY-----' in private_key and
        '-----END RSA PRIVATE KEY-----' in private_key and
        private_key.count('\n') >= 2
    )

    if is_valid:
        print(f"  ✓ Appears to be a valid PEM format")
    else:
        print(f"  ⚠ WARNING: May not be in valid PEM format")
        print(f"    Expected format:")
        print(f"      - Must start with '-----BEGIN RSA PRIVATE KEY-----'")
        print(f"      - Must end with '-----END RSA PRIVATE KEY-----'")
        print(f"      - Must have newlines between sections")
else:
    print("  ✗ NOT LOADED (empty or missing)")

# Check email/password fallback
email = os.getenv("KALSHI_EMAIL")
password = os.getenv("KALSHI_PASSWORD")

print(f"\nKALSHI_EMAIL: {'✓ ' + email if email else '✗ Not set'}")
print(f"KALSHI_PASSWORD: {'✓ Set' if password else '✗ Not set'}")

print("\n" + "=" * 60)
print("Diagnosis")
print("=" * 60)

has_api_key = api_key_id and private_key
has_password = email and password

if has_api_key:
    print("\n✓ API Key credentials found!")
    print("  The bot will attempt to use API key authentication.")

    if private_key and '-----BEGIN RSA PRIVATE KEY-----' not in private_key:
        print("\n⚠ WARNING: Private key may be incorrectly formatted!")
        print("  See instructions below for proper formatting.")
elif has_password:
    print("\n✓ Email/Password credentials found!")
    print("  The bot will use password authentication.")
else:
    print("\n✗ NO VALID CREDENTIALS FOUND!")
    print("\nPlease add to your .env file:")
    print("\n  Option 1: API Key (recommended)")
    print('  KALSHI_API_KEY_ID="your-key-id"')
    print('  KALSHI_API_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\\nMIIE...\\n-----END RSA PRIVATE KEY-----"')
    print("\n  Option 2: Email/Password")
    print('  KALSHI_EMAIL="your@email.com"')
    print('  KALSHI_PASSWORD="your-password"')

print("\n" + "=" * 60)
