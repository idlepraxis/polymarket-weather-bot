#!/usr/bin/env python3
"""Test Kalshi API key signing to debug authentication issues."""

import os
import time
import base64
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

# Load environment
load_dotenv()

api_key_id = os.getenv("KALSHI_API_KEY_ID")
private_key_pem = os.getenv("KALSHI_API_PRIVATE_KEY")

print("=" * 60)
print("Kalshi API Key Signing Test")
print("=" * 60)

print(f"\nAPI Key ID: {api_key_id[:20] if api_key_id else 'NOT LOADED'}...")

print(f"\nPrivate Key PEM (first 100 chars):")
if private_key_pem:
    print(f"  {repr(private_key_pem[:100])}...")
    print(f"\nKey length: {len(private_key_pem)} characters")
    print(f"Has 'BEGIN': {'BEGIN' in private_key_pem}")
    print(f"Has 'END': {'END' in private_key_pem}")
    print(f"Newline count: {private_key_pem.count(chr(10))}")
else:
    print("  NOT LOADED")
    exit(1)

# Try to load the private key
print("\n" + "=" * 60)
print("Testing Private Key Loading")
print("=" * 60)

try:
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None,
        backend=default_backend()
    )
    print("\n✓ Private key loaded successfully!")
except Exception as e:
    print(f"\n✗ Failed to load private key: {e}")
    print("\nThe private key format is incorrect. Make sure it's in PEM format with:")
    print("  - -----BEGIN RSA PRIVATE KEY-----")
    print("  - Actual newlines (not \\n literals)")
    print("  - -----END RSA PRIVATE KEY-----")
    exit(1)

# Test signing
print("\n" + "=" * 60)
print("Testing Request Signing")
print("=" * 60)

timestamp_ms = str(int(time.time() * 1000))
method = "GET"
path = "/portfolio/balance"

# Create message
msg_string = timestamp_ms + method + path
msg_bytes = msg_string.encode('utf-8')

print(f"\nMessage to sign: {repr(msg_string)}")
print(f"Message length: {len(msg_string)} chars")

# Sign
try:
    signature = private_key.sign(
        msg_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )

    sig_b64 = base64.b64encode(signature).decode('utf-8')

    print(f"\n✓ Signature generated successfully!")
    print(f"Signature (first 50 chars): {sig_b64[:50]}...")
    print(f"Signature length: {len(sig_b64)} chars")

    print("\n" + "=" * 60)
    print("Headers that would be sent:")
    print("=" * 60)
    print(f"KALSHI-ACCESS-KEY: {api_key_id}")
    print(f"KALSHI-ACCESS-TIMESTAMP: {timestamp_ms}")
    print(f"KALSHI-ACCESS-SIGNATURE: {sig_b64[:50]}...")

except Exception as e:
    print(f"\n✗ Failed to sign request: {e}")
    exit(1)

print("\n" + "=" * 60)
print("Diagnosis")
print("=" * 60)
print("\n✓ All signing operations successful!")
print("\nIf you're still getting authentication errors, the issue might be:")
print("  1. API key ID is incorrect")
print("  2. Private key doesn't match the public key registered with Kalshi")
print("  3. API key has been revoked or expired")
print("\nTry generating a new API key pair in your Kalshi account settings.")
