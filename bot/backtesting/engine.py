"""Backtesting engine for strategy simulation."""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict

from bot.utils.logger import get_logger


@dataclass
class BacktestParams:
    """Parameters for backtesting."""

    # Price thresholds
    yes_min_price: float = 0.03
    yes_max_price: float = 0.12
    no_min_yes_price: float = 0.50

    # Edge threshold
    min_edge: float = 0.10

    # Trade type filters
    skip_yes_on_threshold: bool = False
    prefer_no_on_range: bool = True

    # Position sizing
    min_position: float = 1.50
    max_position: float = 2.50
    aggressive_max: float = 5.00

    def to_dict(self) -> Dict[str, Any]:
        return {
            "yes_min_price": self.yes_min_price,
            "yes_max_price": self.yes_max_price,
            "no_min_yes_price": self.no_min_yes_price,
            "min_edge": self.min_edge,
            "skip_yes_on_threshold": self.skip_yes_on_threshold,
            "prefer_no_on_range": self.prefer_no_on_range,
            "min_position": self.min_position,
            "max_position": self.max_position,
            "aggressive_max": self.aggressive_max,
        }


@dataclass
class BacktestResult:
    """Results from a backtest run."""

    params: BacktestParams
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    pending: int = 0
    total_pnl: float = 0.0
    total_invested: float = 0.0

    # Breakdown by category
    breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Individual trade results
    trades: List[Dict[str, Any]] = field(default_factory=list)

    # Skipped trades (for analysis)
    skipped: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        resolved = self.wins + self.losses
        return self.wins / resolved if resolved > 0 else 0.0

    @property
    def roi(self) -> float:
        return self.total_pnl / self.total_invested if self.total_invested > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "pending": self.pending,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "total_invested": self.total_invested,
            "roi": self.roi,
            "breakdown": self.breakdown,
        }


class BacktestEngine:
    """Engine for running backtests against historical data."""

    def __init__(self, trades_db_path: str = "data/trades.db"):
        """Initialize backtesting engine.

        Args:
            trades_db_path: Path to trades database
        """
        self.trades_db_path = trades_db_path
        self.logger = get_logger()

    def load_trades(
        self,
        simulation_only: bool = True,
        resolved_only: bool = True,
        platform: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Load trades from database.

        Args:
            simulation_only: Only load simulation trades
            resolved_only: Only load resolved trades
            platform: Filter by platform

        Returns:
            List of trade dictionaries
        """
        conn = sqlite3.connect(self.trades_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if simulation_only:
            query += " AND simulation = 1"
        if resolved_only:
            query += " AND resolved = 1"
        if platform:
            query += " AND platform = ?"
            params.append(platform)

        query += " ORDER BY timestamp"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def run_backtest(
        self,
        params: Optional[BacktestParams] = None,
        trades: Optional[List[Dict[str, Any]]] = None,
    ) -> BacktestResult:
        """Run a backtest with given parameters.

        Args:
            params: Backtest parameters (uses defaults if None)
            trades: Trades to backtest (loads from DB if None)

        Returns:
            BacktestResult with outcomes
        """
        params = params or BacktestParams()
        trades = trades or self.load_trades()

        result = BacktestResult(params=params)
        result.skipped = defaultdict(list)

        for trade in trades:
            # Extract trade info
            price = trade["price"]
            market_id = trade["market_id"]
            token_id = trade["token_id"] or ""
            fair_prob = trade["fair_probability"] or 0
            cost = trade["cost"]
            won = trade["won"]
            pnl = trade["pnl"] or 0

            is_yes = "_YES" in token_id
            is_no = "_NO" in token_id
            is_range = "-B" in market_id
            is_threshold = "-T" in market_id

            # Determine the YES price for this trade
            if is_yes:
                yes_price = price
            else:  # NO trade
                yes_price = 1 - price  # If NO costs X, YES costs 1-X

            # Calculate edge (for YES trades, edge = fair_prob - price)
            # For NO trades stored in DB, we need to recalculate
            if is_yes:
                edge = fair_prob - price if fair_prob else 0
            else:
                # For NO, fair_prob in DB is for NO, edge is fair_prob_no - no_price
                edge = fair_prob - price if fair_prob else 0

            # Apply filters
            skip_reason = None

            # Filter 1: Minimum price for YES trades
            if is_yes and yes_price < params.yes_min_price:
                skip_reason = "sub_min_price"

            # Filter 2: Maximum price for YES trades
            elif is_yes and yes_price >= params.yes_max_price:
                skip_reason = "above_max_price"

            # Filter 3: Minimum YES price for NO trades
            elif is_no and yes_price <= params.no_min_yes_price:
                skip_reason = "yes_not_expensive_enough"

            # Filter 4: Skip YES on threshold
            elif is_yes and is_threshold and params.skip_yes_on_threshold:
                skip_reason = "yes_on_threshold"

            # Filter 5: Minimum edge
            elif edge < params.min_edge:
                skip_reason = "below_min_edge"

            if skip_reason:
                result.skipped[skip_reason].append({
                    "market_id": market_id,
                    "price": price,
                    "won": won,
                    "pnl": pnl,
                    "cost": cost,
                    "is_yes": is_yes,
                    "is_range": is_range,
                })
                continue

            # Trade passes filters - include in results
            # Recalculate position size based on params
            if is_yes:
                position_size = self._calculate_yes_position(yes_price, params)
            else:
                position_size = self._calculate_no_position(yes_price, params)

            # Scale P&L by position size ratio
            original_cost = cost
            scale_factor = position_size / original_cost if original_cost > 0 else 1
            scaled_pnl = pnl * scale_factor if pnl else 0
            scaled_cost = position_size

            result.trades.append({
                "market_id": market_id,
                "price": price,
                "position_size": position_size,
                "won": won,
                "pnl": scaled_pnl,
                "cost": scaled_cost,
                "is_yes": is_yes,
                "is_no": is_no,
                "is_range": is_range,
                "is_threshold": is_threshold,
            })

            result.total_trades += 1
            result.total_invested += scaled_cost

            if won is None:
                result.pending += 1
            elif won:
                result.wins += 1
                result.total_pnl += scaled_pnl
            else:
                result.losses += 1
                result.total_pnl += scaled_pnl

        # Calculate breakdown by category
        result.breakdown = self._calculate_breakdown(result.trades)

        return result

    def _calculate_yes_position(self, yes_price: float, params: BacktestParams) -> float:
        """Calculate position size for YES trades."""
        if yes_price <= 0.05:
            return params.aggressive_max
        elif yes_price <= 0.08:
            return params.max_position
        elif yes_price <= 0.10:
            return params.max_position
        elif yes_price <= 0.12:
            return params.max_position * 0.75
        else:
            return params.min_position

    def _calculate_no_position(self, yes_price: float, params: BacktestParams) -> float:
        """Calculate position size for NO trades."""
        if yes_price >= 0.60:
            return params.aggressive_max
        elif yes_price >= 0.55:
            return params.max_position
        elif yes_price >= 0.50:
            return params.max_position
        else:
            return params.min_position

    def _calculate_breakdown(self, trades: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Calculate performance breakdown by category."""
        categories = {
            "NO_RANGE": lambda t: t["is_no"] and t["is_range"],
            "NO_THRESHOLD": lambda t: t["is_no"] and t["is_threshold"],
            "YES_RANGE": lambda t: t["is_yes"] and t["is_range"],
            "YES_THRESHOLD": lambda t: t["is_yes"] and t["is_threshold"],
        }

        breakdown = {}
        for cat_name, cat_filter in categories.items():
            cat_trades = [t for t in trades if cat_filter(t)]
            if cat_trades:
                wins = sum(1 for t in cat_trades if t["won"])
                losses = sum(1 for t in cat_trades if t["won"] is False)
                pnl = sum(t["pnl"] or 0 for t in cat_trades)
                invested = sum(t["cost"] for t in cat_trades)

                breakdown[cat_name] = {
                    "trades": len(cat_trades),
                    "wins": wins,
                    "losses": losses,
                    "win_rate": wins / (wins + losses) if (wins + losses) > 0 else 0,
                    "pnl": pnl,
                    "invested": invested,
                    "roi": pnl / invested if invested > 0 else 0,
                }

        return breakdown

    def compare_strategies(
        self,
        param_sets: List[BacktestParams],
        names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Compare multiple strategy configurations.

        Args:
            param_sets: List of parameter configurations to test
            names: Optional names for each configuration

        Returns:
            List of results with comparisons
        """
        trades = self.load_trades()
        results = []

        for i, params in enumerate(param_sets):
            name = names[i] if names and i < len(names) else f"Strategy {i+1}"
            result = self.run_backtest(params, trades)

            results.append({
                "name": name,
                "params": params.to_dict(),
                "trades": result.total_trades,
                "wins": result.wins,
                "win_rate": result.win_rate,
                "pnl": result.total_pnl,
                "invested": result.total_invested,
                "roi": result.roi,
                "breakdown": result.breakdown,
                "skipped_counts": {k: len(v) for k, v in result.skipped.items()},
            })

        return results

    def print_comparison(self, results: List[Dict[str, Any]]):
        """Print a formatted comparison of backtest results."""
        print("\n" + "=" * 80)
        print("STRATEGY COMPARISON")
        print("=" * 80)

        # Header
        print(f"\n{'Strategy':<25} {'Trades':>8} {'Wins':>6} {'Win%':>7} {'P&L':>10} {'ROI':>8}")
        print("-" * 80)

        for r in results:
            print(f"{r['name']:<25} {r['trades']:>8} {r['wins']:>6} "
                  f"{r['win_rate']*100:>6.1f}% ${r['pnl']:>+9.2f} {r['roi']*100:>+7.1f}%")

        # Best strategy
        best = max(results, key=lambda x: x["pnl"])
        print("-" * 80)
        print(f"Best: {best['name']} with ${best['pnl']:+.2f} P&L ({best['roi']*100:+.1f}% ROI)")

        # Show what each strategy skipped
        print("\n" + "-" * 80)
        print("SKIPPED TRADES BY REASON:")
        print("-" * 80)
        for r in results:
            skipped = r.get("skipped_counts", {})
            if skipped:
                skip_str = ", ".join(f"{k}: {v}" for k, v in skipped.items())
                print(f"{r['name']:<25}: {skip_str}")
