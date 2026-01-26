# Changelog

All notable changes to the Polymarket Weather Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Diagnostic scripts**:
  - `check_recent_trades.py`: Inspect database for duplicates and trade details
  - `check_kalshi_questions.py`: Test location injection and API responses

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
- `check_recent_trades.py`: Diagnostic script for trade analysis
- `check_kalshi_questions.py`: Test script for location injection

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
