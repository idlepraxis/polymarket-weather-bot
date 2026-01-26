# Polymarket Weather Bot: Complete Architecture Map

**Version:** 2.2.0 (Dual-Mode Resolution + Duplicate Prevention)
**Last Updated:** January 26, 2026
**Purpose:** Comprehensive program map for context preservation and future development

**New in v2.2:** Dual-mode resolution checking, duplicate prevention, location injection, logging fixes
**New in v2.1:** Automated bot runner with daemon mode, P&L tracking, and simplified CLI

---

## 📋 Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Data Flow](#data-flow)
3. [File-by-File Breakdown](#file-by-file-breakdown)
4. [Key Configuration Parameters](#key-configuration-parameters)
5. [Common Issues & Solutions](#common-issues--solutions)

---

## High-Level Architecture (v2.1 - Automated Bot)

```
┌─────────────────────────────────────────────────────────────┐
│                    USER / VPS                               │
│        Commands: bot-start, bot-status, bot-stop           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               CLI LAYER (bot/cli/cli.py)                    │
│  - Command routing (Typer)                                  │
│  - Status display (Rich tables)                             │
│  - 3 core commands for automated operation                  │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴──────────────┐
         │                              │
         ▼                              ▼
┌─────────────────────┐       ┌──────────────────────┐
│   BOT RUNNER        │◄─────►│  TRADE HISTORY DB    │
│  (bot_runner.py)    │       │  (trade_history.py)  │
│                     │       │                      │
│  DAEMON MODE:       │       │  - SQLite database   │
│  - Scan: 6 hours    │       │  - log_trade()       │
│  - Resolve: 1 hour  │       │  - update_resolution()│
│  - Daily resets     │       │  - get_pnl_summary() │
│  - Risk limits      │       │                      │
└──────────┬──────────┘       └──────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  EXTREME VALUE STRATEGY             │
│  (extreme_value_strategy.py)        │
│                                     │
│  Platform-Agnostic Logic:           │
│  - scan_for_opportunities()         │
│  - _check_yes_opportunity()         │
│  - _check_no_opportunity()          │
│  - Position sizing                  │
│  - City diversification             │
└──────────┬──────────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌──────────┐  ┌─────────────┐
│ KALSHI   │  │ POLYMARKET  │
│ CLIENT   │  │ CLIENT      │
└──────────┘  └─────────────┘
```

---

## Data Flow

### Automated Bot Flow (PRIMARY - v2.1)

```
1. USER → VPS
   python bot.py bot-start --simulation --platform kalshi

2. CLI → BotRunner.start()
   Enter main loop (runs indefinitely)

3. MAIN LOOP:
   Every 6 hours:
   ├→ Scan markets via KalshiClient.get_all_markets()
   ├→ Find opportunities via ExtremeValueStrategy
   ├→ Execute top 20 trades
   └→ Log each trade to TradeHistory database

   Every 1 hour:
   ├→ Check open trades for resolutions
   ├→ Calculate P&L for resolved trades
   └→ Update database

   Every 24 hours:
   └→ Reset daily counters (trades, exposure)

4. USER → Check Status
   python bot.py bot-status --simulation
   ├→ Get P&L summary from database
   └→ Display: trades, win rate, ROI, open positions
```

---

## File-by-File Breakdown

### Core Application Files

**bot/application/bot_runner.py** (600+ lines) ⭐ UPDATED in v2.2
- Automated daemon with main loop
- `start()` - Main loop (scan every 6h, resolve every 1h)
- `_scan_and_trade()` - Find and execute opportunities
- `_check_resolutions()` - Dual-mode: simulation vs live checking
- `_check_kalshi_markets_simulation()` - NEW: Query finalized markets
- `_check_kalshi_settlements()` - Query settlements for live trades
- `_filter_existing_positions()` - NEW: Prevent duplicate trades
- Enforces daily limits and risk management

**bot/application/extreme_value_strategy.py** (372 lines)
- Trading strategy logic (platform-agnostic)
- `scan_for_opportunities()` - Find YES < 15¢ or NO (YES > 40¢)
- `_calculate_position_size()` - Target ~$1 per trade
- Conservative probability estimation (2.5x multiplier)

**bot/database/trade_history.py** (400+ lines) ⭐ UPDATED in v2.2
- SQLite P&L tracking system
- `log_trade()` - Insert new trade
- `update_resolution()` - Mark trade as resolved with P&L
- `get_pnl_summary()` - Calculate win rate, ROI, total P&L
- `get_open_trades()` - Fetch unresolved positions
- `get_open_market_ids()` - NEW: Get markets with existing positions

### CLI & Interface

**bot/cli/cli.py** (600+ lines) - UPDATED in v2.1
- Command-line interface (Typer + Rich)
- NEW: `bot-start`, `bot-status`, `bot-stop` (simplified workflow)
- Legacy: `extreme-scan`, `extreme-trade` (still supported)
- Performance: `pnl`, `trades`, `stats` commands

### Platform Connectors

**bot/connectors/kalshi.py** (800+ lines) - UPDATED in v2.2
- Kalshi API integration with RSA-PSS auth
- `get_all_markets()` - Fetch ~72 weather markets
- `execute_limit_order()` - Place trades
- `get_market()` - Check resolution status
- `get_finalized_markets_by_series()` - NEW: Query settled markets by series
- `_extract_location_from_ticker()` - NEW: Parse city from ticker codes
- Location injection into market questions

**bot/connectors/polymarket.py** (900+ lines)
- Polymarket + Chainstack integration
- `get_all_markets()` - Fetch 1000+ markets
- `filter_weather_markets()` - Extract ~175 weather markets
- `batch_get_token_prices()` - Concurrent price fetching (5x faster)
- `execute_market_order()` - Place trades via CLOB API

### Configuration & Utilities

**bot/utils/config.py** (80+ lines) - UPDATED in v2.1
- Configuration management (loads .env)
- Made Polymarket fields optional for Kalshi-only usage
- Added bot runner config fields (scan interval, limits, etc.)
- Fixed position sizing defaults (1.50 instead of 5.00)

**bot/utils/models.py** (250+ lines)
- Pydantic data models
- `WeatherMarket` - Unified market representation
- `TradeSignal` - Trade opportunity
- `Trade` - Executed trade record

**bot/utils/logger.py** (100+ lines) - FIXED in v2.2
- Centralized logging configuration
- `get_logger()` - Global logger singleton with file logging
- `setup_logger()` - Configure handlers (console + file)
- FIXED: Now initializes with file handlers from first call
- Logs to console and logs/bot.log file

---

## Key Configuration Parameters

### Position Sizing (target ~$1 avg)
```bash
EXTREME_MIN_POSITION=0.50        # Min $0.50
EXTREME_MAX_POSITION=1.00        # Standard $1.00
EXTREME_AGGRESSIVE_MAX=1.50      # Max $1.50
```

### Bot Runner
```bash
BANKROLL=1000.0                  # Total capital
SCAN_INTERVAL_HOURS=6            # Scan every 6 hours
MAX_TRADES_PER_SCAN=20           # Trades per scan
MAX_TRADES_PER_DAY=50            # Daily limit
MAX_TRADES_PER_CITY=3            # City diversification
MAX_DAILY_EXPOSURE_PCT=5.0       # Max 5% daily risk
RESOLUTION_CHECK_HOURS=1         # Check resolutions hourly
```

### Entry Thresholds
```bash
EXTREME_YES_MAX_PRICE=0.15       # Buy YES if < 15¢
EXTREME_NO_MIN_YES_PRICE=0.40    # Buy NO if YES > 40¢
```

---

## Common Issues & Solutions

### Issue 1: Position Sizing Too High
**Symptom:** Trades averaging $3-5 instead of $1
**Fix:** Updated EXTREME_AGGRESSIVE_MAX to 1.50 (was 5.00)
**Files:** config.py, extreme_value_strategy.py, .env
**Commit:** 0b7c6f5

### Issue 2: Incorrect P&L Tracking
**Symptom:** Database shows costs 10x too low
**Fix:** Changed cost calculation from `size * price` to just `size`
**File:** bot_runner.py:287
**Commit:** c62de1e

### Issue 3: Config Validation Error
**Symptom:** `POLYGON_WALLET_PRIVATE_KEY Field required` for Kalshi-only
**Fix:** Made Polymarket fields Optional[str] = None
**File:** config.py
**Commit:** 2ad65aa

### Issue 4: ModuleNotFoundError on VPS
**Symptom:** `ModuleNotFoundError: No module named 'typer'`
**Fix:** Always activate venv: `source .venv/bin/activate`

### Issue 5: Bot Stops After SSH Disconnect
**Symptom:** Bot stops when terminal closes
**Fix:** Use tmux - detach with `Ctrl+B` then `D`

### Issue 6: Daily Counter Reset Every Minute (January 16, 2026)
**Symptom:** Logs show "Resetting daily counters" every minute
**Cause:** Date comparison against datetime.min (year 0001)
**Fix:** Track last_reset_date separately
**File:** bot_runner.py:99-107
**Commit:** 7cd09cf

### Issue 7: Resolution Checker - AttributeError (January 16, 2026)
**Symptom:** `'KalshiClient' object has no attribute 'base_url'`
**Cause:** Used wrong attribute name (base_url vs api_base)
**Fix:** Changed to self.client.api_base
**File:** bot_runner.py:375
**Commit:** f5fcdc5
**Impact:** CRITICAL - Resolution checking was 100% broken

### Issue 8: Resolution Checker - JSON Parsing (January 16, 2026)
**Symptom:** `argument of type 'Response' is not iterable`
**Cause:** Didn't parse httpx.Response object to dict
**Fix:** Call response.json() before accessing data
**File:** bot_runner.py:371-407
**Commit:** 86e08b7
**Impact:** CRITICAL - Resolution checking was 100% broken

### Issue 9: Settlements API Empty for Simulation (January 24-26, 2026)
**Symptom:** 0 resolved trades despite 80+ simulation trades placed
**Cause:** Settlements API only returns real positions (live mode), not simulation trades
**Fix:** Implemented dual-mode resolution checking
  - Simulation: Query markets API with `status=settled`
  - Live: Use settlements API for real positions
**Files:** bot_runner.py (added `_check_kalshi_markets_simulation()`)
          kalshi.py (added `get_finalized_markets_by_series()`)
**Commits:** Multiple during Phase 8-9
**Impact:** CRITICAL - Resolution checking 100% broken for simulation mode

### Issue 10: Duplicate Trades on Same Markets (January 25-26, 2026)
**Symptom:** Bot placing 80-120 trades/day despite only ~20 new markets
**Cause:** No duplicate prevention - every scan re-traded existing positions
**Fix:** Added `_filter_existing_positions()` to check database before trading
**Files:** bot_runner.py (added filter method)
          trade_history.py (added `get_open_market_ids()`)
**Impact:** HIGH - Wasting capital on duplicate positions

### Issue 11: Empty Log Files (January 25-26, 2026)
**Symptom:** logs/bot.log at 0 bytes despite bot running for days
**Cause:** Global logger initialized without file handlers
  - KalshiClient calls `get_logger()` first during import
  - Logger created with console-only handlers
  - Later calls to setup_logger had no effect (singleton already exists)
**Fix:** Modified `get_logger()` to always call `setup_logger(log_dir="logs")`
**File:** logger.py:98-103
**Impact:** HIGH - Impossible to debug issues without logs

### Issue 12: Missing Location in Market Questions (January 26, 2026)
**Symptom:** Questions show "Will the minimum temperature be 15-16°" without city
**Cause:** Kalshi API doesn't include city in question, only in ticker (KXLOWTDEN)
**Fix:** Added `_extract_location_from_ticker()` to parse city from ticker
  - Extracts city code (SEA, CHI, DEN, etc.)
  - Injects into question: "Will the minimum temperature in Denver be..."
**File:** kalshi.py (added location extraction and injection logic)
**Impact:** MEDIUM - UI clarity improvement

---

## Database Schema

```sql
CREATE TABLE trades (
    trade_id TEXT PRIMARY KEY,
    timestamp DATETIME,
    market_id TEXT,
    question TEXT,
    side TEXT,
    price REAL,
    size REAL,
    cost REAL,           -- FIXED in v2.1: equals size
    simulation INTEGER,  -- 0=live, 1=simulation
    platform TEXT,       -- 'kalshi' or 'polymarket'
    resolved INTEGER DEFAULT 0,
    won INTEGER,
    pnl REAL,
    resolution_date DATETIME,
    edge REAL,
    reasoning TEXT
);
```

---

## Performance Characteristics

- **Scan Interval:** 6 hours (configurable)
- **Resolution Check:** 1 hour (configurable)
- **Memory Usage:** ~50-100 MB
- **CPU Usage:** Minimal (sleeps between checks)
- **Database Size:** ~1 KB per trade

---

**Version:** 2.2.0
**Last Updated:** January 26, 2026
**Status:** Production - Running on VPS with dual-mode resolution, duplicate prevention, and location injection
