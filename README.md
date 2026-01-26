# Polymarket Weather Bot

**Automated trading bot for prediction market weather trading using extreme value betting strategy.**

> 🤖 **Current Status:** Fully operational with automated bot runner, P&L tracking, duplicate prevention, dual-mode resolution checking, and multi-platform support (Kalshi + Polymarket)

---

## 🎯 Strategy: Extreme Value Betting

The bot uses a **high-volume, extreme value strategy** based on successful trader analysis ($25,700 profit from 1,420 trades):

- **Buy YES** when price < 10-15¢
- **Buy NO** when YES > 40-50¢
- **Small positions** (~$1 per trade)
- **High volume** (20-30 trades/day)
- **Asymmetric payoffs** (risk $0.10 to win $0.90)

This exploits market mispricings through volume and asymmetric risk/reward ratios, not weather forecasting.

📖 **[Read Full Strategy Guide →](EXTREME_VALUE_STRATEGY.md)**

---

## ⚡ Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/idlepraxis/polymarket-weather-bot.git
cd polymarket-weather-bot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and add your credentials:

```bash
cp .env.example .env
```

**Required for Kalshi trading** (recommended):
```bash
KALSHI_EMAIL=your_email@example.com
KALSHI_PASSWORD=your_password
```

**Optional for Polymarket trading:**
```bash
POLYGON_WALLET_PRIVATE_KEY=your_wallet_private_key
CHAINSTACK_RPC_URL=https://polygon-mainnet.chainstacklabs.com/your_key
OPENWEATHER_API_KEY=your_openweather_key
```

**Bot Configuration** (optional, defaults provided):
```bash
BANKROLL=1000.0                    # Total capital
SCAN_INTERVAL_HOURS=6              # How often to scan for trades
MAX_TRADES_PER_SCAN=20             # Trades per scan cycle
MAX_TRADES_PER_DAY=50              # Daily trade limit
MAX_DAILY_EXPOSURE_PCT=5.0         # Max 5% of bankroll at risk per day
EXTREME_AGGRESSIVE_MAX=1.50        # Max position size ($1.50)
```

### 3. Start the Bot

**Simulation Mode (recommended first):**
```bash
# Activate virtual environment
source .venv/bin/activate

# Start automated bot in simulation mode
python bot.py bot-start --simulation --platform kalshi
```

The bot will:
- Scan for opportunities every 6 hours
- Execute up to 20 trades per scan
- Check for resolutions every hour
- Track all trades in SQLite database

**Live Mode (after validation):**
```bash
python bot.py bot-start --platform kalshi
```

### 4. Monitor Performance

**Check bot status:**
```bash
python bot.py bot-status --simulation --platform kalshi
```

Shows:
- Total trades executed
- Win rate and P&L
- Open positions
- Recent trades
- Performance metrics

**View detailed trade history:**
```bash
python bot.py trades --simulation --limit 50
```

**See P&L summary:**
```bash
python bot.py pnl --simulation --platform kalshi
```

### 5. Stop the Bot

```bash
python bot.py bot-stop
```

---

## 📱 Running on a VPS (24/7 Operation)

### Option 1: Tmux (Quick Setup)

**Start the bot in background:**
```bash
# Create tmux session
tmux new -s bot

# Inside tmux, start the bot
source .venv/bin/activate
python bot.py bot-start --simulation --platform kalshi

# Detach from tmux: Press Ctrl+B, then press D
```

**Check bot status later:**
```bash
# Reattach to see bot output
tmux attach -t bot

# Or check status without attaching
source .venv/bin/activate
python bot.py bot-status --simulation --platform kalshi

# Detach again: Ctrl+B, then D
```

**Stop the bot:**
```bash
# Attach to tmux
tmux attach -t bot

# Press Ctrl+C to stop bot
exit

# Or kill tmux session entirely
tmux kill-session -t bot
```

**Tmux useful commands:**
```bash
tmux ls                    # List all sessions
tmux attach -t bot         # Attach to session named "bot"
tmux kill-session -t bot   # Kill session
```

### Option 2: Systemd Service (Production)

**Create service file:**
```bash
sudo nano /etc/systemd/system/trading-bot.service
```

**Add configuration:**
```ini
[Unit]
Description=Polymarket Weather Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/polymarket-weather-bot
Environment="PATH=/path/to/polymarket-weather-bot/.venv/bin"
ExecStart=/path/to/polymarket-weather-bot/.venv/bin/python bot.py bot-start --simulation --platform kalshi
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot

# Check status
sudo systemctl status trading-bot

# View logs
sudo journalctl -u trading-bot -f
```

---

## 🎮 CLI Commands Reference

### Bot Management

| Command | Description |
|---------|-------------|
| `bot-start [--simulation] [--platform kalshi]` | Start automated bot |
| `bot-status [--simulation] [--platform kalshi]` | Show performance summary |
| `bot-stop` | Stop running bot |

### Performance Tracking

| Command | Description |
|---------|-------------|
| `pnl [--simulation] [--platform kalshi]` | P&L summary |
| `trades [--simulation] [--limit 50]` | Trade history |
| `stats [--simulation]` | Detailed statistics |

### Analysis & Strategy

| Command | Description |
|---------|-------------|
| `analyze-wallet <address>` | Reverse engineer strategy from Polymarket wallet |
| `analyze-wallet <address> --show-trades` | Show individual trades |

### Utilities

| Command | Description |
|---------|-------------|
| `config-check` | Verify configuration |
| `balance` | Check USDC balance (Polymarket) |
| `status` | Check portfolio (Polymarket) |

### Common Options

- `--simulation` / `--sim`: Use simulation mode (no real money)
- `--platform [kalshi|polymarket]`: Choose trading platform
- `--limit N`: Limit results shown

---

## 📊 How It Works

### 1. Market Scanning (Every 6 Hours)

```
┌─────────────┐
│  Bot Wakes  │
│   Up Every  │
│   6 Hours   │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ Fetch All Markets   │
│ from Kalshi API     │
│ (72+ weather mkts)  │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Filter for Extreme  │
│ Value Opportunities │
│ • YES < 15¢         │
│ • YES > 40¢ (NO)    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Apply Filters:      │
│ • City diversity    │
│ • Time to close     │
│ • Daily limits      │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Execute Top 20      │
│ Trades (~$1 each)   │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Log to Database     │
│ (trade_history.db)  │
└─────────────────────┘
```

### 2. Resolution Checking (Every Hour)

The bot uses **dual-mode resolution checking**:

**Simulation Mode:**
- Queries Kalshi markets API with `status=settled`
- Checks if markets have finalized
- No real positions to settle (local-only trades)

**Live Mode:**
- Uses Kalshi settlements API
- Checks actual settled positions
- Calculates real P&L from executed trades

```
┌─────────────┐
│  Check Open │
│  Positions  │
│  Every Hour │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ Query Kalshi API    │
│ • Simulation: Check │
│   finalized markets │
│ • Live: Check       │
│   settlements       │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ If Resolved:        │
│ • Calculate P&L     │
│ • Update Database   │
│ • Mark Complete     │
└─────────────────────┘
```

### 3. Position Sizing

Based on how cheap the opportunity is:

| Market Price | Position Size | Rationale |
|--------------|---------------|-----------|
| ≤ 5¢ | $1.50 (aggressive) | Super cheap, high upside |
| 5-8¢ | $1.00-1.25 | Very attractive |
| 8-10¢ | $1.00 | Ideal range |
| 10-12¢ | $0.75 | Good value |
| 12-15¢ | $0.50 | Acceptable |

**Average: ~$1.00 per trade**

### 4. Risk Management

- **Daily Exposure:** Max 5% of bankroll ($50 on $1,000)
- **Position Limit:** Max $1.50 per trade
- **Trade Limit:** Max 50 trades/day
- **City Diversification:** Max 3 trades per city
- **Resolution Time:** Only markets closing within 7 days

---

## 📈 Performance Metrics

The bot tracks comprehensive performance metrics:

### Win Rate Calculation
```
Win Rate = (Winning Trades / Total Resolved Trades) × 100%
```

### P&L Tracking
```
Realized P&L = Σ(Winning Trades) - Σ(Losing Trades)
ROI = (Realized P&L / Total Invested) × 100%
```

### Expected Results (2-Week Simulation)

Based on strategy analysis with $1,000 bankroll:

| Metric | Target | Notes |
|--------|--------|-------|
| **Win Rate** | 30-35% | Success threshold |
| **Total Trades** | 280-420 | 20-30 per day |
| **Avg Position** | $1.00 | Small positions |
| **Total Invested** | $280-420 | ~30% of bankroll |
| **ROI Target** | 50-100%+ | If win rate ≥30% |

**Decision Criteria:**
- Win rate **> 30%** → GO LIVE with real money
- Win rate **25-30%** → Adjust parameters, retest
- Win rate **< 25%** → Strategy not viable, don't go live

---

## 🔍 Wallet Analysis Feature

Reverse engineer successful traders' strategies by analyzing their on-chain Polymarket activity.

### Quick Start

```bash
# Analyze a wallet to extract strategy
bot analyze-wallet 0x8278252ebbf354eca8ce316e680a0eaf02859464

# Show individual trades
bot analyze-wallet 0x8278252ebbf354eca8ce316e680a0eaf02859464 --show-trades

# Limit number of trades fetched
bot analyze-wallet 0x8278252ebbf354eca8ce316e680a0eaf02859464 --limit 500
```

### What It Analyzes

The wallet analyzer extracts comprehensive strategy insights:

**📊 Entry Thresholds:**
- Average YES entry price
- Median YES/NO entry prices
- 10th/90th percentile thresholds
- Price ranges for extreme value strategy

**💰 Position Sizing:**
- Min, max, median, average position sizes
- Position size standard deviation
- Max single position as % of total volume

**🎲 Market Selection:**
- Category breakdown (weather, sports, politics, etc.)
- Weather market percentage
- Trading focus analysis

**📈 Risk Management:**
- Max daily exposure
- Average daily exposure
- Position diversification metrics

**⚡ Trading Frequency:**
- Trades per day average
- Trading period duration
- Activity patterns

**🎯 Performance by Range:**
- YES < 15¢ performance (extreme low)
- YES 15-40¢ performance (mid-range)
- NO buying performance (when YES > 40¢)

### Example Output

```
🎯 Strategy Overview
┌──────────────────────┬──────────────┐
│ Total Trades         │ 1,420        │
│ Total Volume         │ $25,700.00   │
│ Profit per Trade     │ $18.10       │
│ Trading Period       │ 456 days     │
│ Trades per Day       │ 3.1          │
└──────────────────────┴──────────────┘

📊 Entry Thresholds (Extreme Value Strategy)
┌──────────────────┬────────────┬────────────┐
│ Metric           │ YES Buys   │ NO Buys    │
├──────────────────┼────────────┼────────────┤
│ Trade Count      │ 892        │ 528        │
│ Average Entry    │ 11.2%      │ 38.5%      │
│ Median Entry     │ 10.5%      │ 37.0%      │
│ 10th Percentile  │ 5.2%       │ -          │
│ 90th Percentile  │ 14.8%      │ -          │
└──────────────────┴────────────┴────────────┘

💰 Position Sizing
┌───────────────────────┬──────────┐
│ Average Size          │ $1.85    │
│ Median Size           │ $1.50    │
│ Min Size              │ $0.50    │
│ Max Size              │ $5.00    │
└───────────────────────┴──────────┘

🎯 Reverse Engineered Strategy:

📍 YES Entry: Buy when price ≤ 10.5%
   Range: 5.2% to 14.8%

📍 NO Entry: Buy when YES price ≥ 63.0%

💰 Position Sizing: $1.50 median, $1.85 average
   Range: $0.50 to $5.00

📊 Frequency: 3.1 trades/day

🌤️ Focus: 94% weather markets

⚙️ Suggested .env Configuration:

EXTREME_YES_MAX_PRICE=0.15
EXTREME_YES_IDEAL_PRICE=0.11
EXTREME_NO_MIN_YES_PRICE=0.63
EXTREME_MIN_POSITION=0.50
EXTREME_MAX_POSITION=1.50
EXTREME_AGGRESSIVE_MAX=5.00
```

### Use Cases

**1. Strategy Validation:**
```bash
# Analyze Trader B (known successful trader)
bot analyze-wallet 0x8278252ebbf354eca8ce316e680a0eaf02859464

# Compare their thresholds to yours
# Adjust your .env settings to match
```

**2. Discovering New Strategies:**
```bash
# Find a high-volume trader on polymarketanalytics.com
# Analyze their approach
bot analyze-wallet 0x... --show-trades

# Look for patterns in their market selection
```

**3. Competitive Analysis:**
```bash
# Track multiple successful traders
for wallet in wallet1 wallet2 wallet3; do
  bot analyze-wallet $wallet > analysis_$wallet.txt
done

# Compare strategies across traders
```

### Data Sources

The analyzer fetches data from:
1. **Polymarket CLOB API** - Primary source for recent trades
2. **The Graph Subgraph** - Fallback for historical on-chain data

### Limitations

- Only analyzes Polymarket activity (not Kalshi)
- Requires wallet to have public trading history
- P&L data may be incomplete if markets are still resolving
- Subject to API rate limits (~1000 trades per query)

---

## 🏗️ Architecture

```
bot/
├── application/
│   ├── bot_runner.py          # Automated daemon (main loop)
│   ├── extreme_value_strategy.py  # Trading strategy logic
│   └── trader.py              # Legacy forecast-based trading
├── connectors/
│   ├── kalshi.py              # Kalshi API integration
│   ├── polymarket.py          # Polymarket + Chainstack
│   └── weather.py             # Weather API connector (optional)
├── database/
│   └── trade_history.py       # P&L tracking system
├── cli/
│   └── cli.py                 # Command-line interface
└── utils/
    ├── config.py              # Configuration management
    ├── logger.py              # Logging utilities
    └── models.py              # Data models

data/
└── trades.db                  # SQLite database (auto-created)

logs/
└── bot.log                    # Application logs (auto-created)
```

---

## 🔧 Configuration Reference

### Trading Strategy Parameters

```bash
# Position Sizing (target ~$1 avg per trade)
EXTREME_MIN_POSITION=0.50           # Minimum bet
EXTREME_MAX_POSITION=1.00           # Standard bet
EXTREME_AGGRESSIVE_MAX=1.50         # Maximum bet

# Entry Thresholds
EXTREME_YES_MAX_PRICE=0.15          # Buy YES if < 15¢
EXTREME_YES_IDEAL_PRICE=0.10        # Ideal YES price: 10¢
EXTREME_NO_MIN_YES_PRICE=0.40       # Buy NO if YES > 40¢
EXTREME_NO_IDEAL_YES_PRICE=0.50     # Ideal NO entry: YES @ 50¢
```

### Bot Runner Configuration

```bash
# Scanning & Trading
BANKROLL=1000.0                     # Total capital
SCAN_INTERVAL_HOURS=6               # Scan every 6 hours
MAX_TRADES_PER_SCAN=20              # Trades per scan
MAX_TRADES_PER_DAY=50               # Daily limit
MAX_TRADES_PER_CITY=3               # City diversification

# Risk Management
MAX_DAILY_EXPOSURE_PCT=5.0          # Max 5% daily exposure
RESOLUTION_CHECK_HOURS=1            # Check resolutions hourly
```

### Platform Configuration

```bash
# Kalshi (Recommended)
KALSHI_EMAIL=your_email@example.com
KALSHI_PASSWORD=your_password
KALSHI_API_BASE=https://trading-api.kalshi.com/trade-api/v2

# Polymarket (Optional)
POLYGON_WALLET_PRIVATE_KEY=0x...
CHAINSTACK_RPC_URL=https://polygon-mainnet...
OPENWEATHER_API_KEY=your_key
```

---

## 🚨 Risk Warnings

⚠️ **This bot trades real money on prediction markets:**

1. **Market Risk**: Extreme value betting requires high volume to be profitable. Individual trades have negative expected value by design.
2. **Validation Required**: **ALWAYS run 2-week simulation first** to validate win rate before risking real money.
3. **Oracle Risk**: Market resolutions could be incorrect or disputed.
4. **Liquidity Risk**: Small markets can have high slippage and low liquidity.
5. **API Risk**: API outages or rate limits could prevent trading.
6. **Regulatory Risk**: Prediction markets face regulatory uncertainty in many jurisdictions.

**Always start in simulation mode and validate performance before going live.**

---

## 📚 Additional Documentation

- **[Extreme Value Strategy Guide](EXTREME_VALUE_STRATEGY.md)** - Full strategy explanation
- **[P&L Tracking Guide](PNL_TRACKING.md)** - Database schema and tracking
- **[Simulation Guide](SIMULATION_GUIDE.md)** - 2-week validation process
- **[Architecture Map](ARCHITECTURE.md)** - Complete technical documentation
- **[Trader Analysis](TRADER_ANALYSIS.md)** - Successful trader patterns

---

## 🐛 Troubleshooting

### Bot won't start

```bash
# Check config
python bot.py config-check

# Check virtual environment
which python  # Should show .venv/bin/python

# Reinstall dependencies
pip install -r requirements.txt
```

### Can't see bot output in tmux

```bash
# Attach to tmux session
tmux attach -t bot

# Or check status without attaching
python bot.py bot-status --simulation
```

### Virtual environment not activated

```bash
# You'll see: ModuleNotFoundError: No module named 'typer'
# Fix: Always activate venv first
source .venv/bin/activate
```

### Database errors

```bash
# Reset simulation (deletes all simulation trades)
python scripts/reset_simulation.py --confirm

# Fix trade costs (if needed)
python scripts/fix_trade_costs.py
```

### Low win rate in simulation

- Check if daily trade limits are too restrictive
- Verify position sizes are correct (~$1 avg)
- Review recent trades for quality: `python bot.py trades --simulation --limit 20`
- Consider adjusting entry thresholds in `.env`

### Trades not resolving (stay pending)

**Symptom:** All trades show "pending" P&L, win rate stays 0%

**Possible causes:**
1. **Markets haven't closed yet** - Weather markets close after the forecast date
2. **Markets closed but not settled** - Kalshi settles 6-12 hours after close
3. **Resolution checker not running** - Check bot logs for "Checking for market resolutions"

**Check bot logs:**
```bash
tmux attach -t bot
# Look for: "Checking 20 open trades..."
# Should see this every hour
```

**Recent fixes (January 2026):**
- **Dual-mode resolution checker** - Different logic for simulation vs live
- **Simulation mode** - Now queries markets API instead of settlements API
- **Logging fixes** - File logging now works properly
- **Duplicate prevention** - Bot no longer trades same markets multiple times

**To get latest fixes:**
```bash
git pull origin main  # or your current branch
# Restart bot after pulling updates
```

---

## 🆕 Recent Improvements (January 2026)

### Duplicate Trade Prevention
The bot now tracks open positions and prevents duplicate trades on the same markets across multiple scans. This ensures each market is only traded once until it resolves.

### Location Injection in Questions
Market questions now include city names extracted from ticker codes:
- **Before:** "Will the minimum temperature be 15-16° on Jan 27, 2026?"
- **After:** "Will the minimum temperature in Denver be 15-16° on Jan 27, 2026?"

### Dual-Mode Resolution Checking
- **Simulation Mode:** Queries finalized markets via Kalshi markets API
- **Live Mode:** Uses Kalshi settlements API for real position settlements
- Ensures proper resolution tracking for both simulation and live trading

### Enhanced Logging
- Fixed file logging to ensure all bot activity is captured in `logs/bot.log`
- All modules now properly initialize with file logging enabled
- Easier debugging and monitoring of bot operations

### UI Improvements
- Wider Market column (60 chars) to show full temperature ranges
- YES/NO side display instead of just "BUY"
- Better status table formatting

---

## 📝 Development Status

### ✅ Implemented (v2.2 - January 2026)
- [x] Multi-platform support (Kalshi + Polymarket)
- [x] Automated bot runner with daemon mode
- [x] P&L tracking with SQLite database
- [x] Dual-mode resolution checking (simulation vs live)
- [x] Duplicate trade prevention (filters existing positions)
- [x] Location injection in market questions (city names from tickers)
- [x] Automatic resolution checking (hourly)
- [x] City diversification and risk management
- [x] Simplified CLI commands
- [x] VPS deployment support (tmux + systemd)
- [x] Position sizing optimization
- [x] Trade history and performance analytics
- [x] Comprehensive logging with file output

### 🚧 Future Enhancements
- [ ] Web dashboard for monitoring
- [ ] Telegram notifications
- [ ] Advanced backtesting framework
- [ ] Machine learning for entry optimization
- [ ] Multi-account support
- [ ] Docker deployment

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:

1. **Strategy Optimization**: Better entry/exit criteria
2. **Risk Management**: Advanced position sizing algorithms
3. **Performance**: Faster market scanning
4. **Monitoring**: Real-time dashboards
5. **Testing**: Unit and integration tests

---

## 📄 License

MIT License - see LICENSE file for details

---

## ⚠️ Disclaimer

This software is for educational and research purposes only. The authors are not responsible for any financial losses incurred through the use of this bot. Prediction market trading carries significant risk and may not be legal in all jurisdictions. Consult with legal and financial advisors before trading.

---

## 🙏 Acknowledgments

- **Kalshi** for prediction market API
- **Polymarket** for decentralized prediction markets
- **Chainstack** for Polygon infrastructure
- Inspired by successful traders: gopfan2, 0xaa7a74...

---

**Built with ❤️ for the prediction market community**
