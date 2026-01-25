"""Automated bot runner for continuous trading and resolution tracking."""

import time
import signal
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from bot.application.extreme_value_strategy import ExtremeValueStrategy
from bot.connectors.kalshi import KalshiClient
from bot.connectors.weather import WeatherConnector
from bot.database.trade_history import TradeHistoryDB
from bot.utils.config import get_config
from bot.utils.logger import get_logger
from bot.utils.models import Trade, TradeSide

# Optional Polymarket support (requires web3, eth-account, py-clob-client)
try:
    from bot.connectors.polymarket import PolymarketClient
    POLYMARKET_AVAILABLE = True
except ImportError:
    POLYMARKET_AVAILABLE = False
    PolymarketClient = None


class BotRunner:
    """Automated bot that scans, trades, and tracks resolutions."""

    def __init__(self, platform: str = "kalshi", simulation: bool = True):
        """Initialize bot runner.

        Args:
            platform: Trading platform (kalshi or polymarket)
            simulation: Run in simulation mode (dry-run)
        """
        self.config = get_config()
        self.logger = get_logger()
        self.platform = platform.lower()
        self.simulation = simulation
        self.running = False

        # Initialize components
        self.trade_db = TradeHistoryDB()
        self.weather = WeatherConnector(self.config)

        # Initialize platform client
        if self.platform == "kalshi":
            self.client = KalshiClient(self.config)
        else:
            if not POLYMARKET_AVAILABLE:
                raise ImportError(
                    "Polymarket support not available. Install required packages:\n"
                    "pip install web3>=6.11.1 eth-account>=0.13.0 py-clob-client>=0.34.4"
                )
            self.client = PolymarketClient(self.config)

        self.strategy = ExtremeValueStrategy(self.config, self.client, self.weather)

        # Bot configuration
        self.scan_interval = getattr(self.config, 'scan_interval_hours', 6) * 3600  # seconds
        self.resolution_check_interval = getattr(self.config, 'resolution_check_hours', 0.25) * 3600  # Check every 15 min
        self.max_trades_per_scan = getattr(self.config, 'max_trades_per_scan', 20)
        self.max_trades_per_day = getattr(self.config, 'max_trades_per_day', 50)
        self.max_trades_per_city = getattr(self.config, 'max_trades_per_city', 3)
        self.bankroll = getattr(self.config, 'bankroll', 1000.0)
        self.max_daily_exposure_pct = getattr(self.config, 'max_daily_exposure_pct', 5.0)

        # State tracking
        self.last_scan_time: Optional[datetime] = None
        self.last_resolution_check: Optional[datetime] = None
        self.trades_today = 0
        self.daily_exposure = 0.0
        self.start_time: Optional[datetime] = None

        # PID file for daemon management
        self.pid_file = Path("./data/bot.pid")

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)

    def start(self):
        """Start the bot daemon."""
        if self.is_running():
            self.logger.error("Bot is already running!")
            return False

        self.running = True
        self.start_time = datetime.now(timezone.utc)

        # Write PID file
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(time.time()))

        mode = "SIMULATION" if self.simulation else "LIVE"
        self.logger.info(f"Starting {mode} bot on {self.platform.upper()}")
        self.logger.info(f"Scan interval: {self.scan_interval/3600:.1f} hours")
        self.logger.info(f"Max trades per scan: {self.max_trades_per_scan}")
        self.logger.info(f"Max trades per day: {self.max_trades_per_day}")
        self.logger.info(f"Bankroll: ${self.bankroll:.2f}")

        # Main loop
        last_scan = datetime.min.replace(tzinfo=timezone.utc)
        last_resolution = datetime.min.replace(tzinfo=timezone.utc)
        last_reset_date = datetime.now(timezone.utc).date()  # Track last reset date

        while self.running:
            try:
                now = datetime.now(timezone.utc)

                # Reset daily counters at midnight UTC (once per day)
                if now.date() > last_reset_date:
                    self._reset_daily_counters()
                    last_reset_date = now.date()

                # Check if it's time to scan for trades
                if (now - last_scan).total_seconds() >= self.scan_interval:
                    self._scan_and_trade()
                    last_scan = now

                # Check if it's time to update resolutions
                if (now - last_resolution).total_seconds() >= self.resolution_check_interval:
                    self._check_resolutions()
                    last_resolution = now

                # Sleep for 1 minute before next check
                time.sleep(60)

            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received, stopping...")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(300)  # Wait 5 minutes on error

        self.stop()
        return True

    def stop(self):
        """Stop the bot daemon."""
        self.running = False

        if self.pid_file.exists():
            self.pid_file.unlink()

        self.logger.info("Bot stopped")

    def is_running(self) -> bool:
        """Check if bot is currently running."""
        if not self.pid_file.exists():
            return False

        # Check if PID file is recent (within last 2 minutes)
        try:
            start_time = float(self.pid_file.read_text())
            age = time.time() - start_time
            return age < 120  # Consider dead if no update in 2 minutes
        except:
            return False

    def _reset_daily_counters(self):
        """Reset daily trade counters."""
        self.logger.info("Resetting daily counters (new day)")
        self.trades_today = 0
        self.daily_exposure = 0.0

    def _scan_and_trade(self):
        """Scan for opportunities and execute trades."""
        self.logger.info("=" * 60)
        self.logger.info(f"Starting scan at {datetime.now(timezone.utc).isoformat()}")

        try:
            # Check daily limits
            if self.trades_today >= self.max_trades_per_day:
                self.logger.warning(f"Daily trade limit reached ({self.max_trades_per_day}), skipping scan")
                return

            max_exposure = self.bankroll * (self.max_daily_exposure_pct / 100)
            if self.daily_exposure >= max_exposure:
                self.logger.warning(f"Daily exposure limit reached (${max_exposure:.2f}), skipping scan")
                return

            # Fetch markets
            self.logger.info(f"Fetching {self.platform} markets...")
            if self.platform == "kalshi":
                all_markets = self.client.get_weather_markets_direct(limit=200)
                weather_markets = self.client.filter_weather_markets(all_markets)
            else:
                all_markets = self.client.get_all_markets()
                weather_markets = self.client.filter_weather_markets(all_markets)

            self.logger.info(f"Found {len(weather_markets)} weather markets")

            # Scan for opportunities
            signals = self.strategy.scan_for_opportunities(weather_markets)
            signals = self.strategy.filter_by_time_to_resolution(signals)
            signals = self.strategy.filter_by_liquidity(signals)

            self.logger.info(f"Found {len(signals)} opportunities")

            if not signals:
                self.logger.info("No opportunities found")
                return

            # Filter out markets with existing open positions (prevent duplicates)
            signals = self._filter_existing_positions(signals)
            self.logger.info(f"After filtering existing positions: {len(signals)} opportunities")

            if not signals:
                self.logger.info("No new opportunities (all have existing positions)")
                return

            # Apply city diversification
            signals = self._apply_city_limits(signals)

            # Apply daily limits
            remaining_trades = min(
                self.max_trades_per_scan,
                self.max_trades_per_day - self.trades_today
            )
            signals = signals[:remaining_trades]

            self.logger.info(f"Executing top {len(signals)} trades...")

            # Execute trades
            executed = self._execute_trades(signals)

            self.logger.info(f"Scan complete: {executed}/{len(signals)} trades executed")
            self.logger.info(f"Daily stats: {self.trades_today} trades, ${self.daily_exposure:.2f} exposure")

        except Exception as e:
            self.logger.error(f"Error during scan: {e}", exc_info=True)

    def _filter_existing_positions(self, signals):
        """Filter out markets that already have open positions.

        This prevents duplicate trades on the same market across multiple scans.

        Args:
            signals: List of trade signals

        Returns:
            Filtered list of signals (excluding markets with open positions)
        """
        # Get set of market IDs with open positions
        open_market_ids = self.trade_db.get_open_market_ids(
            simulation=self.simulation,
            platform=self.platform
        )

        if open_market_ids:
            self.logger.info(f"Filtering {len(open_market_ids)} markets with existing positions")

        # Filter out signals for markets we already have positions in
        filtered = [s for s in signals if s.market.market_id not in open_market_ids]

        skipped = len(signals) - len(filtered)
        if skipped > 0:
            self.logger.info(f"Skipped {skipped} signals (already have positions)")

        return filtered

    def _apply_city_limits(self, signals):
        """Limit trades per city to avoid correlation."""
        city_counts: Dict[str, int] = {}
        filtered = []

        for signal in signals:
            # Extract city from question (rough heuristic)
            question = signal.market.question.lower()
            city = None

            cities = ["seattle", "nyc", "new york", "san francisco", "sfo",
                     "los angeles", "chicago", "boston", "miami", "denver",
                     "atlanta", "phoenix"]

            for c in cities:
                if c in question:
                    city = c
                    break

            if city:
                if city_counts.get(city, 0) >= self.max_trades_per_city:
                    continue
                city_counts[city] = city_counts.get(city, 0) + 1

            filtered.append(signal)

        return filtered

    def _execute_trades(self, signals) -> int:
        """Execute trade signals and log to database."""
        executed = 0

        for signal in signals:
            try:
                # Execute based on platform
                if self.platform == "kalshi":
                    ticker = signal.market.market_id
                    side = "yes" if signal.action == "BUY" else "no"
                    price_cents = int(signal.price * 100)
                    count = int(signal.size / signal.price) if signal.price > 0 else 1000

                    order_id = self.client.execute_limit_order(
                        ticker=ticker,
                        side=side,
                        count=count,
                        price=price_cents,
                        simulation=self.simulation,
                    )
                else:
                    order_id = self.client.execute_market_order(
                        token_id=signal.token_id,
                        amount=signal.size,
                        simulation=self.simulation,
                    )

                # Create and log trade
                # For Kalshi: count = signal.size / signal.price contracts
                # Actual cost = count * signal.price ≈ signal.size (with rounding)
                # For accuracy, just use signal.size as it's already the dollar amount
                trade = Trade(
                    trade_id=order_id or f"sim_{signal.market.market_id}_{int(time.time())}",
                    timestamp=datetime.now(timezone.utc),
                    market_id=signal.market.market_id,
                    question=signal.market.question,
                    token_id=signal.token_id,
                    side=TradeSide.BUY,
                    price=signal.price,
                    size=signal.size,
                    cost=signal.size,  # Fixed: signal.size is already the dollar amount
                    simulation=self.simulation,
                    tx_hash=order_id,
                    status="executed",
                    fair_probability=signal.fair_probability,
                    edge=signal.edge,
                    reasoning=signal.reasoning
                )

                self.trade_db.log_trade(trade, platform=self.platform)

                # Update counters
                executed += 1
                self.trades_today += 1
                self.daily_exposure += signal.size

                self.logger.info(
                    f"✓ Trade {executed}: {signal.action} {signal.size:.2f} USDC @ {signal.price:.1%} "
                    f"- {signal.market.question[:60]}..."
                )

                time.sleep(1)  # Rate limiting

            except Exception as e:
                self.logger.error(f"Failed to execute trade: {e}")

        return executed

    def _check_resolutions(self):
        """Check and update resolutions for open trades."""
        self.logger.info("Checking for market resolutions...")

        try:
            open_trades = self.trade_db.get_open_trades(
                simulation=self.simulation,
                platform=self.platform
            )

            if not open_trades:
                self.logger.info("No open trades to check")
                return

            self.logger.info(f"Checking {len(open_trades)} open trades...")

            resolved_count = 0

            if self.platform == "kalshi":
                # For Kalshi: Branch on simulation vs live mode
                if self.simulation:
                    # Simulation: Query finalized markets (no real positions exist)
                    resolved_count = self._check_kalshi_markets_simulation(open_trades)
                else:
                    # Live: Use settlements API (real positions exist)
                    resolved_count = self._check_kalshi_settlements(open_trades)
            else:
                # For Polymarket: Query individual markets (keeping old logic)
                for trade in open_trades:
                    try:
                        market_id = trade['market_id']
                        market_info = self._get_polymarket_status(market_id)

                        if market_info and market_info.get('resolved'):
                            won = self._calculate_trade_outcome(trade, market_info)
                            pnl = self._calculate_pnl(trade, won)

                            self.trade_db.update_resolution(
                                trade_id=trade['trade_id'],
                                won=won,
                                pnl=pnl,
                                resolution_date=datetime.now(timezone.utc)
                            )

                            resolved_count += 1

                    except Exception as e:
                        self.logger.debug(f"Error checking trade {trade['trade_id']}: {e}")

            if resolved_count > 0:
                self.logger.info(f"Updated {resolved_count} resolved trades")
            else:
                self.logger.info("No new resolutions found")

        except Exception as e:
            self.logger.error(f"Error checking resolutions: {e}", exc_info=True)

    def _check_kalshi_settlements(self, open_trades: List[Dict]) -> int:
        """Check Kalshi settlements and update resolved trades.

        Args:
            open_trades: List of open trades from database

        Returns:
            Number of trades resolved
        """
        resolved_count = 0

        try:
            # Get all settlements from Kalshi
            settlements = self.client.get_settlements(limit=200)

            if not settlements:
                self.logger.debug("No settlements found")
                return 0

            # Create a lookup map: ticker -> settlement
            settlement_map = {s['ticker']: s for s in settlements}
            self.logger.debug(f"Found settlements for {len(settlement_map)} markets")

            # Check each open trade against settlements
            for trade in open_trades:
                ticker = trade['market_id']

                if ticker in settlement_map:
                    settlement = settlement_map[ticker]

                    # Extract outcome from settlement
                    market_result = settlement.get('market_result', '').lower()  # 'yes' or 'no'

                    self.logger.info(f"Found settlement for {ticker}: result={market_result}")

                    # Determine if trade won
                    token_id = trade['token_id']
                    if 'yes' in token_id.lower():
                        won = market_result == 'yes'
                    else:
                        won = market_result == 'no'

                    # Calculate P&L
                    pnl = self._calculate_pnl(trade, won)

                    # Update database
                    self.trade_db.update_resolution(
                        trade_id=trade['trade_id'],
                        won=won,
                        pnl=pnl,
                        resolution_date=datetime.now(timezone.utc)
                    )

                    resolved_count += 1
                    self.logger.info(f"Resolved: {ticker} - {'WON' if won else 'LOST'} (P&L: ${pnl:+.2f})")

        except Exception as e:
            self.logger.error(f"Error checking Kalshi settlements: {e}", exc_info=True)

        return resolved_count

    def _check_kalshi_markets_simulation(self, open_trades: List[Dict]) -> int:
        """Check finalized Kalshi markets for simulation mode trades.

        Since simulation mode doesn't create real positions on Kalshi,
        we can't use the settlements API. Instead, we query markets by
        series with status=finalized to find resolved markets.

        Args:
            open_trades: List of open trades from database

        Returns:
            Number of trades resolved
        """
        resolved_count = 0

        try:
            # Extract unique series tickers from open trades
            # Market tickers look like: KXLOWTLAX-24DEC31
            # Series ticker is the part before the hyphen: KXLOWTLAX
            series_set = set()
            for trade in open_trades:
                ticker = trade['market_id']
                # Extract series ticker (everything before the hyphen)
                if '-' in ticker:
                    series = ticker.split('-')[0]
                    series_set.add(series)

            if not series_set:
                self.logger.debug("No series tickers found in open trades")
                return 0

            series_list = list(series_set)
            self.logger.info(f"Checking finalized markets for {len(series_list)} series: {series_list[:5]}...")

            # Fetch all finalized markets for these series
            finalized_markets = self.client.get_finalized_markets_by_series(series_list)

            if not finalized_markets:
                self.logger.debug("No finalized markets found")
                return 0

            # Create a lookup map: ticker -> market
            finalized_map = {m['ticker']: m for m in finalized_markets}
            self.logger.debug(f"Found finalized markets for {len(finalized_map)} tickers")

            # Check each open trade against finalized markets
            for trade in open_trades:
                ticker = trade['market_id']

                if ticker in finalized_map:
                    market = finalized_map[ticker]

                    # Extract outcome from market
                    market_result = market.get('result', '').lower()  # 'yes' or 'no'
                    market_status = market.get('status', '')

                    self.logger.info(f"Found finalized market for {ticker}: status={market_status}, result={market_result}")

                    # Determine if trade won
                    token_id = trade['token_id']
                    if 'yes' in token_id.lower():
                        won = market_result == 'yes'
                    else:
                        won = market_result == 'no'

                    # Calculate P&L
                    pnl = self._calculate_pnl(trade, won)

                    # Update database
                    self.trade_db.update_resolution(
                        trade_id=trade['trade_id'],
                        won=won,
                        pnl=pnl,
                        resolution_date=datetime.now(timezone.utc)
                    )

                    resolved_count += 1
                    self.logger.info(f"Resolved: {ticker} - {'WON' if won else 'LOST'} (P&L: ${pnl:+.2f})")

        except Exception as e:
            self.logger.error(f"Error checking Kalshi finalized markets: {e}", exc_info=True)

        return resolved_count

    def _get_kalshi_market_status(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get market status from Kalshi API."""
        try:
            # Use Kalshi API to get market details
            url = f"{self.client.api_base}/markets/{ticker}"
            response = self.client._make_request("GET", url)

            # Check if request was successful
            if response.status_code == 404:
                # Market was deleted (likely expired/finalized and removed from API)
                self.logger.warning(f"Market {ticker} not found (404) - likely expired and removed from API")
                return None
            elif response.status_code != 200:
                self.logger.debug(f"Failed to get market {ticker}: status {response.status_code}")
                return None

            # Parse JSON response
            data = response.json()

            if data and 'market' in data:
                market = data['market']
                status = market.get('status', '')
                result = market.get('result', '')

                # DEBUG: Log what we're seeing
                self.logger.debug(f"Market {ticker}: status={status}, result={result}")

                # Kalshi uses 'finalized' for resolved markets
                is_resolved = status == 'finalized'

                if is_resolved:
                    self.logger.info(f"Found resolved market: {ticker} - status={status}, result={result}")

                return {
                    'resolved': is_resolved,
                    'outcome': result  # 'yes' or 'no'
                }
        except Exception as e:
            self.logger.error(f"Error getting Kalshi market status for {ticker}: {e}")

        return None

    def _get_polymarket_status(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Get market status from Polymarket."""
        # TODO: Implement Polymarket resolution checking
        return None

    def _calculate_trade_outcome(self, trade: Dict, market_info: Dict) -> bool:
        """Determine if trade won based on outcome."""
        outcome = market_info.get('outcome', '').lower()

        # For Kalshi: trade['token_id'] contains 'yes' or 'no'
        # Match against market outcome
        if 'yes' in trade['token_id'].lower():
            return outcome == 'yes'
        else:
            return outcome == 'no'

    def _calculate_pnl(self, trade: Dict, won: bool) -> float:
        """Calculate profit/loss for a trade."""
        if won:
            # Win: get full payout
            # Shares = size / price, payout = shares * $1
            shares = trade['size'] / trade['price'] if trade['price'] > 0 else trade['size']
            payout = shares
            profit = payout - trade['cost']
            return round(profit, 2)
        else:
            # Loss: lose entire stake
            return -round(trade['cost'], 2)

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        # Get P&L summary
        pnl = self.trade_db.get_pnl_summary(
            simulation=self.simulation,
            platform=self.platform
        )

        # Get open trades
        open_trades = self.trade_db.get_open_trades(
            simulation=self.simulation,
            platform=self.platform
        )

        return {
            'running': self.is_running(),
            'mode': 'SIMULATION' if self.simulation else 'LIVE',
            'platform': self.platform.upper(),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_scan': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'trades_today': self.trades_today,
            'daily_exposure': self.daily_exposure,
            'bankroll': self.bankroll,
            'pnl': pnl,
            'open_positions': len(open_trades),
        }
