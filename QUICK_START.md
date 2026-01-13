# Quick Start Guide

Get your Polymarket Weather Bot running in 5 minutes!

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Configure Environment

Create `.env` file from template:

```bash
cp .env.example .env
```

**Minimum required configuration** (edit `.env`):

```bash
# Your Polygon wallet private key (KEEP SECRET!)
POLYGON_WALLET_PRIVATE_KEY="0x..."

# Your Chainstack Polygon node endpoints
CHAINSTACK_RPC_URL="https://polygon-mainnet.core.chainstack.com/YOUR_KEY"
CHAINSTACK_WS_URL="wss://polygon-mainnet.core.chainstack.com/ws/YOUR_KEY"

# Free weather API key from https://openweathermap.org/api
OPENWEATHER_API_KEY="your_api_key_here"
```

### Getting API Keys

**Chainstack** (Polygon Node):
1. Sign up at https://chainstack.com
2. Create a new Polygon mainnet node
3. Copy the HTTP RPC and WebSocket URLs

**OpenWeatherMap** (Weather Data):
1. Sign up at https://openweathermap.org/api
2. Get free API key (1000 calls/day)
3. Copy the API key

## Step 3: Test Configuration

```bash
python bot.py config-check
```

You should see all green checkmarks ✓

## Step 4: Scan Markets (Simulation)

```bash
python bot.py scan --limit 10
```

This shows you the top 10 weather markets with trading opportunities. **No trades are executed.**

## Step 5: Run One Trading Cycle (Simulation)

```bash
python bot.py trade-once --dry-run
```

This will:
- Scan all Polymarket markets
- Filter for weather predictions
- Analyze with weather forecasts
- Show what trades it would make
- **NOT actually execute trades** (simulation mode)

Check the output to see what the bot found!

## Step 6: Check Status

```bash
python bot.py status
```

Shows your portfolio, recent trades (simulated), and performance.

## Step 7: Run Continuously (Simulation)

```bash
python bot.py run --interval 15 --dry-run
```

This runs the bot every 15 minutes in simulation mode. Perfect for:
- Testing the strategy
- Seeing what opportunities exist
- Verifying everything works
- Building confidence before going live

Press `Ctrl+C` to stop.

## Going Live (When Ready)

⚠️ **Only after thorough testing in simulation mode!**

### Run one live trade:
```bash
python bot.py trade-once --live
```

### Run continuously live:
```bash
python bot.py run --interval 15 --live
```

**The bot will ask for confirmation before executing real trades.**

## Important Notes

1. **Start Small**: Set `MAX_POSITION_SIZE_USDC=1.0` in `.env` to risk only $1 per trade
2. **Watch Carefully**: Monitor the first few hours closely
3. **Check Balance**: Run `python bot.py balance` to verify USDC available
4. **Read Logs**: Check `./logs/bot.log` for detailed information
5. **Stay in Simulation**: Test for at least 24 hours before going live

## Common Issues

### "Missing required configuration"
- Make sure you created `.env` file (not `.env.example`)
- Fill in all required fields

### "Failed to connect to Chainstack"
- Verify your Chainstack URLs are correct
- Check your Chainstack node is active
- Test with `curl -X POST $CHAINSTACK_RPC_URL -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'`

### "No weather markets found"
- This is normal! Weather markets are cyclical
- Try running `python bot.py scan` to see all markets
- Come back during active weather seasons

### "OpenWeather API failed"
- Verify API key is correct
- Check you haven't exceeded free tier limits (1000 calls/day)
- Wait a few minutes and try again

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Adjust trading parameters in `.env` (position sizes, thresholds, etc.)
- Set up Telegram alerts (optional)
- Add more weather APIs for better forecasts
- Monitor performance and iterate

## Support

Questions or issues?
- Check [README.md](README.md) for troubleshooting
- Open an issue on GitHub
- Review logs in `./logs/` directory

Happy trading! 🌤️📈
