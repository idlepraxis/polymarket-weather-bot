"""Extreme value betting strategy - based on successful trader analysis.

Strategy:
- Buy YES shares ONLY when price < 0.10-0.15 (10-15¢)
- Buy NO shares ONLY when YES price > 0.40-0.50 (implying NO is cheap)
- Keep position sizes very small (<$1 typically, max $5)
- High volume (many bets per day)
- Let extreme mispricings and asymmetric payoffs drive profits

This exploits market microstructure inefficiencies in low-liquidity weather markets.
"""

from datetime import datetime
from typing import List, Optional, Any

from bot.connectors.weather import WeatherConnector
from bot.utils.config import Config
from bot.utils.logger import get_logger
from bot.utils.models import TradeSignal, TradeSide, WeatherMarket

# Optional Polymarket support
try:
    from bot.connectors.polymarket import PolymarketClient
except ImportError:
    PolymarketClient = None


class ExtremeValueStrategy:
    """Extreme value betting strategy for weather markets."""

    def __init__(
        self,
        config: Config,
        polymarket: Any,  # Can be PolymarketClient or KalshiClient
        weather: Optional[WeatherConnector] = None,
    ):
        self.config = config
        self.polymarket = polymarket
        self.weather = weather
        self.logger = get_logger()

        # Strategy parameters (configurable via config)
        self.yes_max_price = getattr(config, "extreme_yes_max_price", 0.15)
        self.yes_ideal_price = getattr(config, "extreme_yes_ideal_price", 0.10)
        self.no_min_yes_price = getattr(config, "extreme_no_min_yes_price", 0.40)
        self.no_ideal_yes_price = getattr(config, "extreme_no_ideal_yes_price", 0.50)

        # Position sizing (target ~$1 average per trade)
        self.min_position = getattr(config, "extreme_min_position", 0.50)  # $0.50
        self.max_position = getattr(config, "extreme_max_position", 1.00)  # $1.00
        self.aggressive_max = getattr(config, "extreme_aggressive_max", 1.50)  # $1.50 for great opportunities

    def scan_for_opportunities(self, markets: List[WeatherMarket]) -> List[TradeSignal]:
        """Scan markets for extreme value opportunities.

        Args:
            markets: List of weather markets to scan

        Returns:
            List of trade signals for extreme value opportunities
        """
        signals = []

        for market in markets:
            # Check YES opportunities (cheap YES shares)
            yes_signal = self._check_yes_opportunity(market)
            if yes_signal:
                signals.append(yes_signal)

            # Check NO opportunities (expensive YES shares = cheap NO)
            no_signal = self._check_no_opportunity(market)
            if no_signal:
                signals.append(no_signal)

        # Sort by expected value (best opportunities first)
        signals.sort(key=lambda s: self._calculate_ev(s), reverse=True)

        return signals

    def _check_yes_opportunity(self, market: WeatherMarket) -> Optional[TradeSignal]:
        """Check if YES shares are cheap enough to buy.

        Args:
            market: Weather market to analyze

        Returns:
            TradeSignal if opportunity exists, None otherwise
        """
        yes_price = market.yes_price

        # Must be below maximum threshold
        if yes_price >= self.yes_max_price:
            return None

        # Calculate position size based on how cheap it is
        position_size = self._calculate_yes_position_size(yes_price)

        # Get forecast to estimate fair probability (if available)
        fair_prob = self._estimate_fair_probability(market, outcome="YES")

        # Calculate edge
        edge = fair_prob - yes_price

        # Must have positive expected value even with conservative estimate
        if edge <= 0:
            # Even without forecast, extreme prices often have edge
            # Use base assumption: if market says 8%, reality is probably 15-25%
            fair_prob = max(yes_price * 2.5, 0.20)  # At least 2.5x market price or 20%
            edge = fair_prob - yes_price

        reasoning = (
            f"EXTREME VALUE: YES at {yes_price:.1%} (threshold: {self.yes_max_price:.1%}). "
            f"Estimated fair prob: {fair_prob:.1%}. "
            f"Edge: {edge:.1%}. "
            f"Asymmetric payoff: Risk ${position_size * yes_price:.2f} to win ${position_size * (1 - yes_price):.2f}"
        )

        return TradeSignal(
            market=market,
            forecast=None,  # Not forecast-driven
            fair_probability=fair_prob,
            market_probability=yes_price,
            edge=edge,
            confidence=self._calculate_confidence(yes_price, "YES"),
            action=TradeSide.BUY,
            token_id=market.yes_token_id,
            price=yes_price,
            size=position_size,
            reasoning=reasoning,
        )

    def _check_no_opportunity(self, market: WeatherMarket) -> Optional[TradeSignal]:
        """Check if NO shares are cheap (YES shares are expensive).

        Args:
            market: Weather market to analyze

        Returns:
            TradeSignal if opportunity exists, None otherwise
        """
        yes_price = market.yes_price
        no_price = market.no_price

        # Must be above minimum threshold (YES overpriced = NO underpriced)
        if yes_price <= self.no_min_yes_price:
            return None

        # Calculate position size based on how expensive YES is
        position_size = self._calculate_no_position_size(yes_price)

        # Get forecast to estimate fair probability
        fair_prob_yes = self._estimate_fair_probability(market, outcome="YES")
        fair_prob_no = 1 - fair_prob_yes

        # Edge for NO shares
        edge = fair_prob_no - no_price

        if edge <= 0:
            # Conservative estimate: if market says YES is 60%, reality is probably 40-50%
            fair_prob_yes = min(yes_price * 0.75, 0.50)
            fair_prob_no = 1 - fair_prob_yes
            edge = fair_prob_no - no_price

        reasoning = (
            f"EXTREME VALUE: YES overpriced at {yes_price:.1%}, buying NO at {no_price:.1%}. "
            f"Estimated fair YES prob: {fair_prob_yes:.1%}. "
            f"NO edge: {edge:.1%}. "
            f"Asymmetric payoff: Risk ${position_size * no_price:.2f} to win ${position_size * (1 - no_price):.2f}"
        )

        return TradeSignal(
            market=market,
            forecast=None,
            fair_probability=fair_prob_no,
            market_probability=no_price,
            edge=edge,
            confidence=self._calculate_confidence(yes_price, "NO"),
            action=TradeSide.SELL,  # SELL = buy NO shares
            token_id=market.no_token_id,
            price=no_price,
            size=position_size,
            reasoning=reasoning,
        )

    def _calculate_yes_position_size(self, yes_price: float) -> float:
        """Calculate position size for YES purchases.

        Smaller prices = smaller positions (more shares for same $).
        """
        # Base position
        base = self.min_position

        # Scale based on how cheap it is
        if yes_price <= 0.05:  # Super cheap (≤5¢)
            # Very attractive, but limit shares
            # At 5¢, $1 = 20 shares
            size = self.aggressive_max
        elif yes_price <= 0.08:  # Very cheap (5-8¢)
            size = min(self.max_position * 2, self.aggressive_max)
        elif yes_price <= 0.10:  # Ideal range (8-10¢)
            size = self.max_position
        elif yes_price <= 0.12:  # Good (10-12¢)
            size = self.max_position * 0.75
        else:  # Acceptable (12-15¢)
            size = self.min_position

        return round(size, 2)

    def _calculate_no_position_size(self, yes_price: float) -> float:
        """Calculate position size for NO purchases.

        Higher YES price = cheaper NO = larger position.
        """
        # NO price = 1 - YES price
        no_price = 1 - yes_price

        # Base position
        base = self.min_position

        # Scale based on how cheap NO is
        if yes_price >= 0.60:  # YES ≥60%, NO ≤40% - very cheap NO
            size = self.aggressive_max
        elif yes_price >= 0.55:  # YES ≥55%, NO ≤45%
            size = min(self.max_position * 2, self.aggressive_max)
        elif yes_price >= 0.50:  # YES ≥50%, NO ≤50%
            size = self.max_position
        elif yes_price >= 0.45:  # YES ≥45%, NO ≤55%
            size = self.max_position * 0.75
        else:  # YES 40-45%, NO 55-60%
            size = self.min_position

        return round(size, 2)

    def _estimate_fair_probability(self, market: WeatherMarket, outcome: str) -> float:
        """Estimate fair probability using weather forecast if available.

        Args:
            market: Weather market
            outcome: "YES" or "NO"

        Returns:
            Estimated fair probability (0-1)
        """
        if not self.weather:
            # No weather connector - cannot calculate edge
            self.logger.warning(
                f"No weather connector configured - skipping trade (no edge without forecast)"
            )
            return self._conservative_estimate(market.yes_price, outcome)

        try:
            # Parse market question
            parsed = self.weather.parse_market_question(market.question)

            if not parsed["location"]:
                self.logger.warning(
                    f"SKIP: Could not parse location from: {market.question[:60]}... "
                    f"(trade will be skipped - no edge without location)"
                )
                return self._conservative_estimate(market.yes_price, outcome)

            # Need either a threshold or a range
            if not parsed["threshold"] and not parsed["is_range"]:
                self.logger.warning(
                    f"SKIP: Could not parse threshold/range from: {market.question[:60]}... "
                    f"(trade will be skipped - no edge without threshold)"
                )
                return self._conservative_estimate(market.yes_price, outcome)

            # Get forecast
            forecast_date = parsed["date"] or market.end_date
            forecast = self.weather.get_forecast(
                location=parsed["location"], date=forecast_date, use_ensemble=True
            )

            if not forecast:
                self.logger.warning(
                    f"SKIP: No forecast for {parsed['location']} on {forecast_date.strftime('%Y-%m-%d') if forecast_date else 'unknown'} "
                    f"(trade will be skipped - no edge without forecast)"
                )
                return self._conservative_estimate(market.yes_price, outcome)

            # Calculate probability based on market type
            if parsed["is_range"]:
                # Range market (Kalshi style: "48-49°")
                fair_prob = self.weather.calculate_range_probability(
                    forecast=forecast,
                    range_low=parsed["range_low"],
                    range_high=parsed["range_high"],
                    threshold_type=parsed["threshold_type"] or "high_temp_f",
                )
                self.logger.debug(
                    f"Range probability for {parsed['range_low']}-{parsed['range_high']}°: "
                    f"{fair_prob:.1%} (forecast: {forecast.temp_high_f if parsed['threshold_type'] == 'high_temp_f' else forecast.temp_low_f}°F)"
                )
            else:
                # Threshold market (">55°" or "above 70" or "<49°")
                # IMPORTANT: Pass threshold_direction to handle < vs > correctly
                direction = parsed.get("threshold_direction", "above")
                fair_prob = self.weather.calculate_probability(
                    forecast=forecast,
                    threshold=parsed["threshold"],
                    threshold_type=parsed["threshold_type"] or "high_temp_f",
                    direction=direction,
                )
                self.logger.debug(
                    f"Threshold probability for {direction} {parsed['threshold']}°: "
                    f"{fair_prob:.1%} (forecast: {forecast.temp_high_f if parsed['threshold_type'] == 'high_temp_f' else forecast.temp_low_f}°F)"
                )

            if outcome == "NO":
                fair_prob = 1 - fair_prob

            return fair_prob

        except Exception as e:
            self.logger.warning(f"Error estimating fair probability: {e}")
            return self._conservative_estimate(market.yes_price, outcome)

    def _conservative_estimate(self, yes_price: float, outcome: str) -> float:
        """Conservative probability estimate when no forecast available.

        IMPORTANT: Without actual weather data, we have NO EDGE.
        Return the market price (no edge) to effectively skip the trade.

        The old logic assumed 2-3x edge without data, which was wrong
        and resulted in betting blind with imaginary edge.
        """
        self.logger.debug(
            f"Using conservative estimate (market price) for {outcome} - "
            f"returning {yes_price:.1%} for YES, {1-yes_price:.1%} for NO (zero edge)"
        )
        if outcome == "YES":
            # No forecast = no edge, use market price
            # This will result in edge = 0 and trade being skipped
            return yes_price
        else:  # NO
            # No forecast = no edge, use market price
            return 1 - yes_price

    def _calculate_confidence(self, yes_price: float, side: str) -> float:
        """Calculate confidence in the trade.

        More extreme prices = higher confidence that market is wrong.
        """
        if side == "YES":
            # Lower price = higher confidence
            if yes_price <= 0.05:
                return 0.90
            elif yes_price <= 0.08:
                return 0.85
            elif yes_price <= 0.10:
                return 0.80
            elif yes_price <= 0.12:
                return 0.75
            else:
                return 0.70
        else:  # NO
            # Higher YES price = higher confidence NO is cheap
            if yes_price >= 0.60:
                return 0.90
            elif yes_price >= 0.55:
                return 0.85
            elif yes_price >= 0.50:
                return 0.80
            elif yes_price >= 0.45:
                return 0.75
            else:
                return 0.70

    def _calculate_ev(self, signal: TradeSignal) -> float:
        """Calculate expected value of a trade signal.

        EV = (win_prob × win_amount) - (lose_prob × lose_amount)
        """
        win_prob = signal.fair_probability
        lose_prob = 1 - win_prob

        win_amount = signal.size * (1 - signal.price)
        lose_amount = signal.size * signal.price

        ev = (win_prob * win_amount) - (lose_prob * lose_amount)

        return ev

    def filter_by_liquidity(
        self, signals: List[TradeSignal], min_liquidity: float = 100.0
    ) -> List[TradeSignal]:
        """Filter signals by minimum market liquidity.

        Args:
            signals: List of trade signals
            min_liquidity: Minimum liquidity in USDC

        Returns:
            Filtered signals
        """
        return [s for s in signals if s.market.liquidity >= min_liquidity]

    def filter_by_time_to_resolution(
        self, signals: List[TradeSignal], min_hours: float = 2.0, max_hours: float = 168.0
    ) -> List[TradeSignal]:
        """Filter signals by time until market resolution.

        Args:
            signals: List of trade signals
            min_hours: Minimum hours until resolution (avoid last-minute markets)
            max_hours: Maximum hours until resolution (avoid distant markets)

        Returns:
            Filtered signals
        """
        from datetime import timedelta, timezone

        now = datetime.now(timezone.utc)
        filtered = []

        for signal in signals:
            hours_until = (signal.market.end_date - now).total_seconds() / 3600

            if min_hours <= hours_until <= max_hours:
                filtered.append(signal)

        return filtered
