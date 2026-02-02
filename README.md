# Polymarket Weather Bot

**Automated trading bot for Polymarket weather prediction markets using extreme value betting strategy.**

> **Current Status:** Polymarket-only, with automated bot runner, P&L tracking, and duplicate prevention.

---

## Strategy: Extreme Value Betting

The bot uses an **extreme value strategy** targeting mispriced weather markets:

- **Buy YES** when price is 3-12¢ (skip sub-3¢ traps)
- **Buy NO** when YES price > 50¢
- **Position sizes** of $1.50-$5.00 per trade
- **10% minimum edge** required from NWS weather forecasts
- **Quality over quantity** (10-25 trades/day max)

Weather forecasts from NWS (National Weather Service) provide the edge. Strict price discipline provides the payoff.

**[Read Full Strategy Guide →](docs/EXTREME_VALUE_STRATEGY.md)**

---

## Quick Start

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

**Required for Polymarket:**
```bash
POLYGON_WALLET_PRIVATE_KEY=your_wallet_private_key
CHAINSTACK_RPC_URL=https://polygon-mainnet.chainstacklabs.com/your_key
```

**Bot Configuration (optional):**
```bash
BANKROLL=1000.0                    # Total capital
SCAN_INTERVAL_HOURS=4              # How often to scan for trades
MAX_TRADES_PER_SCAN=10             # Trades per scan cycle
MAX_TRADES_PER_DAY=25              # Daily trade limit
MIN_EDGE_THRESHOLD=0.10            # 10% minimum edge required
MAX_DAILY_EXPOSURE_PCT=5.0         # Max 5% of bankroll at risk per day
```

### 3. Start the Bot

**Simulation Mode (recommended first):**
```bash
source .venv/bin/activate
python bot.py bot-start --simulation
```

The bot will:
- Scan for opportunities every 4 hours
- Execute up to 10 trades per scan
- Require 10% minimum edge from weather forecasts
- Use NWS as primary weather data source
- Check for resolutions every 15 minutes
- Track all trades in SQLite database

**Live Mode (after validation):**
```bash
python bot.py bot-start
```

### 4. Monitor Performance

**Check bot status:**
```bash
python bot.py bot-status --simulation
```

**View trade history:**
```bash
python bot.py trades --simulation --limit 50
```

**See P&L summary:**
```bash
python bot.py pnl --simulation
```

### 5. Stop the Bot

```bash
python bot.py bot-stop
```

---

## Running on a VPS (24/7 Operation)

### Using Tmux

**Start in background:**
```bash
tmux new -s bot
source .venv/bin/activate
python bot.py bot-start --simulation

# Detach: Press Ctrl+B, then D
```

**Check later:**
```bash
tmux attach -t bot
# Detach again: Ctrl+B, then D
```

**Stop:**
```bash
tmux attach -t bot
# Press Ctrl+C
exit
```

### Using Systemd (Production)

Create `/etc/systemd/system/trading-bot.service`:

```ini
[Unit]
Description=Polymarket Weather Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/polymarket-weather-bot
Environment="PATH=/path/to/polymarket-weather-bot/.venv/bin"
ExecStart=/path/to/polymarket-weather-bot/.venv/bin/python bot.py bot-start --simulation
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
```

---

## CLI Commands

### Bot Management

| Command | Description |
|---------|-------------|
| `bot-start [--simulation]` | Start automated bot |
| `bot-status [--simulation]` | Show performance summary |
| `bot-stop` | Stop running bot |

### Performance Tracking

| Command | Description |
|---------|-------------|
| `pnl [--simulation]` | P&L summary |
| `trades [--simulation] [--limit N]` | Trade history |
| `stats [--simulation]` | Detailed statistics |

### Wallet Analysis

| Command | Description |
|---------|-------------|
| `analyze-wallet <address>` | Reverse engineer strategy from wallet |
| `analyze-wallet <address> --show-trades` | Show individual trades |

### Utilities

| Command | Description |
|---------|-------------|
| `config-check` | Verify configuration |
| `balance` | Check USDC balance |
| `status` | Check portfolio |

---

## Architecture

```
bot/
├── application/
│   ├── bot_runner.py              # Automated daemon (main loop)
│   └── extreme_value_strategy.py  # Trading strategy logic
├── connectors/
│   ├── polymarket.py              # Polymarket API + Chainstack
│   └── weather.py                 # NWS weather connector
├── database/
│   └── trade_history.py           # P&L tracking system
├── cli/
│   └── cli.py                     # Command-line interface
├── analysis/
│   └── wallet_analyzer.py         # Wallet strategy analyzer
├── backtesting/
│   └── engine.py                  # Backtesting engine
└── utils/
    ├── config.py                  # Configuration management
    ├── logger.py                  # Logging utilities
    └── models.py                  # Data models

data/
└── trades.db                      # SQLite database (auto-created)

logs/
└── bot.log                        # Application logs (auto-created)

archive/                           # Archived code (Kalshi, legacy docs)
```

---

## Configuration Reference

### Strategy Parameters

```bash
# Edge Requirement
MIN_EDGE_THRESHOLD=0.10             # 10% minimum edge required

# Position Sizing
EXTREME_MIN_POSITION=1.50           # Minimum bet
EXTREME_MAX_POSITION=2.50           # Standard bet
EXTREME_AGGRESSIVE_MAX=5.00         # Maximum bet

# Entry Thresholds
EXTREME_YES_MIN_PRICE=0.03          # Skip sub-3¢ YES traps
EXTREME_YES_MAX_PRICE=0.12          # Buy YES if < 12¢
EXTREME_YES_IDEAL_PRICE=0.08        # Ideal YES price
EXTREME_NO_MIN_YES_PRICE=0.50       # Buy NO if YES > 50¢
EXTREME_NO_MIN_PRICE=0.03           # Skip sub-3¢ NO traps
```

### Bot Runner Configuration

```bash
BANKROLL=1000.0                     # Total capital
SCAN_INTERVAL_HOURS=4               # Scan frequency
MAX_TRADES_PER_SCAN=10              # Trades per scan
MAX_TRADES_PER_DAY=25               # Daily limit
MAX_TRADES_PER_CITY=2               # City diversification
MAX_DAILY_EXPOSURE_PCT=5.0          # Max daily exposure
```

### Polymarket Configuration

```bash
POLYGON_WALLET_PRIVATE_KEY=0x...    # Required
CHAINSTACK_RPC_URL=https://...      # Required
WALLET_ADDRESS=0x...                # Optional (derived from private key)
```

---

## Risk Warnings

**This bot trades real money on prediction markets:**

1. **Market Risk**: Extreme value betting requires volume to be profitable
2. **Validation Required**: Run 2-week simulation first before risking real money
3. **Oracle Risk**: Market resolutions could be incorrect or disputed
4. **Liquidity Risk**: Small markets can have high slippage
5. **API Risk**: API outages could prevent trading

**Always start in simulation mode and validate performance before going live.**

---

## Documentation

- **[Extreme Value Strategy Guide](docs/EXTREME_VALUE_STRATEGY.md)** - Full strategy explanation
- **[Architecture Map](docs/ARCHITECTURE.md)** - Technical documentation
- **[Configuration Guide](docs/CONFIGURATION.md)** - Detailed configuration options
- **[Changelog](docs/CHANGELOG.md)** - Version history

---

## Troubleshooting

### Bot won't start

```bash
python bot.py config-check
which python  # Should show .venv/bin/python
pip install -r requirements.txt
```

### Virtual environment not activated

```bash
# Fix: Always activate venv first
source .venv/bin/activate
```

### Trades not resolving

- Weather markets close after the forecast date
- Resolution checking runs every 15 minutes
- Check logs: `tail -f logs/bot.log`

---

## License

MIT License - see LICENSE file for details

---

## Disclaimer

This software is for educational and research purposes only. The authors are not responsible for any financial losses. Prediction market trading carries significant risk and may not be legal in all jurisdictions.

---

**Built for the prediction market community**
