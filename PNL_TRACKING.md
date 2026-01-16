# P&L Tracking Guide

## Overview

The bot now includes comprehensive profit & loss (P&L) tracking using SQLite. All trades (both live and simulation) are automatically logged to a database for later analysis.

## Features

✅ **Automatic Trade Logging** - Every trade is logged to SQLite database
✅ **Simulation Support** - Track paper trading separately from live trades
✅ **Multi-Platform** - Supports both Polymarket and Kalshi
✅ **Rich Statistics** - Win rate, ROI, average edge, best/worst trades
✅ **Resolution Tracking** - Update trades when markets resolve (future feature)

## Database

- **Location**: `./data/trades.db`
- **Type**: SQLite3
- **Schema**: Stores trade details, platform, simulation status, P&L, and resolution data

## New CLI Commands

### 1. View P&L Summary

```bash
# View LIVE trading P&L
python bot.py pnl

# View SIMULATION trading P&L
python bot.py pnl --simulation

# Filter by platform
python bot.py pnl --simulation --platform kalshi
python bot.py pnl --platform polymarket
```

**Metrics Shown:**
- Total trades executed
- Win/loss count and win rate
- Realized P&L (from resolved trades)
- Total invested
- ROI (return on investment)
- Average P&L per trade
- Best and worst trades
- Average entry price and edge

### 2. View Recent Trades

```bash
# View last 20 LIVE trades
python bot.py trades

# View last 20 SIMULATION trades
python bot.py trades --simulation

# Show more trades
python bot.py trades --simulation --limit 50

# Filter by platform
python bot.py trades --simulation --platform kalshi
```

**Shows:**
- Date and time
- Platform (Polymarket, Kalshi)
- Side (BUY/SELL)
- Entry price and size
- Total cost
- P&L (if resolved, otherwise "pending")
- Market question

### 3. View Statistics by Platform

```bash
# Compare Polymarket vs Kalshi performance
python bot.py stats --simulation

# Live trades stats
python bot.py stats
```

**Shows:**
- Platform-specific metrics
- Total trades per platform
- Win rate by platform
- ROI comparison
- Average entry price

## Example Workflow: Paper Trading for a Week

```bash
# Day 1-7: Run simulation trades
python bot.py extreme-trade --dry-run --max-trades 5 --platform kalshi

# Check your simulated performance
python bot.py pnl --simulation

# View all simulated trades
python bot.py trades --simulation --limit 50

# Compare platforms
python bot.py stats --simulation

# If results look good, switch to live trading
python bot.py extreme-trade --max-trades 5 --platform kalshi
python bot.py pnl  # View live P&L
```

## Testing the P&L System

Run the test script to see sample data:

```bash
python test_pnl_tracking.py
python bot.py pnl --simulation
python bot.py trades --simulation
python bot.py stats --simulation
```

This creates 3 sample trades (2 Kalshi, 1 Polymarket) with realistic data.

## How It Works

### Automatic Logging

When you run `extreme-trade`, every executed trade is automatically logged:

```python
# After successful trade execution
trade = Trade(
    trade_id=order_id,
    timestamp=datetime.now(timezone.utc),
    market_id=signal.market.market_id,
    question=signal.market.question,
    side=TradeSide.BUY,
    price=signal.price,
    size=signal.size,
    cost=signal.size,  # FIXED: Cost equals size (position size in USD)
    simulation=dry_run,  # True for --dry-run, False for live
    ...
)

trade_db.log_trade(trade, platform="kalshi")
```

### Resolution Tracking (Manual - for now)

When a market resolves, you can manually update the P&L:

```python
from bot.database.trade_history import TradeHistoryDB

db = TradeHistoryDB()

# If your trade won
db.update_resolution(
    trade_id="your-trade-id",
    won=True,
    pnl=0.90  # Profit in USDC
)

# If your trade lost
db.update_resolution(
    trade_id="your-trade-id",
    won=False,
    pnl=-0.10  # Loss in USDC
)
```

**Status as of Jan 16, 2026**: ✅ Automatic resolution tracking is now IMPLEMENTED. The bot checks resolutions hourly via Kalshi API and automatically updates P&L for resolved trades.

## Example Output

### P&L Summary
```
SIMULATION Trading P&L (ALL PLATFORMS)

╭───────────────────┬────────╮
│ Metric            │  Value │
├───────────────────┼────────┤
│ Total Trades      │     25 │
│ Winning Trades    │     18 │
│ Losing Trades     │      7 │
│ Win Rate          │  72.0% │
│                   │        │
│ Realized P&L      │ $45.80 │
│ Total Invested    │ $25.00 │
│ ROI               │ 183.2% │
│                   │        │
│ Avg P&L per Trade │  $1.83 │
│ Best Trade        │  $8.50 │
│ Worst Trade       │ $-0.95 │
│                   │        │
│ Avg Entry Price   │  11.2% │
│ Avg Edge          │  58.7% │
╰───────────────────┴────────╯
```

## Database Queries (Advanced)

You can query the SQLite database directly:

```bash
sqlite3 data/trades.db
```

```sql
-- View all simulation trades
SELECT * FROM trades WHERE simulation = 1;

-- Calculate win rate by platform
SELECT
    platform,
    COUNT(*) as total,
    SUM(CASE WHEN won = 1 THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN won = 1 THEN 1.0 ELSE 0 END) / COUNT(*) * 100, 1) as win_rate
FROM trades
WHERE resolved = 1
GROUP BY platform;

-- Find best trades
SELECT question, platform, price, pnl
FROM trades
WHERE resolved = 1
ORDER BY pnl DESC
LIMIT 10;
```

## Tips

1. **Start with Simulation**: Always run `--dry-run` first to test your strategy
2. **Review Weekly**: Check `python bot.py stats --simulation` weekly to evaluate performance
3. **Platform Comparison**: Use stats to see which platform performs better
4. **Track Your Edge**: Monitor "Avg Edge" - should be high for extreme value strategy
5. **Win Rate Goal**: Aim for 60%+ win rate on extreme value bets
6. **Small Bets**: Keep position sizes small ($0.50-$2) until proven profitable

## Files Modified

- `bot/database/trade_history.py` - New SQLite database handler
- `bot/cli/cli.py` - Added automatic logging + 3 new commands (`pnl`, `trades`, `stats`)
- `bot/utils/models.py` - Existing Trade model used for logging

## Limitations

- **Manual Resolution**: Currently requires manual update of trade outcomes
- **No Cross-Platform Aggregation**: Stats are per-platform, not global
- **No Time-Series Analysis**: Can't see P&L over time (yet)

## Future Enhancements

1. Automatic resolution tracking via APIs
2. Time-series P&L charts
3. Email/Telegram alerts for trade results
4. Export to CSV for external analysis
5. Backtesting framework using historical trades
