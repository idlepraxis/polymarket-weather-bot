"""Wallet analyzer for reverse engineering trading strategies from Polymarket wallets."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from statistics import mean, median, stdev

import httpx

from bot.utils.logger import get_logger


@dataclass
class TradeAnalysis:
    """Analysis of a single trade."""
    market_id: str
    market_question: str
    side: str  # YES or NO
    entry_price: float
    position_size: float
    timestamp: datetime
    outcome: Optional[str] = None  # 'won', 'lost', or None if pending
    pnl: Optional[float] = None
    market_type: Optional[str] = None  # 'weather', 'sports', 'politics', etc.


@dataclass
class StrategyProfile:
    """Complete strategy profile for a wallet."""

    # Basic Stats
    total_trades: int
    total_volume: float
    total_pnl: float
    win_rate: float
    avg_profit_per_trade: float

    # Entry Thresholds (for extreme value strategy)
    yes_entry_prices: List[float]  # All YES entry prices
    no_entry_prices: List[float]   # All NO entry prices (as complement, so if YES=0.60, NO=0.40)
    avg_yes_entry: float
    median_yes_entry: float
    yes_10th_percentile: float  # Lowest 10% of YES entries
    yes_90th_percentile: float  # Highest 10% of YES entries
    avg_no_entry: float
    median_no_entry: float

    # Position Sizing
    position_sizes: List[float]
    avg_position_size: float
    median_position_size: float
    min_position_size: float
    max_position_size: float
    position_size_stddev: float

    # Market Selection
    market_categories: Dict[str, int]  # Category -> count
    weather_trades: int
    weather_percentage: float

    # Trading Frequency
    trades_per_day: float
    first_trade_date: datetime
    last_trade_date: datetime
    trading_days: int

    # Risk Management
    max_daily_exposure: float
    avg_daily_exposure: float
    max_single_position_pct: float  # As % of total volume

    # Performance by Price Range
    yes_low_performance: Dict[str, Any]  # YES < 0.15
    yes_mid_performance: Dict[str, Any]  # YES 0.15-0.40
    no_performance: Dict[str, Any]  # When buying NO (YES > 0.40)

    # Raw trades for detailed analysis
    trades: List[TradeAnalysis]


class WalletAnalyzer:
    """Analyzes Polymarket wallets to reverse engineer trading strategies."""

    def __init__(self):
        self.logger = get_logger()
        self.http_client = httpx.Client(timeout=30.0)

        # Polymarket Subgraph endpoints
        self.subgraph_url = "https://api.thegraph.com/subgraphs/name/polymarket/polymarket-subgraph"

    def analyze_wallet(self, wallet_address: str, limit: int = 1000) -> StrategyProfile:
        """
        Analyze a wallet's trading strategy.

        Args:
            wallet_address: Ethereum wallet address (0x...)
            limit: Maximum number of trades to fetch

        Returns:
            StrategyProfile with complete strategy analysis
        """
        self.logger.info(f"Analyzing wallet: {wallet_address}")

        # Fetch trades from wallet
        trades = self._fetch_wallet_trades(wallet_address, limit)

        if not trades:
            self.logger.warning(f"No trades found for wallet {wallet_address}")
            return self._empty_profile()

        self.logger.info(f"Found {len(trades)} trades, analyzing...")

        # Analyze strategy
        profile = self._analyze_strategy(trades)

        return profile

    def _fetch_wallet_trades(self, wallet_address: str, limit: int) -> List[TradeAnalysis]:
        """Fetch all trades from a wallet using Polymarket API."""
        trades = []

        # Try multiple API endpoints
        endpoints = [
            {
                "name": "Data API - Activity",
                "url": "https://data-api.polymarket.com/activity",
                "method": "activity"
            },
            {
                "name": "Data API - Trades",
                "url": "https://data-api.polymarket.com/trades",
                "method": "trades"
            },
        ]

        for endpoint in endpoints:
            try:
                if endpoint["method"] == "activity" or endpoint["method"] == "trades":
                    url = endpoint["url"]
                    params = {
                        "user": wallet_address.lower(),
                        "limit": limit
                    }

                    self.logger.debug(f"Fetching from {endpoint['name']}: {url}")
                    response = self.http_client.get(url, params=params)

                    if response.status_code == 200:
                        data = response.json()
                        self.logger.info(f"Fetched {len(data)} trades from {endpoint['name']}")

                        for trade_data in data:
                            trade = self._parse_trade(trade_data)
                            if trade:
                                trades.append(trade)

                        if trades:
                            return trades
                    else:
                        self.logger.warning(f"{endpoint['name']} returned status {response.status_code}")

            except Exception as e:
                self.logger.debug(f"Error with {endpoint['name']}: {e}")
                continue

        # If Polymarket APIs didn't work, try The Graph subgraph
        if not trades:
            self.logger.info("Attempting to fetch from Polymarket subgraph...")
            trades = self._fetch_from_subgraph(wallet_address, limit)

        return trades

    def _fetch_from_subgraph(self, wallet_address: str, limit: int) -> List[TradeAnalysis]:
        """Fetch trades from The Graph subgraph."""
        trades = []

        query = """
        query GetUserTrades($user: String!, $limit: Int!) {
          trades(
            where: { user: $user }
            first: $limit
            orderBy: timestamp
            orderDirection: desc
          ) {
            id
            market {
              id
              question
              category
            }
            outcome
            shares
            price
            timestamp
            makerAmount
            takerAmount
          }
        }
        """

        variables = {
            "user": wallet_address.lower(),
            "limit": limit
        }

        try:
            response = self.http_client.post(
                self.subgraph_url,
                json={"query": query, "variables": variables}
            )

            if response.status_code == 200:
                data = response.json()

                if "data" in data and "trades" in data["data"]:
                    for trade_data in data["data"]["trades"]:
                        trade = self._parse_subgraph_trade(trade_data)
                        if trade:
                            trades.append(trade)

                    self.logger.info(f"Fetched {len(trades)} trades from subgraph")

        except Exception as e:
            self.logger.error(f"Error fetching from subgraph: {e}")

        return trades

    def _parse_trade(self, trade_data: Dict) -> Optional[TradeAnalysis]:
        """Parse trade data from Polymarket API."""
        try:
            # Determine side (YES or NO)
            side = trade_data.get("side", "").upper()
            if side not in ["YES", "NO"]:
                side = "BUY"  # Default

            # Parse timestamp - Data API returns Unix timestamp (integer seconds)
            timestamp_value = trade_data.get("timestamp", 0)
            try:
                # Try parsing as Unix timestamp first (Data API format)
                if isinstance(timestamp_value, (int, float)):
                    timestamp = datetime.fromtimestamp(timestamp_value)
                # Fall back to ISO string format
                elif isinstance(timestamp_value, str):
                    timestamp = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
                else:
                    timestamp = datetime.now()
            except:
                timestamp = datetime.now()

            # Data API uses different field names than CLOB API
            market_id = trade_data.get("conditionId") or trade_data.get("market", "")
            market_question = trade_data.get("title") or trade_data.get("market_question", "Unknown")
            # Use usdcSize for dollar amount, fall back to size
            position_size = float(trade_data.get("usdcSize") or trade_data.get("size", 0))

            return TradeAnalysis(
                market_id=market_id,
                market_question=market_question,
                side=side,
                entry_price=float(trade_data.get("price", 0)),
                position_size=position_size,
                timestamp=timestamp,
                market_type=self._classify_market(market_question),
            )

        except Exception as e:
            self.logger.debug(f"Error parsing trade: {e}")
            return None

    def _parse_subgraph_trade(self, trade_data: Dict) -> Optional[TradeAnalysis]:
        """Parse trade data from subgraph."""
        try:
            market = trade_data.get("market", {})

            return TradeAnalysis(
                market_id=market.get("id", ""),
                market_question=market.get("question", "Unknown"),
                side=trade_data.get("outcome", "YES"),
                entry_price=float(trade_data.get("price", 0)),
                position_size=float(trade_data.get("shares", 0)) * float(trade_data.get("price", 0)),
                timestamp=datetime.fromtimestamp(int(trade_data.get("timestamp", 0))),
                market_type=self._classify_market(market.get("question", "")),
            )

        except Exception as e:
            self.logger.debug(f"Error parsing subgraph trade: {e}")
            return None

    def _classify_market(self, question: str) -> str:
        """Classify market type based on question."""
        question_lower = question.lower()

        # Weather keywords
        weather_keywords = [
            'temperature', 'temp', 'degrees', 'fahrenheit', 'celsius',
            'rain', 'snow', 'precipitation', 'weather', 'forecast',
            'high', 'low', 'exceed', 'above', 'below', 'climate'
        ]

        if any(keyword in question_lower for keyword in weather_keywords):
            return 'weather'
        elif any(sport in question_lower for sport in ['nfl', 'nba', 'mlb', 'soccer', 'football']):
            return 'sports'
        elif any(pol in question_lower for pol in ['election', 'vote', 'president', 'congress']):
            return 'politics'
        else:
            return 'other'

    def _analyze_strategy(self, trades: List[TradeAnalysis]) -> StrategyProfile:
        """Analyze trades to extract strategy profile."""

        if not trades:
            return self._empty_profile()

        # Basic stats
        total_trades = len(trades)
        total_volume = sum(t.position_size for t in trades)

        # Calculate P&L if we have outcome data
        total_pnl = sum(t.pnl for t in trades if t.pnl is not None) if any(t.pnl is not None for t in trades) else 0
        wins = len([t for t in trades if t.outcome == 'won'])
        losses = len([t for t in trades if t.outcome == 'lost'])
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        avg_profit = total_pnl / total_trades if total_trades > 0 else 0

        # Entry thresholds
        yes_entries = [t.entry_price for t in trades if t.side == "YES"]
        no_entries = [1 - t.entry_price for t in trades if t.side == "NO"]  # Convert to NO price

        # Position sizing
        position_sizes = [t.position_size for t in trades]

        # Market categories
        market_categories = defaultdict(int)
        for trade in trades:
            market_categories[trade.market_type or 'unknown'] += 1

        weather_trades = market_categories.get('weather', 0)

        # Trading frequency
        sorted_trades = sorted(trades, key=lambda t: t.timestamp)
        first_trade = sorted_trades[0].timestamp
        last_trade = sorted_trades[-1].timestamp
        trading_days = (last_trade - first_trade).days or 1
        trades_per_day = total_trades / trading_days

        # Daily exposure analysis
        daily_exposure = defaultdict(float)
        for trade in trades:
            date_key = trade.timestamp.date()
            daily_exposure[date_key] += trade.position_size

        # Performance by price range
        yes_low = [t for t in trades if t.side == "YES" and t.entry_price <= 0.15]
        yes_mid = [t for t in trades if t.side == "YES" and 0.15 < t.entry_price <= 0.40]
        no_trades = [t for t in trades if t.side == "NO"]

        return StrategyProfile(
            total_trades=total_trades,
            total_volume=total_volume,
            total_pnl=total_pnl,
            win_rate=win_rate,
            avg_profit_per_trade=avg_profit,

            # Entry thresholds
            yes_entry_prices=yes_entries,
            no_entry_prices=no_entries,
            avg_yes_entry=mean(yes_entries) if yes_entries else 0,
            median_yes_entry=median(yes_entries) if yes_entries else 0,
            yes_10th_percentile=sorted(yes_entries)[int(len(yes_entries) * 0.1)] if yes_entries else 0,
            yes_90th_percentile=sorted(yes_entries)[int(len(yes_entries) * 0.9)] if yes_entries else 0,
            avg_no_entry=mean(no_entries) if no_entries else 0,
            median_no_entry=median(no_entries) if no_entries else 0,

            # Position sizing
            position_sizes=position_sizes,
            avg_position_size=mean(position_sizes) if position_sizes else 0,
            median_position_size=median(position_sizes) if position_sizes else 0,
            min_position_size=min(position_sizes) if position_sizes else 0,
            max_position_size=max(position_sizes) if position_sizes else 0,
            position_size_stddev=stdev(position_sizes) if len(position_sizes) > 1 else 0,

            # Market selection
            market_categories=dict(market_categories),
            weather_trades=weather_trades,
            weather_percentage=weather_trades / total_trades if total_trades > 0 else 0,

            # Trading frequency
            trades_per_day=trades_per_day,
            first_trade_date=first_trade,
            last_trade_date=last_trade,
            trading_days=trading_days,

            # Risk management
            max_daily_exposure=max(daily_exposure.values()) if daily_exposure else 0,
            avg_daily_exposure=mean(daily_exposure.values()) if daily_exposure else 0,
            max_single_position_pct=(max(position_sizes) / total_volume * 100) if total_volume > 0 else 0,

            # Performance by range
            yes_low_performance=self._calc_range_performance(yes_low),
            yes_mid_performance=self._calc_range_performance(yes_mid),
            no_performance=self._calc_range_performance(no_trades),

            # Raw data
            trades=trades,
        )

    def _calc_range_performance(self, trades: List[TradeAnalysis]) -> Dict[str, Any]:
        """Calculate performance metrics for a subset of trades."""
        if not trades:
            return {
                'count': 0,
                'avg_entry': 0,
                'avg_size': 0,
                'total_volume': 0,
            }

        return {
            'count': len(trades),
            'avg_entry': mean([t.entry_price for t in trades]),
            'avg_size': mean([t.position_size for t in trades]),
            'total_volume': sum([t.position_size for t in trades]),
        }

    def _empty_profile(self) -> StrategyProfile:
        """Return an empty strategy profile."""
        return StrategyProfile(
            total_trades=0,
            total_volume=0,
            total_pnl=0,
            win_rate=0,
            avg_profit_per_trade=0,
            yes_entry_prices=[],
            no_entry_prices=[],
            avg_yes_entry=0,
            median_yes_entry=0,
            yes_10th_percentile=0,
            yes_90th_percentile=0,
            avg_no_entry=0,
            median_no_entry=0,
            position_sizes=[],
            avg_position_size=0,
            median_position_size=0,
            min_position_size=0,
            max_position_size=0,
            position_size_stddev=0,
            market_categories={},
            weather_trades=0,
            weather_percentage=0,
            trades_per_day=0,
            first_trade_date=datetime.now(),
            last_trade_date=datetime.now(),
            trading_days=0,
            max_daily_exposure=0,
            avg_daily_exposure=0,
            max_single_position_pct=0,
            yes_low_performance={},
            yes_mid_performance={},
            no_performance={},
            trades=[],
        )
