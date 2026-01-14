#!/usr/bin/env python3
"""Debug script to check Kalshi configuration loading."""

from bot.utils.config import get_config

config = get_config()

print("=" * 60)
print("Kalshi Configuration Debug")
print("=" * 60)

print(f"\nKALSHI_API_KEY_ID:")
if config.kalshi_api_key_id:
    print(f"  ✓ Loaded: {config.kalshi_api_key_id[:20]}...")
else:
    print("  ✗ NOT LOADED (None or empty)")

print(f"\nKALSHI_API_PRIVATE_KEY:")
if config.kalshi_api_private_key:
    key_preview = config.kalshi_api_private_key[:50].replace('\n', '\\n')
    print(f"  ✓ Loaded: {key_preview}...")
    print(f"  Length: {len(config.kalshi_api_private_key)} characters")
    print(f"  Has BEGIN marker: {'BEGIN RSA' in config.kalshi_api_private_key}")
    print(f"  Has END marker: {'END RSA' in config.kalshi_api_private_key}")
    print(f"  Newlines count: {config.kalshi_api_private_key.count(chr(10))}")
else:
    print("  ✗ NOT LOADED (None or empty)")

print(f"\nKALSHI_EMAIL:")
if config.kalshi_email:
    print(f"  ✓ Loaded: {config.kalshi_email}")
else:
    print("  ✗ NOT LOADED (None or empty)")

print(f"\nKALSHI_PASSWORD:")
if config.kalshi_password:
    print(f"  ✓ Loaded: {'*' * 10}")
else:
    print("  ✗ NOT LOADED (None or empty)")

print(f"\nKALSHI_USE_DEMO: {config.kalshi_use_demo}")

print("\n" + "=" * 60)
print("Diagnosis:")
print("=" * 60)

has_api_key = config.kalshi_api_key_id and config.kalshi_api_private_key
has_password = config.kalshi_email and config.kalshi_password

if has_api_key:
    print("✓ API Key credentials found - will use API key auth")
elif has_password:
    print("✓ Email/Password credentials found - will use password auth")
else:
    print("✗ NO VALID CREDENTIALS FOUND")
    print("\nPlease check your .env file and ensure:")
    print("  1. The .env file exists in the project root")
    print("  2. Credentials are properly formatted")
    print("  3. No quotes around multiline private keys")
