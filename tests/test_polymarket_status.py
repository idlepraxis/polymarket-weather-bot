"""Integration tests for Polymarket market status checking.

These tests hit the real Gamma API but avoid slow blockchain initialization.
"""

import pytest
import httpx
from datetime import datetime

from bot.utils.config import Config


@pytest.fixture
def config():
    """Load configuration from environment."""
    return Config()


@pytest.fixture
def gamma_api_url(config):
    """Get Gamma API URL from config."""
    return getattr(config, 'gamma_api_url', 'https://gamma-api.polymarket.com')


class TestGammaAPI:
    """Direct integration tests for Gamma API (fast, no blockchain)."""

    def test_fetch_markets(self, gamma_api_url):
        """Test fetching markets from Gamma API."""
        response = httpx.get(
            f"{gamma_api_url}/markets",
            params={"closed": False, "limit": 10},
            timeout=30.0,
        )

        assert response.status_code == 200, f"API returned {response.status_code}"

        markets = response.json()
        assert isinstance(markets, list), "Should return a list"
        assert len(markets) > 0, "Should have at least one market"

        print(f"\nFetched {len(markets)} markets:")
        for m in markets[:5]:
            question = m.get('question', 'N/A')[:60]
            closed = m.get('closed', False)
            market_id = m.get('id', 'N/A')[:16]
            print(f"  [{market_id}...] closed={closed} - {question}...")

    def test_fetch_single_market(self, gamma_api_url):
        """Test fetching a single market by ID."""
        # First get a market ID from the list
        list_response = httpx.get(
            f"{gamma_api_url}/markets",
            params={"closed": False, "limit": 1},
            timeout=30.0,
        )
        markets = list_response.json()
        assert len(markets) > 0, "Need at least one market"

        market_id = markets[0].get('id')
        assert market_id, "Market should have an ID"

        # Now fetch that specific market
        response = httpx.get(
            f"{gamma_api_url}/markets/{market_id}",
            timeout=30.0,
        )

        assert response.status_code == 200, f"API returned {response.status_code}"

        market = response.json()
        print(f"\nFetched single market: {market_id}")
        print(f"  Question: {market.get('question', 'N/A')[:80]}...")
        print(f"  Closed: {market.get('closed')}")
        print(f"  Resolved: {market.get('resolved')}")
        print(f"  Outcome Prices: {market.get('outcomePrices')}")
        print(f"  Outcomes: {market.get('outcomes')}")

    def test_market_structure(self, gamma_api_url):
        """Test that market data has expected fields."""
        response = httpx.get(
            f"{gamma_api_url}/markets",
            params={"closed": False, "limit": 1},
            timeout=30.0,
        )
        markets = response.json()
        market = markets[0]

        print(f"\nMarket keys: {sorted(market.keys())}")

        # Check expected fields exist
        assert 'question' in market, "Should have 'question'"
        assert 'outcomes' in market, "Should have 'outcomes'"
        assert 'outcomePrices' in market, "Should have 'outcomePrices'"

    def test_market_resolution_logic(self, gamma_api_url):
        """Test the resolution detection logic with real data."""
        response = httpx.get(
            f"{gamma_api_url}/markets",
            params={"closed": False, "limit": 10},
            timeout=30.0,
        )
        markets = response.json()

        print(f"\nTesting resolution logic on {len(markets)} markets:")

        for market in markets:
            is_closed = market.get('closed', False)
            is_resolved = market.get('resolved', False)
            outcome_prices = market.get('outcomePrices', [])
            outcomes = market.get('outcomes', ['Yes', 'No'])

            # Determine if resolved based on prices
            resolved_by_price = False
            winning_outcome = None

            if outcome_prices and len(outcome_prices) >= 2:
                max_price = 0.0
                winning_idx = 0
                for idx, price_str in enumerate(outcome_prices):
                    try:
                        price = float(price_str)
                        if price > max_price:
                            max_price = price
                            winning_idx = idx
                    except (ValueError, TypeError):
                        continue

                if max_price >= 0.99:
                    resolved_by_price = True
                    winning_outcome = outcomes[winning_idx].lower() if winning_idx < len(outcomes) else None

            question = market.get('question', 'N/A')[:50]
            print(f"  closed={is_closed}, resolved={is_resolved}, "
                  f"price_resolved={resolved_by_price}, winner={winning_outcome} - {question}...")


class TestPolymarketStatusLogic:
    """Test the _get_polymarket_status logic without full client init."""

    def test_status_logic_open_market(self, gamma_api_url):
        """Test status logic with an open market."""
        # Fetch an open market
        response = httpx.get(
            f"{gamma_api_url}/markets",
            params={"closed": False, "limit": 5},
            timeout=30.0,
        )
        markets = response.json()
        market = markets[0]

        # Simulate _get_polymarket_status logic
        is_closed = market.get('closed', False)
        is_resolved = market.get('resolved', False)

        if not (is_closed or is_resolved):
            status = {'resolved': False, 'outcome': None}
        else:
            outcome_prices = market.get('outcomePrices', [])
            outcomes = market.get('outcomes', ['Yes', 'No'])

            winning_idx = 0
            max_price = 0.0
            for idx, price_str in enumerate(outcome_prices):
                try:
                    price = float(price_str)
                    if price > max_price:
                        max_price = price
                        winning_idx = idx
                except (ValueError, TypeError):
                    continue

            if max_price < 0.99:
                status = {'resolved': False, 'outcome': None}
            else:
                winning_outcome = outcomes[winning_idx].lower() if winning_idx < len(outcomes) else 'yes'
                status = {'resolved': True, 'outcome': winning_outcome}

        print(f"\nOpen market status test:")
        print(f"  Question: {market.get('question', 'N/A')[:60]}...")
        print(f"  Status: {status}")

        assert status['resolved'] == False, "Open market should not be resolved"

    def test_fetch_closed_markets(self, gamma_api_url):
        """Test fetching closed/resolved markets."""
        response = httpx.get(
            f"{gamma_api_url}/markets",
            params={"closed": True, "limit": 10},
            timeout=30.0,
        )

        if response.status_code != 200:
            pytest.skip("Could not fetch closed markets")

        markets = response.json()

        if not markets:
            pytest.skip("No closed markets found")

        print(f"\nFetched {len(markets)} closed markets:")

        for market in markets[:5]:
            outcome_prices = market.get('outcomePrices', [])
            outcomes = market.get('outcomes', ['Yes', 'No'])

            # Find winner
            max_price = 0.0
            winning_idx = 0
            for idx, price_str in enumerate(outcome_prices):
                try:
                    price = float(price_str)
                    if price > max_price:
                        max_price = price
                        winning_idx = idx
                except:
                    continue

            winner = outcomes[winning_idx] if winning_idx < len(outcomes) else "?"
            question = market.get('question', 'N/A')[:50]

            print(f"  Winner: {winner} (price={max_price:.2f}) - {question}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])