"""Main trading orchestration and decision engine."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any

from bot.connectors.weather import WeatherConnector
from bot.utils.config import Config
from bot.utils.logger import get_logger
from bot.utils.models import (
    Portfolio,
    Position,
    Trade,
    TradeSignal,
    TradeSide,
    WeatherMarket,
)

# Optional Polymarket support
try:
    from bot.connectors.polymarket import PolymarketClient
except ImportError:
    PolymarketClient = None


class WeatherTrader:
    """Core trading logic for weather prediction markets."""

    def __init__(self, config: Config, polymarket: Any, weather: WeatherConnector):  # polymarket can be PolymarketClient or KalshiClient
        self.config = config
        self.polymarket = polymarket
        self.weather = weather
        self.logger = get_logger()

        # Trading state
        self.positions: List[Position] = []
        self.trades: List[Trade] = []
        self.daily_trade_count = 0
        self.last_trade_date = None

        # Load state if exists
        self._load_state()

    def scan_and_trade(self) -> dict:
        """Main trading cycle: scan markets, analyze, and execute trades.

        Returns:
            Dict with cycle results (markets scanned, trades executed, etc.)
        """
        self.logger.info("Starting trading cycle...")

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "markets_scanned": 0,
            "weather_markets": 0,
            "signals_generated": 0,
            "trades_executed": 0,
            "errors": [],
        }

        try:
            # 1. Fetch all markets
            all_markets = self.polymarket.get_all_markets()
            results["markets_scanned"] = len(all_markets)
            self.logger.info(f"Fetched {len(all_markets)} total markets")

            # 2. Filter for weather markets
            weather_markets = self.polymarket.filter_weather_markets(all_markets)
            results["weather_markets"] = len(weather_markets)
            self.logger.info(f"Found {len(weather_markets)} weather markets")

            if not weather_markets:
                self.logger.warning("No weather markets found")
                return results

            # 3. Analyze each market
            signals = []
            for market in weather_markets:
                try:
                    signal = self.analyze_market(market)
                    if signal and self._should_trade(signal):
                        signals.append(signal)
                except Exception as e:
                    self.logger.error(f"Error analyzing market {market.market_id}: {e}")
                    results["errors"].append(str(e))

            results["signals_generated"] = len(signals)
            self.logger.info(f"Generated {len(signals)} trade signals")

            # 4. Sort signals by edge (best first)
            signals.sort(key=lambda s: s.edge, reverse=True)

            # 5. Execute trades (up to daily limit)
            for signal in signals:
                if self._can_trade():
                    try:
                        trade = self.execute_trade(signal)
                        if trade:
                            self.trades.append(trade)
                            results["trades_executed"] += 1
                            self.daily_trade_count += 1
                    except Exception as e:
                        self.logger.error(f"Error executing trade: {e}")
                        results["errors"].append(str(e))
                else:
                    self.logger.warning("Daily trade limit reached or insufficient funds")
                    break

            # 6. Save state
            self._save_state()

        except Exception as e:
            self.logger.error(f"Error in trading cycle: {e}", exc_info=True)
            results["errors"].append(str(e))

        self.logger.info(f"Cycle complete: {results['trades_executed']} trades executed")
        return results

    def analyze_market(self, market: WeatherMarket) -> Optional[TradeSignal]:
        """Analyze a weather market and generate trade signal if edge exists.

        Args:
            market: Weather market to analyze

        Returns:
            TradeSignal if trade is recommended, None otherwise
        """
        try:
            # Parse market question for details
            parsed = self.weather.parse_market_question(market.question)

            if not parsed["location"] or not parsed["threshold"]:
                self.logger.debug(f"Could not parse market: {market.question}")
                return None

            # Use market end_date if no date parsed
            forecast_date = parsed["date"] or market.end_date

            # Get weather forecast
            forecast = self.weather.get_forecast(
                location=parsed["location"],
                date=forecast_date,
                use_ensemble=self.config.enable_ensemble_models,
            )

            if not forecast:
                self.logger.warning(f"No forecast available for {parsed['location']}")
                return None

            # Calculate fair probability
            fair_prob = self.weather.calculate_probability(
                forecast=forecast,
                threshold=parsed["threshold"],
                threshold_type=parsed["threshold_type"] or "high_temp_f",
            )

            # Determine which side to trade
            yes_edge = fair_prob - market.yes_price
            no_edge = (1 - fair_prob) - market.no_price

            # Only trade if edge exceeds threshold
            if abs(yes_edge) < self.config.min_edge_threshold and abs(
                no_edge
            ) < self.config.min_edge_threshold:
                return None

            # Choose side with better edge
            if yes_edge > no_edge:
                side = TradeSide.BUY
                token_id = market.yes_token_id
                price = market.yes_price
                edge = yes_edge
            else:
                side = TradeSide.SELL  # Buy NO shares
                token_id = market.no_token_id
                price = market.no_price
                edge = no_edge

            # Calculate position size
            size = self._calculate_position_size(edge, forecast.confidence)

            # Build reasoning
            reasoning = (
                f"Forecast: {forecast.temp_high_f:.1f}°F (±5°F), "
                f"Threshold: {parsed['threshold']}°F, "
                f"Fair prob: {fair_prob:.2%}, Market: {price:.2%}, "
                f"Edge: {edge:.2%}, Source: {forecast.source}"
            )

            signal = TradeSignal(
                market=market,
                forecast=forecast,
                fair_probability=fair_prob,
                market_probability=price,
                edge=edge,
                confidence=forecast.confidence,
                action=side,
                token_id=token_id,
                price=price,
                size=size,
                reasoning=reasoning,
            )

            self.logger.info(f"Signal: {signal.action} {market.question[:60]}... | Edge: {edge:.2%}")

            return signal

        except Exception as e:
            self.logger.error(f"Error analyzing market: {e}")
            return None

    def _calculate_position_size(self, edge: float, confidence: float) -> float:
        """Calculate position size using Kelly Criterion (fractional).

        Args:
            edge: Expected edge (fair_prob - market_prob)
            confidence: Forecast confidence (0-1)

        Returns:
            Position size in USDC
        """
        # Fractional Kelly (more conservative)
        kelly_fraction = 0.25  # Use 25% of full Kelly

        # Simple Kelly: f = edge / odds
        # For binary outcomes with price p, Kelly = (edge * confidence) / p
        # More conservative: use bankroll percentage
        base_size = self.config.bankroll_usdc * self.config.position_size_pct

        # Scale by edge and confidence
        size_multiplier = min(abs(edge) * confidence * 2, 1.0)  # Cap at 1x
        position_size = base_size * size_multiplier

        # Apply limits
        position_size = min(position_size, self.config.max_position_size_usdc)
        position_size = max(position_size, 1.0)  # Minimum $1 bet

        return round(position_size, 2)

    def _should_trade(self, signal: TradeSignal) -> bool:
        """Check if signal meets trading criteria.

        Args:
            signal: Trade signal to evaluate

        Returns:
            True if should trade, False otherwise
        """
        # Check confidence threshold
        if signal.confidence < self.config.min_confidence:
            return False

        # Check edge threshold
        if abs(signal.edge) < self.config.min_edge_threshold:
            return False

        # Check if already have position in this market
        for position in self.positions:
            if position.market_id == signal.market.market_id and position.is_open:
                self.logger.debug(f"Already have position in {signal.market.market_id}")
                return False

        return True

    def _can_trade(self) -> bool:
        """Check if bot can execute more trades today.

        Returns:
            True if can trade, False otherwise
        """
        # Reset daily counter if new day
        today = datetime.utcnow().date()
        if self.last_trade_date != today:
            self.daily_trade_count = 0
            self.last_trade_date = today

        # Check daily limit
        if self.daily_trade_count >= self.config.max_daily_trades:
            return False

        # Check position limit
        open_positions = sum(1 for p in self.positions if p.is_open)
        if open_positions >= self.config.max_open_positions:
            return False

        return True

    def execute_trade(self, signal: TradeSignal) -> Optional[Trade]:
        """Execute a trade based on signal.

        Args:
            signal: Trade signal to execute

        Returns:
            Trade record if successful, None otherwise
        """
        try:
            # Execute order (respects simulation mode)
            order_id = self.polymarket.execute_market_order(
                token_id=signal.token_id,
                amount=signal.size,
                simulation=self.config.simulation_mode,
            )

            # Create trade record
            trade = Trade(
                trade_id=order_id or f"trade_{int(time.time())}",
                market_id=signal.market.market_id,
                question=signal.market.question,
                token_id=signal.token_id,
                side=signal.action,
                price=signal.price,
                size=signal.size,
                cost=signal.size * signal.price,
                simulation=self.config.simulation_mode,
                tx_hash=order_id if not self.config.simulation_mode else None,
                status="executed" if self.config.simulation_mode else "pending",
                fair_probability=signal.fair_probability,
                edge=signal.edge,
                reasoning=signal.reasoning,
            )

            mode = "SIMULATION" if self.config.simulation_mode else "LIVE"
            self.logger.info(
                f"[{mode}] Executed trade: {signal.action} {signal.size} USDC "
                f"in {signal.market.question[:50]}... @ {signal.price:.2%}"
            )

            return trade

        except Exception as e:
            self.logger.error(f"Failed to execute trade: {e}", exc_info=True)
            return None

    def get_portfolio(self) -> Portfolio:
        """Calculate current portfolio status.

        Returns:
            Portfolio summary
        """
        try:
            cash_balance = self.polymarket.get_usdc_balance()
        except:
            cash_balance = self.config.bankroll_usdc

        # Calculate stats
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.status == "won")
        losing_trades = sum(1 for t in self.trades if t.status == "lost")
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        realized_pnl = sum(
            t.cost * (2 if t.status == "won" else -1)
            for t in self.trades
            if t.status in ["won", "lost"]
        )

        open_positions_count = sum(1 for p in self.positions if p.is_open)

        return Portfolio(
            total_value=cash_balance,
            cash_balance=cash_balance,
            invested=0.0,  # TODO: Calculate from open positions
            total_pnl=realized_pnl,
            realized_pnl=realized_pnl,
            unrealized_pnl=0.0,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            open_positions=open_positions_count,
            max_position_size=self.config.max_position_size_usdc,
            total_exposure=0.0,
        )

    def _save_state(self):
        """Save trading state to disk."""
        state_file = Path(self.config.cache_dir) / "trader_state.json"
        state = {
            "positions": [p.model_dump() for p in self.positions],
            "trades": [t.model_dump() for t in self.trades],
            "daily_trade_count": self.daily_trade_count,
            "last_trade_date": (
                self.last_trade_date.isoformat() if self.last_trade_date else None
            ),
        }

        with open(state_file, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def _load_state(self):
        """Load trading state from disk."""
        state_file = Path(self.config.cache_dir) / "trader_state.json"
        if not state_file.exists():
            return

        try:
            with open(state_file, "r") as f:
                state = json.load(f)

            self.positions = [Position(**p) for p in state.get("positions", [])]
            self.trades = [Trade(**t) for t in state.get("trades", [])]
            self.daily_trade_count = state.get("daily_trade_count", 0)

            if state.get("last_trade_date"):
                from datetime import date

                self.last_trade_date = date.fromisoformat(state["last_trade_date"])

            self.logger.info(
                f"Loaded state: {len(self.positions)} positions, {len(self.trades)} trades"
            )

        except Exception as e:
            self.logger.error(f"Error loading state: {e}")
