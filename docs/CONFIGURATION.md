# Configuration Guide

## Where Configuration Lives

### ✅ Single Source of Truth: `.env` File

**All your settings should go in `.env`** - this is your single source of truth.

```bash
# Edit this file
nano .env

# Or copy from example
cp .env.example .env
```

### How It Works

```
┌─────────────────────────────────────┐
│  YOU EDIT: .env                     │
│  BANKROLL=1000.0                    │
│  MAX_TRADES_PER_DAY=50              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  PYTHON READS: bot/utils/config.py  │
│  (has fallback defaults)            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  BOT USES: Final configuration      │
│  • If in .env → uses .env value ✅  │
│  • If NOT in .env → uses default ⚠️ │
└─────────────────────────────────────┘
```

---

## Configuration Priority (What Wins?)

1. **`.env` file** - Highest priority, ALWAYS wins
2. **Python defaults** (`bot/utils/config.py`) - Fallback if not in .env
3. **Command-line flags** - Override for single run (e.g., `--simulation`)

### Example

**Your `.env`:**
```bash
BANKROLL=2000.0
```

**Python default (`config.py`):**
```python
bankroll: float = Field(1000.0, alias="BANKROLL")
```

**Result:** Bot uses **$2000** (your .env wins!)

---

## Required vs Optional Settings

### ✅ REQUIRED (Bot won't work properly without these)

```bash
# Kalshi credentials - PICK ONE METHOD:
KALSHI_EMAIL=you@example.com          # Method 1: Email/password
KALSHI_PASSWORD=yourpassword

# OR
KALSHI_API_KEY_ID=your_key_id         # Method 2: API key (more secure)
KALSHI_API_PRIVATE_KEY=your_private_key

# Capital
BANKROLL=1000.0                       # How much money to trade with

# Weather API - AT LEAST ONE REQUIRED (free tiers available)
# NWS is used automatically (no key required) as primary source
OPENWEATHER_API_KEY=your_key          # https://openweathermap.org/api
# OR
WEATHERAPI_KEY=your_key               # https://www.weatherapi.com/
# Optional: NOAA for additional data
NOAA_API_KEY=your_key                 # https://www.ncdc.noaa.gov/cdo-web/
```

> ⚠️ **CRITICAL**: Without a weather API key, the bot cannot calculate real probabilities and will skip all trades. The strategy requires actual weather forecasts to identify mispricings.

### ⚙️ RECOMMENDED (Should set these, but have defaults)

```bash
# Position sizing (increased in v2.4.0 for fewer, larger trades)
EXTREME_MIN_POSITION=1.50             # Default: 1.50 (was 0.50)
EXTREME_MAX_POSITION=2.50             # Default: 2.50 (was 1.00)
EXTREME_AGGRESSIVE_MAX=5.00           # Default: 5.00 (was 1.50)

# Trading frequency (reduced in v2.4.0 for quality over quantity)
SCAN_INTERVAL_HOURS=4                 # Default: 4 (was 6)
MAX_TRADES_PER_SCAN=10                # Default: 10 (was 20)
MAX_TRADES_PER_DAY=25                 # Default: 25 (was 50)
```

### 📝 OPTIONAL (Can omit, will use defaults)

```bash
# Logging
LOG_LEVEL=INFO                        # Default: INFO

# Data storage
CACHE_DIR=./data/cache                # Default: ./data/cache
LOG_DIR=./logs                        # Default: ./logs
```

---

## What Settings Actually Do

### Capital & Risk

| Setting | What It Does | Example |
|---------|--------------|---------|
| `BANKROLL` | Total capital for trading | `1000.0` = $1,000 |
| `MAX_DAILY_EXPOSURE_PCT` | Max % at risk per day | `5.0` = max $50/day risk |

### Position Sizing (Per Trade)

| Setting | What It Does | When Used |
|---------|--------------|-----------|
| `EXTREME_MIN_POSITION` | Minimum bet size | Weak opportunities (12-15¢) |
| `EXTREME_MAX_POSITION` | Standard bet size | Good opportunities (8-10¢) |
| `EXTREME_AGGRESSIVE_MAX` | Maximum bet size | Great opportunities (≤5¢) |

**Target:** ~$1.00 average per trade

### Trading Frequency

| Setting | What It Does | Recommendation |
|---------|--------------|----------------|
| `SCAN_INTERVAL_HOURS` | How often to scan for trades | 6 hours (daily temp markets) |
| `RESOLUTION_CHECK_HOURS` | How often to check resolutions | 1 hour (catch resolutions quickly) |

### Trade Limits

| Setting | What It Does | Why |
|---------|--------------|-----|
| `MAX_TRADES_PER_SCAN` | Trades per scan cycle | Prevents over-trading in one scan |
| `MAX_TRADES_PER_DAY` | Daily trade limit | Safety cap, risk management |
| `MAX_TRADES_PER_CITY` | Max per city | Diversification across cities |

### Entry Thresholds

| Setting | What It Does | Default |
|---------|--------------|---------|
| `EXTREME_YES_MAX_PRICE` | Only buy YES if price below this | 0.12 (12¢) |
| `EXTREME_YES_IDEAL_PRICE` | Ideal price for YES trades | 0.08 (8¢) |
| `EXTREME_NO_MIN_YES_PRICE` | Only buy NO if YES above this | 0.50 (50¢) |
| `EXTREME_NO_IDEAL_YES_PRICE` | Ideal YES price for NO trades | 0.60 (60¢) |
| `MIN_EDGE_THRESHOLD` | Minimum edge required to trade | 0.10 (10%) |

> **Note on NO threshold**: Buying NO when YES > 60% means NO costs < 40¢, giving a 1.5x+ payoff ratio. The old 40% threshold resulted in buying NO at 55-60¢ (terrible 0.8x payoff).

---

## Legacy Settings (Ignored by v2.1)

These are from the old forecast-based strategy and **NOT used** by the automated bot:

```bash
MAX_POSITION_SIZE_USDC=5.0      # OLD - use EXTREME_AGGRESSIVE_MAX
BANKROLL_USDC=1000.0            # OLD - use BANKROLL
MIN_EDGE_THRESHOLD=0.05         # OLD - not used in extreme value
MIN_CONFIDENCE=0.70             # OLD - not used in extreme value
POSITION_SIZE_PCT=0.01          # OLD - not used in extreme value
MAX_OPEN_POSITIONS=20           # OLD - not enforced in v2.1
POLL_INTERVAL_MINUTES=15        # OLD - use SCAN_INTERVAL_HOURS
```

**Why keep them?** Backward compatibility with old code that's still in the codebase but not actively used.

---

## Common Configuration Scenarios

### Scenario 1: Conservative (Low Risk)

```bash
BANKROLL=500.0                    # Smaller bankroll
EXTREME_MIN_POSITION=0.25         # Smaller bets
EXTREME_MAX_POSITION=0.50
EXTREME_AGGRESSIVE_MAX=0.75
MAX_TRADES_PER_DAY=30             # Fewer trades
MAX_DAILY_EXPOSURE_PCT=3.0        # Lower exposure (3%)
```

**Expected:** ~$0.50 avg/trade, 15-30 trades/day, $7.50-15/day exposure

### Scenario 2: Recommended (Balanced) - v2.4.0 Defaults

```bash
BANKROLL=1000.0                   # $1k bankroll
EXTREME_MIN_POSITION=1.50         # Larger positions, fewer trades
EXTREME_MAX_POSITION=2.50
EXTREME_AGGRESSIVE_MAX=5.00
MAX_TRADES_PER_DAY=25             # Quality over quantity
MAX_DAILY_EXPOSURE_PCT=5.0        # 5% risk
SCAN_INTERVAL_HOURS=4             # 6 scans/day
MIN_EDGE_THRESHOLD=0.10           # 10% minimum edge
```

**Expected:** ~$2.50 avg/trade, 10-15 trades/day, $25-40/day exposure

### Scenario 3: Aggressive (Higher Volume)

```bash
BANKROLL=2000.0                   # Larger bankroll
EXTREME_MIN_POSITION=1.00         # Larger bets
EXTREME_MAX_POSITION=2.00
EXTREME_AGGRESSIVE_MAX=3.00
MAX_TRADES_PER_DAY=100            # More trades
MAX_DAILY_EXPOSURE_PCT=10.0       # Higher exposure (10%)
SCAN_INTERVAL_HOURS=4             # Scan more often
```

**Expected:** ~$2.00 avg/trade, 40-60 trades/day, $80-120/day exposure

---

## Checking Your Configuration

### Option 1: View your .env

```bash
cat .env | grep -E "^[A-Z_]+=" | grep -v "^#"
```

### Option 2: Use config-check command

```bash
python bot.py config-check
```

This will show:
- Which credentials are set
- Which values are defaults vs customized
- Any warnings about missing required fields

---

## Troubleshooting

### Issue: "Bot is using wrong position sizes"

**Check:**
1. What's in your `.env`?
   ```bash
   grep EXTREME .env
   ```

2. Are you editing the right file?
   ```bash
   ls -la .env .env.example
   ```

3. Did you restart the bot after changing .env?
   ```bash
   # Stop bot
   tmux attach -t bot
   Ctrl+C

   # Restart bot (reloads .env)
   python bot.py bot-start --simulation --platform kalshi
   ```

### Issue: "Bot uses defaults, ignores my .env"

**Cause:** Typo in setting name or .env not in correct location

**Fix:**
1. Check spelling in .env matches exactly:
   ```bash
   BANKROLL=1000.0           ✅ Correct
   Bankroll=1000.0           ❌ Wrong (lowercase)
   BANKROL=1000.0            ❌ Wrong (missing L)
   ```

2. Confirm .env is in project root:
   ```bash
   pwd
   # Should be: /root/trading-bots/polymarket-weather-bot

   ls -la .env
   # Should exist
   ```

### Issue: "Which BANKROLL setting is used?"

**Answer:** Only `BANKROLL` is used in v2.1

- `BANKROLL` - **Current** (v2.1 bot runner)
- `BANKROLL_USDC` - **Legacy** (old forecast strategy)

Both can coexist, but bot uses `BANKROLL`.

---

## Best Practices

### ✅ DO

- Keep `.env` as your single source of truth
- Comment your changes in .env
- Test with simulation first
- Document non-standard configurations

### ❌ DON'T

- Don't edit `bot/utils/config.py` Python defaults
- Don't hardcode values in Python code
- Don't commit `.env` to git (use `.env.example`)
- Don't change config while bot is running

---

## Summary: Simple Rules

1. **All settings go in `.env`** (single source of truth)
2. **Python defaults are fallbacks** (don't edit these)
3. **Restart bot after .env changes** (reload config)
4. **When in doubt, check .env.example** (comprehensive reference)

That's it! Configuration is now straightforward. 🎉
