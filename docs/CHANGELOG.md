# Changelog

All notable changes to the Polymarket Weather Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.5.2] - 2026-02-02

### Changed
- **INVERTED position sizing logic**: Bet MORE on proven winners, LESS on traps
  - Old logic: Cheaper prices → larger positions (backwards!)
  - New logic: Bet based on actual win rate data

  **YES Position Sizing (inverted):**
  | Price Range | Old Size | New Size | Rationale |
  |-------------|----------|----------|-----------|
  | 3-5¢ | $5.00 | $1.50 | 0% historical win rate - traps |
  | 5-8¢ | $5.00 | $2.50 | 18% win rate + great payoff |
  | 8-10¢ | $2.50 | $2.50 | Decent performance |
  | 10-12¢ | $1.88 | $5.00 | **Best win rate (20%)** |
  | >12¢ | $1.50 | $1.50 | Lower payoff ratio |

  **NO Position Sizing (inverted):**
  | NO Price | Old Size | New Size | Rationale |
  |----------|----------|----------|-----------|
  | <10¢ | $5.00 | $1.50 | Trap (YES >90%) |
  | 10-30¢ | $5.00 | $1.50 | Risky |
  | 30-40¢ | $2.50 | $2.50 | Good sweet spot |
  | 40-45¢ | $2.50 | $5.00 | Best balance |
  | 45-50¢ | $1.50 | $2.50 | Moderate payoff |

### Analysis
Trade data showed position sizing was backwards:
- $5.00 trades: 9.1% win rate, -$39.62 loss
- $2.50 trades at <5¢: 0% win rate, -$122.50 loss
- $1.12 trades: 20% win rate, +$5.07 profit (only profitable bucket!)

The 10-12¢ range had 20% win rate but was getting smallest positions.

---

## [2.5.1] - 2026-02-02

### Added
- **Minimum NO price floor (3¢)**: Skip sub-3¢ NO trades (same logic as YES minimum)
  - New config: `EXTREME_NO_MIN_PRICE=0.03`
  - If YES is 97%+, NO costs only 3¢ - these are traps just like cheap YES trades
  - Analysis showed a 0.5¢ NO trade slipped through the previous filters

### Technical Details

#### Files Modified
- `bot/utils/config.py`:
  - Added `extreme_no_min_price` (default 0.03)
- `bot/application/extreme_value_strategy.py`:
  - Added minimum price check in `_check_no_opportunity()`

---

## [2.5.0] - 2026-02-02

### Added
- **Minimum price floor (3¢)**: Skip sub-3¢ trades that have 0% historical win rate
  - New config: `EXTREME_YES_MIN_PRICE=0.03`
  - Analysis showed 28 trades <3¢ with 0 wins and -$70 loss
- **Trade type preferences**: Prioritize proven profitable trade types
  - New config: `PREFER_NO_ON_RANGE=true` - NO bets on range markets have 18.2% win rate
  - New config: `SKIP_YES_ON_THRESHOLD=false` - Optionally skip YES threshold bets (4% win rate)
  - Signals now sorted by trade type priority, then by EV
- **NWS-only mode**: Use NWS exclusively when available
  - New config: `PREFER_NWS_ONLY=true`
  - Kalshi uses NWS station data for resolution; ensemble averaging introduced bias

### Changed
- **Increased forecast uncertainty (std_dev)**: 4.0°F → 7.0°F
  - Analysis showed actual forecast errors of 6-10°F
  - 97% fair probability trades were losing due to overconfidence
  - New std_dev produces more conservative probability estimates
- **Disabled ensemble by default**: `ENABLE_ENSEMBLE_MODELS=false`
  - WeatherAPI/OpenWeather temps were 1-2°F higher than NWS station data
  - This bias caused systematic losses on threshold markets

### Fixed
- **Probability calibration**: High fair probability estimates (70-97%) had near-0% actual win rate
  - Root cause: Forecasts systematically differed from Kalshi's NWS resolution data
  - Fix: NWS-only mode + higher std_dev produces calibrated probabilities

### Analysis Summary (v2.4.0 Results)
Based on 84 simulation trades:

| Segment | Trades | Wins | Win Rate | P&L |
|---------|--------|------|----------|-----|
| Entry <3¢ | 28 | 0 | 0.0% | -$70.00 |
| Entry 3-6¢ | 11 | 1 | 9.1% | +$17.95 |
| Entry >10¢ | 13 | 2 | 15.4% | +$3.81 |
| NO on RANGE | 11 | 2 | 18.2% | +$34.69 |
| YES on THRESHOLD | 24 | 1 | 4.2% | -$42.19 |

### Technical Details

#### Files Modified
- `bot/utils/config.py`:
  - Added `extreme_yes_min_price` (default 0.03)
  - Added `prefer_no_on_range` (default True)
  - Added `skip_yes_on_threshold` (default False)
  - Added `prefer_nws_only` (default True)
  - Changed `enable_ensemble_models` default to False
- `bot/application/extreme_value_strategy.py`:
  - Added minimum price check in `_check_yes_opportunity()`
  - Added threshold market skip option
  - Updated `scan_for_opportunities()` to prioritize NO/RANGE trades
- `bot/connectors/weather.py`:
  - Increased `std_dev` from 4.0 to 7.0 in both probability functions
  - Added NWS-only mode in `get_forecast()`

#### Configuration Changes
| Parameter | Old Value | New Value |
|-----------|-----------|-----------|
| `EXTREME_YES_MIN_PRICE` | (none) | 0.03 |
| `PREFER_NO_ON_RANGE` | (none) | true |
| `PREFER_NWS_ONLY` | (none) | true |
| `ENABLE_ENSEMBLE_MODELS` | true | false |
| Forecast std_dev | 4.0°F | 7.0°F |

---

## [2.4.0] - 2026-01-31

### Added
- **NWS (National Weather Service) API integration**: Primary weather data source
  - Official US government weather source, likely matches Kalshi's resolution data
  - Weighted ensemble with 2x weight for NWS over other sources
  - Falls back to OpenWeatherMap and WeatherAPI.com when NWS unavailable
- **Negative temperature support**: Parser now handles sub-zero markets
  - Regex patterns updated to match `-?\d+` for temps like `<-1°` and `-1-0°`
  - Added comprehensive tests for negative threshold and range markets

### Fixed
- **CRITICAL**: Threshold direction ignored in probability calculation
  - `calculate_probability()` always calculated P(temp > threshold)
  - For `<49°` markets, this meant betting with inverted probabilities
  - Added `direction` parameter: `"above"` or `"below"`
  - This bug caused near 100% loss rate on threshold markets
- **CRITICAL**: Fallback heuristic assumed edge without data
  - Old behavior: Assumed 2.5x edge when no weather forecast available
  - New behavior: Only trades when real weather data provides actual edge
  - Audit showed 4.8% win rate (1/21) partly due to this flaw
- **CRITICAL**: Zero threshold treated as missing
  - Python's `not 0.0` evaluates to `True`, causing `<0°` markets to be skipped
  - Changed to explicit `is None` check for threshold validation

### Changed
- **Increased min_edge_threshold**: 5% → 10%
  - Higher quality trades only, reduces noise
- **Reduced trading volume**:
  - `max_trades_per_day`: 50 → 25
  - `max_trades_per_scan`: 20 → 10
  - `max_trades_per_city`: 3 → 2
- **Increased position sizes** (compensate for fewer trades):
  - `extreme_min_position`: $0.50 → $1.50
  - `extreme_max_position`: $1.00 → $2.50
  - `extreme_aggressive_max`: $1.50 → $5.00
- **Tighter price thresholds**:
  - `extreme_yes_max_price`: 0.15 → 0.12
  - `extreme_yes_ideal_price`: 0.10 → 0.08
  - `extreme_no_min_yes_price`: 0.40 → 0.50
  - `extreme_no_ideal_yes_price`: 0.50 → 0.60
- **More frequent scans**: `scan_interval_hours`: 6 → 4

### Technical Details

#### Files Modified
- `bot/connectors/weather.py`:
  - Added NWS API client with weighted ensemble averaging
  - Updated regex patterns for negative temperature parsing
  - Added `direction` parameter to `calculate_probability()`
- `bot/application/extreme_value_strategy.py`:
  - Removed fallback heuristic probability estimation
  - Pass `threshold_direction` to probability calculation
  - Fixed zero threshold check (`is None` instead of truthiness)
- `bot/utils/config.py`:
  - Updated all trading parameter defaults
  - Added `NOAA_API_KEY` configuration option

#### Configuration Changes
| Parameter | Old Value | New Value |
|-----------|-----------|-----------|
| `MIN_EDGE_THRESHOLD` | 0.05 | 0.10 |
| `MAX_TRADES_PER_DAY` | 50 | 25 |
| `MAX_TRADES_PER_SCAN` | 20 | 10 |
| `EXTREME_MIN_POSITION` | 0.50 | 1.50 |
| `EXTREME_MAX_POSITION` | 1.00 | 2.50 |
| `EXTREME_YES_MAX_PRICE` | 0.15 | 0.12 |
| `EXTREME_NO_MIN_YES_PRICE` | 0.40 | 0.50 |

---

## [2.3.0] - 2026-01-29

### Added
- **Kalshi market format parser**: Properly parses Kalshi-specific question formats
  - Range markets: "48-49°", "56° to 57°"
  - Threshold markets: ">13°", "<13°"
  - Date formats: "Jan 27, 2026"
- **Range probability calculation**: New `calculate_range_probability()` method
  - Calculates P(temp falls within X-Y°) using normal distribution
  - Enables accurate probability estimates for Kalshi's bucket-style markets
- **Weather API integration**: Real weather forecasts now drive probability estimates
  - Supports OpenWeatherMap API (free tier)
  - Supports WeatherAPI.com as backup
  - Ensemble averaging when multiple APIs configured

### Fixed
- **CRITICAL**: Strategy was betting blind without actual weather data
  - Parser couldn't extract temperature thresholds from Kalshi format
  - Fell back to hardcoded 35%/65% probability estimates
  - Now uses real weather forecasts for probability calculation
- **CRITICAL**: NO trade threshold was too low (45% → 60%)
  - Old threshold: Buy NO when YES > 45% (NO costs 55¢, terrible 0.8x payoff)
  - New threshold: Buy NO when YES > 60% (NO costs 40¢, good 1.5x payoff)
  - This was causing systematic losses on NO trades
- **CRITICAL**: Conservative fallback assumed fake edge
  - Old behavior: When no forecast available, assumed 35% fair prob for YES
  - New behavior: Returns market price (no edge = skip trade)
  - Prevents betting without actual information advantage

### Changed
- Weather API keys now **REQUIRED** for strategy to function
  - `OPENWEATHER_API_KEY` or `WEATHERAPI_KEY` must be set
  - Without weather data, bot will skip trades (no fake edge)
- Updated default NO threshold from 0.45 to 0.60
- Parser now returns `is_range`, `range_low`, `range_high` fields
- Improved debug logging for probability calculations

### Technical Details

#### Files Modified
- `bot/connectors/weather.py`:
  - Rewrote `parse_market_question()` to handle Kalshi formats
  - Added `calculate_range_probability()` for bucket markets
  - Added support for "Jan 27, 2026" date format
- `bot/application/extreme_value_strategy.py`:
  - Updated `_estimate_fair_probability()` to use range calculations
  - Fixed `_conservative_estimate()` to not assume fake edge
  - Added debug logging for probability estimates

#### Configuration Changes
- `EXTREME_NO_MIN_YES_PRICE`: Default changed from 0.45 to 0.60
- `EXTREME_NO_IDEAL_YES_PRICE`: Default changed from 0.55 to 0.70
- `OPENWEATHER_API_KEY`: Now required (was optional)

---

## [2.2.0] - 2026-01-26

### Added
- **Dual-mode resolution checking**: Different resolution logic for simulation vs live mode
  - Simulation mode: Queries Kalshi markets API with `status=settled` parameter
  - Live mode: Uses Kalshi settlements API for real position settlements
  - Fixes critical bug where simulation trades never resolved
- **Duplicate trade prevention**: Bot now tracks open positions and filters them before trading
  - Added `get_open_market_ids()` to trade_history.py
  - Added `_filter_existing_positions()` to bot_runner.py
  - Prevents re-trading same markets across multiple scans
- **Location injection in market questions**: City names now appear in questions
  - Added `_extract_location_from_ticker()` to parse city codes from tickers
  - Questions now show "in Denver" instead of just temperature ranges
  - Improved UI clarity and trade identification
- **Enhanced logging system**: File logging now works properly
  - Modified `get_logger()` to initialize with file handlers from first call
  - All bot activity now captured in `logs/bot.log`
  - Easier debugging and monitoring
- **Diagnostic scripts** (in `scripts/` directory):
  - `scripts/check_recent_trades.py`: Inspect database for duplicates and trade details
  - `scripts/check_kalshi_questions.py`: Test location injection and API responses

### Fixed
- **CRITICAL**: Resolution checker not working for simulation mode (Phase 8-9)
  - Settlements API only returns real positions, not simulation trades
  - Implemented markets API fallback for simulation mode
  - Resolution checking now works for both simulation and live trading
- **CRITICAL**: Empty log files despite bot running
  - Global logger singleton was initialized without file handlers
  - Fixed initialization order to ensure file logging always enabled
  - Bot activity now properly logged to `logs/bot.log`
- **HIGH**: Duplicate trades on same markets
  - Bot was re-trading existing positions every 6-hour scan
  - 80-120 trades/day despite only ~20 new markets available
  - Added position filtering to prevent duplicates
- **MEDIUM**: Missing city names in market questions
  - Kalshi API doesn't include city in question text
  - Added ticker parsing and location injection
  - Questions now show full context with city names

### Changed
- UI improvements:
  - Increased Market column width from 40 to 60 characters
  - Show YES/NO side instead of just "BUY" in trade tables
  - Better formatting for temperature ranges
- Resolution checker logic split into `_check_kalshi_markets_simulation()` and `_check_kalshi_settlements()`
- Trade history database now used for duplicate detection

### Technical Details

#### Files Modified
- `bot/application/bot_runner.py`:
  - Added `_check_kalshi_markets_simulation()` for simulation resolution
  - Added `_filter_existing_positions()` for duplicate prevention
  - Updated `_check_resolutions()` to branch on simulation mode
- `bot/connectors/kalshi.py`:
  - Added `get_finalized_markets_by_series()` for market queries
  - Added `_extract_location_from_ticker()` for city parsing
  - Modified question building to inject location
- `bot/database/trade_history.py`:
  - Added `get_open_market_ids()` for duplicate detection
- `bot/utils/logger.py`:
  - Modified `get_logger()` to pass `log_dir="logs"` parameter
- `bot/cli/cli.py`:
  - Updated Market column max_width to 60
  - Added YES/NO extraction from token_id for Side display

#### Files Added
- `scripts/check_recent_trades.py`: Diagnostic script for trade analysis
- `scripts/check_kalshi_questions.py`: Test script for location injection

---

## [2.1.1] - 2026-01-16

### Fixed
- **CRITICAL**: Resolution checker AttributeError
  - Fixed incorrect attribute name (`base_url` → `api_base`)
  - Resolution checking was completely broken
- **CRITICAL**: Resolution checker JSON parsing
  - Added `response.json()` call before accessing data
  - Fixed "argument of type 'Response' is not iterable" error
- Daily counter reset bug
  - Was resetting every minute instead of daily
  - Fixed date comparison logic

---

## [2.1.0] - 2026-01-15

### Added
- Automated bot runner with daemon mode
- P&L tracking with SQLite database
- Hourly resolution checking
- Daily trade limits and risk management
- Simplified CLI commands (`bot-start`, `bot-status`, `bot-stop`)
- VPS deployment support (tmux + systemd)

### Changed
- Made Polymarket fields optional for Kalshi-only usage
- Fixed position sizing defaults (1.50 instead of 5.00)
- Improved trade cost calculation

---

## [2.0.0] - 2026-01-10

### Added
- Extreme value betting strategy
- Multi-platform support (Kalshi + Polymarket)
- Wallet analysis feature
- Trade history tracking
- Performance metrics

---

## Upgrade Guide

### Upgrading from v2.3.x to v2.4.0

1. **Pull latest changes:**
   ```bash
   git pull origin main
   ```

2. **Review new configuration defaults** (optional - bot uses better defaults automatically):
   ```bash
   # If you want to customize, update .env:
   MIN_EDGE_THRESHOLD=0.10           # Now 10% (was 5%)
   MAX_TRADES_PER_DAY=25             # Reduced from 50
   EXTREME_MIN_POSITION=1.50         # Larger positions
   EXTREME_MAX_POSITION=2.50
   ```

3. **NWS API is automatic** - No configuration needed. The bot now uses the National Weather Service as the primary data source.

4. **Restart bot to apply fixes:**
   ```bash
   # Stop current bot (Ctrl+C in tmux)
   # Restart with new version
   python bot.py bot-start --simulation --platform kalshi
   ```

5. **Verify improvements:**
   - Check logs for "NWS" mentions confirming the new weather source
   - Monitor trade quality: Should see fewer but higher-edge trades
   - Look for correct probability direction in logs (e.g., "P(temp < 49) = 0.23")

### Breaking Changes

**None** - v2.4.0 is fully backward compatible.

However, **behavior changes significantly**:
- Fewer trades per day (quality over quantity)
- Larger position sizes per trade
- Stricter edge requirements (10% minimum)
- No trades without real weather data (removed fallback heuristics)

If you were relying on high trade volume, you may want to adjust `MAX_TRADES_PER_DAY` and position sizing in your `.env`.

---

### Upgrading from v2.1.x to v2.2.0

1. **Pull latest changes:**
   ```bash
   git pull origin main
   ```

2. **No configuration changes required** - All improvements are automatic

3. **Restart bot to apply fixes:**
   ```bash
   # Stop current bot (Ctrl+C in tmux)
   # Restart with new version
   python bot.py bot-start --simulation --platform kalshi
   ```

4. **Verify improvements:**
   - Check `logs/bot.log` to confirm file logging works
   - Monitor duplicate prevention: "After filtering existing positions: X opportunities"
   - Look for location injection in status tables: "in Denver", "in Seattle", etc.
   - Verify resolution checking: "Found X finalized markets" in simulation mode

### Breaking Changes

**None** - v2.2.0 is fully backward compatible with v2.1.x

All existing trades in the database will continue to work. New features activate automatically on restart.

---

## Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check the troubleshooting section in README.md
- Review ARCHITECTURE.md for technical details

---

**Version Format**: MAJOR.MINOR.PATCH
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)
