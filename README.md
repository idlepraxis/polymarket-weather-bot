# Polymarket Weather Bot

Automated trading bot for Polymarket weather prediction markets using Chainstack infrastructure.

## Features

- 🌤️ **Weather Market Scanning**: Automatically identifies temperature and weather-related prediction markets
- 🔮 **Ensemble Forecasting**: Combines multiple weather APIs (OpenWeather, WeatherAPI, NOAA) for accurate predictions
- 🎯 **Edge Detection**: Calculates fair probabilities and identifies mispriced markets
- 💰 **Risk Management**: Kelly Criterion position sizing, daily trade limits, stop-loss protection
- 🔐 **Chainstack Integration**: Uses private Polygon node for fast, secure blockchain access
- 🧪 **Simulation Mode**: Test strategies risk-free before going live
- 📊 **Portfolio Tracking**: Track positions, P&L, and performance metrics
- 🎨 **Rich CLI**: Beautiful command-line interface with tables and colors

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/idlepraxis/polymarket-weather-bot.git
cd polymarket-weather-bot

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required configuration:
- `POLYGON_WALLET_PRIVATE_KEY`: Your Polygon wallet private key
- `CHAINSTACK_RPC_URL`: Chainstack Polygon RPC endpoint
- `CHAINSTACK_WS_URL`: Chainstack WebSocket endpoint
- `OPENWEATHER_API_KEY`: OpenWeatherMap API key (free tier available)

Optional but recommended:
- `TELEGRAM_BOT_TOKEN`: For trade alerts
- `WEATHERAPI_KEY`: Additional weather data source
- `NOAA_API_KEY`: US weather data

### 3. Verify Setup

```bash
python bot.py config-check
```

### 4. Run in Simulation Mode

```bash
# Scan markets without trading
python bot.py scan

# Run one trading cycle (simulation)
python bot.py trade-once --dry-run

# Run continuously (simulation)
python bot.py run --interval 15 --dry-run
```

### 5. Go Live (when ready)

```bash
# Single cycle with real trades
python bot.py trade-once --live

# Continuous trading
python bot.py run --interval 15 --live
```

## CLI Commands

### Status & Monitoring

```bash
# Check portfolio and recent trades
python bot.py status

# Check USDC balance
python bot.py balance

# Verify configuration
python bot.py config-check
```

### Trading

```bash
# Scan markets and show opportunities
python bot.py scan --limit 10 --min-edge 0.05

# Execute one trading cycle
python bot.py trade-once [--dry-run|--live]

# Run continuously
python bot.py run --interval 15 --max-cycles 100 [--dry-run|--live]
```

### Options

- `--dry-run`: Simulation mode (default, safe)
- `--live`: Live trading mode (real money at risk)
- `--interval N`: Minutes between cycles (default: 15)
- `--max-cycles N`: Stop after N cycles (0 = unlimited)
- `--limit N`: Max results to show
- `--min-edge X`: Minimum edge threshold

## How It Works

### 1. Market Scanning
The bot scans all Polymarket markets via the Gamma API and filters for weather-related predictions (temperature, rain, snow, etc.).

### 2. Weather Analysis
For each market:
- Extracts location, date, and threshold from the market question
- Fetches weather forecasts from multiple sources
- Calculates fair probability using ensemble forecasting
- Applies probabilistic models with uncertainty

### 3. Edge Calculation
```
Edge = Fair Probability - Market Price
```
Only trades when edge exceeds threshold (default: 5%)

### 4. Position Sizing
Uses fractional Kelly Criterion:
```
Position Size = Bankroll × Position % × (Edge × Confidence)
```
With limits:
- Max position size: $5 (configurable)
- Max daily trades: 50
- Max open positions: 20

### 5. Order Execution
- Uses Polymarket CLOB API for order placement
- Routes through Chainstack private node for speed and privacy
- Supports both limit and market orders
- Includes retry logic for failed transactions

## Architecture

```
bot/
├── application/
│   └── trader.py          # Main trading logic
├── connectors/
│   ├── polymarket.py      # Polymarket + Chainstack integration
│   └── weather.py         # Weather API connector
├── utils/
│   ├── config.py          # Configuration management
│   ├── logger.py          # Logging utilities
│   └── models.py          # Pydantic data models
└── cli/
    └── cli.py             # Typer CLI interface
```

## Configuration Reference

### Trading Parameters

```bash
MAX_POSITION_SIZE_USDC=5.0       # Max bet per trade
MIN_EDGE_THRESHOLD=0.05          # Min 5% edge to trade
MIN_CONFIDENCE=0.70              # Min forecast confidence
MAX_DAILY_TRADES=50              # Daily trade limit
MAX_OPEN_POSITIONS=20            # Max concurrent positions
```

### Risk Management

```bash
BANKROLL_USDC=1000.0             # Total capital
POSITION_SIZE_PCT=0.01           # 1% per trade (Kelly)
STOP_LOSS_PCT=0.50               # Stop if down 50%
```

### Bot Behavior

```bash
POLL_INTERVAL_MINUTES=15         # Scan frequency
SIMULATION_MODE=true             # Safe by default
LOG_LEVEL=INFO                   # Logging verbosity
```

## Strategy Details

### Weather Probability Model

For temperature thresholds:
1. Fetches forecast from multiple sources
2. Averages predictions (ensemble)
3. Applies ±5°F uncertainty (normal distribution)
4. Calculates probability using error function

Example:
- Forecast: 75°F high
- Threshold: 70°F
- Probability = 84% (1 std dev above)

### Trade Selection

Signals ranked by:
1. **Edge**: Higher is better
2. **Confidence**: Higher is better
3. **Liquidity**: Prefer liquid markets

### Exit Strategy

Currently manual exits at resolution. Future enhancements:
- Auto-close before resolution
- Stop-loss on unrealized losses
- Take-profit at target returns

## Risk Warnings

⚠️ **This bot trades real money on prediction markets:**

1. **Market Risk**: Weather forecasts are probabilistic, not guaranteed
2. **Oracle Risk**: Polymarket uses UMA oracle which could resolve incorrectly
3. **Liquidity Risk**: Small markets can have high slippage
4. **Smart Contract Risk**: Bugs in Polymarket contracts could cause losses
5. **Regulatory Risk**: Prediction markets face regulatory uncertainty

**Always start in simulation mode and test thoroughly before risking real funds.**

## Performance Expectations

Based on analysis of successful traders (e.g., 0xaa7a74...):

- **Expected Win Rate**: 55-65%
- **Average Edge**: 2-8% per trade
- **ROI Target**: 50-100% annually on small capital (<$10k)
- **Daily Trades**: 5-20 on typical days
- **Position Sizes**: $1-5 per bet (micro-stakes strategy)

**Note**: Past performance does not guarantee future results.

## Development Status

### ✅ Implemented (v1.0)
- [x] Project structure and configuration
- [x] Chainstack Polygon integration
- [x] Weather API connectors (OpenWeather, WeatherAPI)
- [x] Market scanning and filtering
- [x] Edge calculation and signal generation
- [x] Order execution (limit & market)
- [x] Simulation mode
- [x] Portfolio tracking
- [x] Risk management (position sizing, limits)
- [x] CLI interface with Rich formatting
- [x] Logging and error handling

### 🚧 Planned (v1.1)
- [ ] Telegram alerts integration
- [ ] Position management (auto-close, monitoring)
- [ ] Advanced weather models (ML, NOAA full integration)
- [ ] Backtesting framework
- [ ] Performance analytics dashboard
- [ ] Database storage (SQLite/Postgres)

### 🔮 Future (v2.0)
- [ ] Multi-market support (non-weather markets)
- [ ] Market making strategies
- [ ] Arbitrage detection
- [ ] Web UI for monitoring
- [ ] Docker deployment

## Troubleshooting

### Connection Errors

```bash
# Test Chainstack connection
curl -X POST $CHAINSTACK_RPC_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

### Weather API Issues

```bash
# Test OpenWeather API
curl "http://api.openweathermap.org/data/2.5/weather?q=New%20York&appid=$OPENWEATHER_API_KEY"
```

### Low Trade Volume

- Decrease `MIN_EDGE_THRESHOLD` (e.g., 0.03 instead of 0.05)
- Increase `POLL_INTERVAL_MINUTES` to scan more frequently
- Add more weather APIs for better ensemble forecasts

### High Error Rate

- Check logs in `./logs/` directory
- Verify API keys are valid
- Ensure sufficient USDC balance
- Check Polygon network status

## Contributing

Contributions welcome! Areas for improvement:

1. **Weather Models**: Better probability calculations
2. **Market Parsing**: Improved question parsing
3. **Exit Strategies**: Position management logic
4. **Testing**: Unit and integration tests
5. **Documentation**: More examples and guides

## License

MIT License - see LICENSE file for details

## Disclaimer

This software is for educational and research purposes only. The authors are not responsible for any financial losses incurred through the use of this bot. Prediction market trading carries significant risk and may not be legal in all jurisdictions. Consult with legal and financial advisors before trading.

## Support

- **Issues**: https://github.com/idlepraxis/polymarket-weather-bot/issues
- **Author**: [@idlepraxis](https://github.com/idlepraxis)

## Acknowledgments

- Polymarket team for the platform and APIs
- Chainstack for reliable Polygon infrastructure
- Weather API providers (OpenWeather, WeatherAPI, NOAA)
- Inspired by successful traders like gopfan2 and 0xaa7a74...

---

Built with ❤️ for the Polymarket community
