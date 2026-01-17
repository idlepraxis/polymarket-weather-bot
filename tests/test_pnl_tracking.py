#!/usr/bin/env python3
"""Test script to verify P&L tracking with simulated trades."""

import uuid
from datetime import datetime, timezone

from bot.database.trade_history import TradeHistoryDB
from bot.utils.models import Trade, TradeSide

# Initialize database
db = TradeHistoryDB()

print("Creating test trades...")

# Test Trade 1: Kalshi YES at 10¢ (extreme value)
trade1 = Trade(
    trade_id=str(uuid.uuid4()),
    timestamp=datetime.now(timezone.utc),
    market_id="KXHIGHTSEA-26JAN14",
    question="Will Seattle hit maximum temperature above 45°F on January 26?",
    token_id="yes_token_123",
    side=TradeSide.BUY,
    price=0.10,  # 10¢
    size=1.00,  # $1 USDC
    cost=0.10,  # $1 * 0.10 = $0.10
    simulation=True,
    tx_hash="sim_tx_1",
    status="executed",
    fair_probability=0.75,
    edge=0.65,  # 75% - 10% = huge edge!
    reasoning="Extreme value: YES at 10¢ when fair prob is 75%"
)

db.log_trade(trade1, platform="kalshi")

# Test Trade 2: Polymarket NO at 8¢ (YES at 92¢)
trade2 = Trade(
    trade_id=str(uuid.uuid4()),
    timestamp=datetime.now(timezone.utc),
    market_id="0x1234567890abcdef",
    question="Will NYC have high temp above 80°F on July 4?",
    token_id="no_token_456",
    side=TradeSide.BUY,
    price=0.08,  # Buying NO at 8¢ (YES is at 92¢)
    size=2.00,  # $2 USDC
    cost=0.16,  # $2 * 0.08 = $0.16
    simulation=True,
    tx_hash="sim_tx_2",
    status="executed",
    fair_probability=0.25,  # 25% chance YES
    edge=0.67,  # NO should be 75¢, we're buying at 8¢ for YES
    reasoning="Extreme value: NO at 8¢ when YES price is way too high (92¢)"
)

db.log_trade(trade2, platform="polymarket")

# Test Trade 3: Smaller Kalshi trade
trade3 = Trade(
    trade_id=str(uuid.uuid4()),
    timestamp=datetime.now(timezone.utc),
    market_id="KXLOWTNYC-27JAN14",
    question="Will NYC hit minimum temperature below 20°F on January 27?",
    token_id="yes_token_789",
    side=TradeSide.BUY,
    price=0.12,  # 12¢
    size=0.50,  # $0.50 USDC
    cost=0.06,  # $0.50 * 0.12 = $0.06
    simulation=True,
    tx_hash="sim_tx_3",
    status="executed",
    fair_probability=0.60,
    edge=0.48,
    reasoning="Extreme value: YES at 12¢ when fair prob is 60%"
)

db.log_trade(trade3, platform="kalshi")

print("\n✓ Created 3 test trades")

# Simulate one trade winning
print("\nSimulating Trade 1 resolution (WON)...")
# If we bought YES at 10¢ for $1 USDC, we get 10 shares
# If YES wins, we get $1.00 (10 shares * $0.10 per share)
# Profit = $1.00 - $0.10 = $0.90
db.update_resolution(trade1.trade_id, won=True, pnl=0.90)

# Simulate one trade losing
print("Simulating Trade 2 resolution (LOST)...")
# If we bought NO at 8¢ for $2 USDC, we spent $0.16
# If NO loses (YES wins), we get $0
# Loss = $0 - $0.16 = -$0.16
db.update_resolution(trade2.trade_id, won=False, pnl=-0.16)

print("\n" + "="*60)
print("Test data created! Now run:")
print("  python bot.py pnl --simulation")
print("  python bot.py trades --simulation")
print("  python bot.py stats --simulation")
print("="*60)
