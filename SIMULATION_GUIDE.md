# 2-Week Simulation Trading Guide

## Quick Start

Run a 2-week simulation to validate the extreme value strategy before risking real money.

```bash
# 1. Clear old test data
Remove-Item data\trades.db  # Windows
# OR
rm data/trades.db  # Linux/Mac

# 2. Configure your .env file (see below)

# 3. Start the bot
python bot.py bot-start --simulation --platform kalshi

# 4. Check status anytime
python bot.py bot-status --simulation --platform kalshi

# 5. Stop the bot
Ctrl+C  # or python bot.py bot-stop
```

---

## Configuration (.env file)

Add these settings to your `.env` file:

```bash
# Kalshi API (required)
KALSHI_API_KEY_ID=your_api_key_id_here
KALSHI_API_PRIVATE_KEY=your_private_key_here

# Bot Configuration
BANKROLL=1000.00              # Total capital allocated
SCAN_INTERVAL_HOURS=6         # Scan every 6 hours
MAX_TRADES_PER_SCAN=20        # Execute up to 20 trades per scan
MAX_TRADES_PER_DAY=50         # Hard limit per day
MAX_TRADES_PER_CITY=3         # Limit correlation risk
MAX_DAILY_EXPOSURE_PCT=5.0    # Max 5% of bankroll risked per day
RESOLUTION_CHECK_HOURS=1      # Check for resolutions every hour

# Strategy Parameters (extreme value betting)
EXTREME_YES_MAX_PRICE=0.15    # Buy YES only if < 15¢
EXTREME_NO_MIN_YES_PRICE=0.40 # Buy NO only if YES > 40¢
EXTREME_MIN_POSITION=0.50     # Minimum bet size
EXTREME_MAX_POSITION=1.00     # Standard bet size
EXTREME_AGGRESSIVE_MAX=1.50   # Max bet for great opportunities

# Optional (for logging)
LOG_LEVEL=INFO
LOG_DIR=./logs
```

---

## What the Bot Does

### Automated Trading Cycle (Every 6 Hours)

1. **Scans Kalshi** for weather temperature markets
2. **Finds extreme value opportunities**:
   - YES shares < 15¢
   - NO shares when YES > 40¢ (implying cheap NO)
3. **Applies filters**:
   - Time to resolution (2-168 hours)
   - Minimum liquidity
   - City diversification (max 3 per city)
4. **Executes top 20 trades** (or less if daily limit reached)
5. **Logs everything to database** (`data/trades.db`)

### Resolution Tracking (Every Hour)

1. **Checks all open trades** via Kalshi API
2. **Identifies resolved markets**
3. **Calculates P&L** (win/loss)
4. **Updates database automatically**

### Risk Management

- **Daily exposure cap**: 5% of bankroll ($50 if $1,000 bankroll)
- **Daily trade limit**: Max 50 trades/day
- **Position sizing**: $0.50-$5 based on price extremity
- **Diversification**: Max 3 trades per city

---

## Monitoring Your Simulation

### Check Bot Status

```bash
python bot.py bot-status --simulation --platform kalshi
```

**Output:**
```
Bot Status - SIMULATION Mode (KALSHI)

╭─ Performance Summary ────────╮
│ Total Trades       │      142 │
│ Open Positions     │       38 │
│ Win Rate           │    32.5% │
│                    │          │
│ Realized P&L       │   $45.80 │
│ Total Invested     │  $142.00 │
│ ROI                │    32.3% │
│                    │          │
│ Avg P&L/Trade      │    $0.44 │
│ Best Trade         │    $9.20 │
│ Worst Trade        │   $-0.85 │
│                    │          │
│ Avg Entry Price    │     11.2 │%
│ Avg Edge           │     60.3% │
╰──────────────────────────────╯
```

### View Recent Trades

```bash
python bot.py trades --simulation --limit 10
```

### View P&L Summary

```bash
python bot.py pnl --simulation
```

---

## Expected Results After 2 Weeks

### Simulation Parameters
- **Duration**: 14 days
- **Scans**: 56 scans (4 per day × 14 days)
- **Expected trades**: 280-840 trades (assuming 5-15 per scan)
- **Total capital risked**: ~$280-$840 (assuming $1 avg position)
- **Daily exposure**: ~$20-$60/day (within 5% limit)

### Success Criteria

| Metric | Good | Acceptable | Concerning |
|--------|------|------------|------------|
| **Win Rate** | > 30% | 25-30% | < 25% |
| **ROI** | > 50% | 20-50% | < 20% |
| **Avg P&L/Trade** | > $0.50 | $0.20-$0.50 | < $0.20 |
| **Total P&L** | > $140 | $56-$140 | < $56 |

### What These Numbers Mean

**If win rate is 30% on 5¢ avg entry:**
- Every 100 trades costs: $5 (100 × $1 × 5%)
- Every 100 trades returns: $30 (30 wins × $1)
- Profit: $25 per 100 trades
- **Over 500 trades: $125 profit on $25 total risk = 500% ROI**

**If win rate is 25%:**
- Profit: $20 per 100 trades
- **Over 500 trades: $100 profit = 400% ROI**

**If win rate is 20% (break-even threshold):**
- Profit: $15 per 100 trades
- **Over 500 trades: $75 profit = 300% ROI**

**If win rate < 20%:**
- Strategy may not work - DO NOT go live

---

## After 2 Weeks: Decision Matrix

### ✅ GO LIVE (Win Rate > 30%, ROI > 50%)
```bash
# Stop simulation
Ctrl+C

# Start live trading (be careful!)
python bot.py bot-start --live --platform kalshi
```

### ⚠️ ADJUST PARAMETERS (Win Rate 25-30%, ROI 20-50%)
Consider:
- Tightening thresholds (`EXTREME_YES_MAX_PRICE=0.12`)
- Reducing position sizes (`EXTREME_MAX_POSITION=0.75`)
- More diversification (`MAX_TRADES_PER_CITY=2`)
- Run another week of simulation with new settings

### ❌ DO NOT GO LIVE (Win Rate < 25%, ROI < 20%)
The strategy may not work for Kalshi temperature markets in 2026. Possible reasons:
- Markets are more efficient than in past years
- Weather patterns are different
- Not enough volume/liquidity
- Extreme prices are actually accurate

---

## Manual Resolution (If Auto-Resolution Fails)

If the bot can't auto-resolve trades, you can update manually:

```python
from bot.database.trade_history import TradeHistoryDB

db = TradeHistoryDB()

# Check Kalshi to see if market resolved
# If you won:
db.update_resolution(
    trade_id="sim_KXHIGHTSEA-26JAN14-B53.5_1768442917",
    won=True,
    pnl=0.95  # Your profit
)

# If you lost:
db.update_resolution(
    trade_id="sim_KXHIGHTSEA-26JAN14-B53.5_1768442917",
    won=False,
    pnl=-0.05  # Your loss (cost of trade)
)
```

---

## Troubleshooting

### Bot Not Finding Trades
```bash
# Check if markets exist
python bot.py extreme-scan --platform kalshi --limit 50

# If you see opportunities but bot isn't trading:
# - Check daily limits in .env
# - Check if exposure cap is hit
# - Verify bot is actually running (check logs)
```

### Database Errors
```bash
# Reset database
Remove-Item data\trades.db
python bot.py bot-start --simulation --platform kalshi
```

### Can't Connect to Kalshi
```bash
# Verify credentials
python bot.py balance --platform kalshi

# Check .env file has correct:
# KALSHI_API_KEY_ID=...
# KALSHI_API_PRIVATE_KEY=...
```

### Trades Not Resolving
```bash
# Check open trades
python bot.py trades --simulation | Select-String "pending"

# Manual resolution (see above section)
# OR wait - markets take 1-2 days to resolve
```

---

## FAQ

### Q: Why 6-hour scan interval?
**A:** Temperature markets resolve daily. Scanning 4×/day catches new markets without over-trading.

### Q: Why only 20 trades per scan?
**A:** Quality over quantity. Top 20 opportunities have best edge. More trades = more correlation + worse average edge.

### Q: Will simulation trades actually execute?
**A:** No! `--simulation` mode logs to database but doesn't hit Kalshi's API for real trades. Zero risk.

### Q: How do I know if a trade won/lost?
**A:** Bot auto-checks every hour. Or check Kalshi manually: https://kalshi.com/markets

### Q: Can I run multiple platforms simultaneously?
**A:** Not with current setup. Choose Kalshi OR Polymarket. Running both requires separate bot instances.

### Q: What if I want to stop early?
**A:** `Ctrl+C` stops the bot anytime. Your data in `data/trades.db` is preserved.

### Q: Can I change settings mid-simulation?
**A:** Yes, but stop bot first, edit `.env`, then restart. Changes apply to new trades only.

---

## VPS Deployment (After Successful Simulation)

Once you validate the strategy works, deploy to VPS for 24/7 operation:

### Option 1: Background Process (tmux/screen)
```bash
# SSH into VPS
ssh your-vps

# Start tmux session
tmux new -s trading-bot

# Run bot
python bot.py bot-start --live --platform kalshi

# Detach: Ctrl+B then D
# Reattach: tmux attach -t trading-bot
```

### Option 2: Systemd Service (Linux)
Create `/etc/systemd/system/trading-bot.service`:
```ini
[Unit]
Description=Kalshi Trading Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/your-user/polymarket-weather-bot
ExecStart=/home/your-user/polymarket-weather-bot/.venv/bin/python bot.py bot-start --live --platform kalshi
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
sudo systemctl status trading-bot
```

---

## Summary Commands

```bash
# Start 2-week simulation
python bot.py bot-start --simulation --platform kalshi

# Check status (run anytime)
python bot.py bot-status --simulation --platform kalshi

# View P&L
python bot.py pnl --simulation

# View all trades
python bot.py trades --simulation --limit 100

# Stop bot
Ctrl+C

# After 2 weeks, if successful:
python bot.py bot-start --live --platform kalshi
```

**Good luck! Remember: Validate the strategy in simulation before risking real money.**
