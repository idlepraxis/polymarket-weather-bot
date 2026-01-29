#!/usr/bin/env python3
"""Debug script to inspect trade data."""
import sqlite3

conn = sqlite3.connect('data/trades.db')
cursor = conn.cursor()

print("=== WINNING TRADES ===")
cursor.execute("""
    SELECT price, size, cost, pnl, question
    FROM trades
    WHERE simulation = 1 AND platform = 'kalshi' AND won = 1
""")
for r in cursor.fetchall():
    print(f"Price: {r[0]:.1%}, Size: ${r[1]:.2f}, Cost: ${r[2]:.2f}, PnL: ${r[3]:.2f}")
    print(f"  {r[4][:70]}")

print("\n=== SAMPLE LOSING TRADES ===")
cursor.execute("""
    SELECT price, size, cost, pnl
    FROM trades
    WHERE simulation = 1 AND platform = 'kalshi' AND won = 0
    LIMIT 5
""")
for r in cursor.fetchall():
    print(f"Price: {r[0]:.1%}, Size: ${r[1]:.2f}, Cost: ${r[2]:.2f}, PnL: ${r[3]:.2f}")

print("\n=== TRADE SIZE DISTRIBUTION ===")
cursor.execute("""
    SELECT MIN(size), MAX(size), AVG(size), MIN(cost), MAX(cost), AVG(cost)
    FROM trades
    WHERE simulation = 1 AND platform = 'kalshi'
""")
r = cursor.fetchone()
print(f"Size - Min: ${r[0]:.2f}, Max: ${r[1]:.2f}, Avg: ${r[2]:.2f}")
print(f"Cost - Min: ${r[3]:.2f}, Max: ${r[4]:.2f}, Avg: ${r[5]:.2f}")

conn.close()
