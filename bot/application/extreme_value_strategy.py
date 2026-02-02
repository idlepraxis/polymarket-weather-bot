"""Extreme value betting strategy - forecast-driven approach.

Strategy:
- Buy YES shares ONLY when price < 0.10-0.15 (10-15¢) AND forecast shows edge
- Buy NO shares ONLY when YES price > 0.40-0.50 AND forecast shows edge
- CRITICAL: Only trade when weather forecast provides minimum edge threshold
- No fallback heuristics - actual forecast data required for every trade
- Keep position sizes small (~$2.50 per trade)
- Quality over quantity - fewer trades with real edge

This combines price-based opportunity detection with forecast-based edge validation.
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
        self.yes_min_price = getattr(config, "extreme_yes_min_price", 0.03)  # v2.5.0: Skip sub-3¢ traps
        self.yes_ideal_price = getattr(config, "extreme_yes_ideal_price", 0.10)
        self.no_min_yes_price = getattr(config, "extreme_no_min_yes_price", 0.40)
        self.no_ideal_yes_price = getattr(config, "extreme_no_ideal_yes_price", 0.50)
        self.no_min_price = getattr(config, "extreme_no_min_price", 0.03)  # v2.5.1: Skip sub-3¢ NO traps

        # Position sizing (target ~$1 average per trade)
        self.min_position = getattr(config, "extreme_min_position", 0.50)  # $0.50
        self.max_position = getattr(config, "extreme_max_position", 1.00)  # $1.00
        self.aggressive_max = getattr(config, "extreme_aggressive_max", 1.50)  # $1.50 for great opportunities

        # Trade type preferences (v2.5.0)
        self.prefer_no_on_range = getattr(config, "prefer_no_on_range", True)
        self.skip_yes_on_threshold = getattr(config, "skip_yes_on_threshold", False)

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

        # v2.5.0: Sort with preference for NO on RANGE markets (proven 18.2% win rate)
        # Range markets have "-B" in the market ID (bucket/range)
        def sort_key(s: TradeSignal) -> tuple:
            is_no_bet = s.token_id and "_NO" in str(s.token_id)
            is_range = "-B" in s.market.market_id

            # Priority: NO+RANGE > NO+THRESHOLD > YES+any
            if self.prefer_no_on_range:
                priority = 0 if (is_no_bet and is_range) else (1 if is_no_bet else 2)
            else:
                priority = 0  # No preference, just use EV

            return (priority, -self._calculate_ev(s))  # Lower priority first, then higher EV

        signals.sort(key=sort_key)

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

        # v2.5.0: Skip sub-3¢ trap trades (0% historical win rate)
        if yes_price < self.yes_min_price:
            self.logger.debug(
                f"SKIP {market.market_id}: Price {yes_price:.1%} below minimum {self.yes_min_price:.1%} (sub-3¢ trap)"
            )
            return None

        # v2.5.0: Check if this is a threshold market and if we should skip YES threshold bets
        is_threshold_market = "-T" in market.market_id or "-T" in str(market.yes_token_id or "")
        if self.skip_yes_on_threshold and is_threshold_market:
            self.logger.debug(
                f"SKIP {market.market_id}: YES on threshold market (skip_yes_on_threshold=True)"
            )
            return None

        # Calculate position size based on how cheap it is
        position_size = self._calculate_yes_position_size(yes_price)

        # Get forecast to estimate fair probability (if available)
        fair_prob = self._estimate_fair_probability(market, outcome="YES")

        # Calculate edge
        edge = fair_prob - yes_price

        # STRICT: Only trade with real forecast-based edge
        # No fallback heuristics - we need actual weather data to have edge
        min_edge = getattr(self.config, "min_edge_threshold", 0.10)
        if edge < min_edge:
            self.logger.debug(
                f"SKIP {market.market_id}: Edge {edge:.1%} < min {min_edge:.1%} "
                f"(fair={fair_prob:.1%}, market={yes_price:.1%})"
            )
            return None

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

        # v2.5.1: Skip sub-3¢ NO trap trades (same logic as YES minimum)
        # If YES is 97%+, NO costs only 3¢ - these are traps just like cheap YES
        if no_price < self.no_min_price:
            self.logger.debug(
                f"SKIP {market.market_id}: NO price {no_price:.1%} below minimum {self.no_min_price:.1%} (sub-3¢ trap)"
            )
            return None

        # Calculate position size based on how expensive YES is
        position_size = self._calculate_no_position_size(yes_price)

        # Get forecast to estimate fair probability
        fair_prob_yes = self._estimate_fair_probability(market, outcome="YES")
        fair_prob_no = 1 - fair_prob_yes

        # Edge for NO shares
        edge = fair_prob_no - no_price

        # STRICT: Only trade with real forecast-based edge
        # No fallback heuristics - we need actual weather data to have edge
        min_edge = getattr(self.config, "min_edge_threshold", 0.10)
        if edge < min_edge:
            self.logger.debug(
                f"SKIP {market.market_id}: NO edge {edge:.1%} < min {min_edge:.1%} "
                f"(fair_no={fair_prob_no:.1%}, market_no={no_price:.1%})"
            )
            return None

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

        v2.5.2: INVERTED logic based on actual win rate data:
        - 3-5¢: 0% win rate historically → minimum position (risky traps)
        - 5-8¢: 18% win rate + great payoff → max position
        - 8-10¢: decent → max position
        - 10-12¢: 20% win rate (best!) → aggressive position
        - >12¢: lower payoff ratio → minimum position
        """
        if yes_price < 0.05:  # 3-5¢ range - HIGH RISK (was 0% win rate)
            size = self.min_position
        elif yes_price <= 0.08:  # 5-8¢ - good win rate + great payoff
            size = self.max_position
        elif yes_price <= 0.10:  # 8-10¢ - decent
            size = self.max_position
        elif yes_price <= 0.12:  # 10-12¢ - BEST win rate (20%)
            size = self.aggressive_max
        else:  # >12¢ - lower payoff ratio
            size = self.min_position

        return round(size, 2)

    def _calculate_no_position_size(self, yes_price: float) -> float:
        """Calculate position size for NO purchases.

        v2.5.2: INVERTED logic based on YES position sizing insights:
        - YES >90% (NO <10¢): TRAP - same as cheap YES, minimum position
        - YES 70-90% (NO 10-30¢): Risky - minimum position
        - YES 60-70% (NO 30-40¢): Good sweet spot - max position
        - YES 55-60% (NO 40-45¢): Best balance - aggressive position
        - YES 50-55% (NO 45-50¢): Lower payoff - max position
        """
        no_price = 1 - yes_price

        # Mirror the YES logic: very cheap NO (<10¢) are traps
        if no_price < 0.10:  # YES >90%, NO <10¢ - TRAP
            size = self.min_position
        elif no_price < 0.30:  # YES 70-90%, NO 10-30¢ - risky
            size = self.min_position
        elif no_price < 0.40:  # YES 60-70%, NO 30-40¢ - good
            size = self.max_position
        elif no_price < 0.45:  # YES 55-60%, NO 40-45¢ - sweet spot
            size = self.aggressive_max
        else:  # YES 50-55%, NO 45-50¢ - moderate payoff
            size = self.max_position

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
            # Note: use "is None" since threshold=0 is valid (0°F)
            if parsed["threshold"] is None and not parsed["is_range"]:
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
