"""Integration tests for Polymarket resolution checking."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
import uuid

from bot.utils.models import Trade, TradeSide


class TestPolymarketResolution:
    """Integration tests for Polymarket market resolution flow."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = Mock()
        config.gamma_api_url = "https://gamma-api.polymarket.com"
        config.chainstack_rpc_url = "https://mock-rpc.example.com"
        config.chainstack_ws_url = "wss://mock-ws.example.com"
        config.polygon_wallet_private_key = "0x" + "a" * 64
        config.usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        config.clob_url = "https://clob.polymarket.com"
        config.chain_id = 137
        config.clob_api_key = "test_key"
        config.clob_secret = "test_secret"
        config.clob_pass_phrase = "test_passphrase"
        config.scan_interval_hours = 6
        config.resolution_check_hours = 0.25
        config.max_trades_per_scan = 20
        config.max_trades_per_day = 50
        config.max_trades_per_city = 3
        config.bankroll = 1000.0
        config.max_daily_exposure_pct = 5.0
        return config

    @pytest.fixture
    def bot_runner(self, mock_config):
        """Create a BotRunner with mocked dependencies."""
        with patch("bot.application.bot_runner.get_config") as mock_get_config, \
             patch("bot.application.bot_runner.setup_logger") as mock_logger, \
             patch("bot.application.bot_runner.TradeHistoryDB") as mock_db, \
             patch("bot.application.bot_runner.WeatherConnector") as mock_weather, \
             patch("bot.application.bot_runner.PolymarketClient") as mock_poly_client, \
             patch("bot.application.bot_runner.ExtremeValueStrategy") as mock_strategy:

            mock_get_config.return_value = mock_config
            mock_logger.return_value = MagicMock()

            # Setup Polymarket client mock
            mock_client_instance = MagicMock()
            mock_poly_client.return_value = mock_client_instance

            from bot.application.bot_runner import BotRunner
            runner = BotRunner(platform="polymarket", simulation=True)
            return runner

    def test_get_polymarket_status_resolved_yes_wins(self, bot_runner):
        """Test _get_polymarket_status when YES wins."""
        market_id = "test-market-123"

        # Mock market data where YES won (outcome price = 1)
        mock_market = {
            "id": market_id,
            "conditionId": "0xabc123",
            "question": "Will NYC temperature exceed 70°F?",
            "closed": True,
            "resolved": True,
            "outcomes": ["Yes", "No"],
            "outcomePrices": ["1", "0"],  # YES won
        }

        bot_runner.client.get_market.return_value = mock_market

        result = bot_runner._get_polymarket_status(market_id)

        assert result is not None
        assert result["resolved"] is True
        assert result["outcome"] == "yes"

    def test_get_polymarket_status_resolved_no_wins(self, bot_runner):
        """Test _get_polymarket_status when NO wins."""
        market_id = "test-market-456"

        # Mock market data where NO won
        mock_market = {
            "id": market_id,
            "conditionId": "0xdef456",
            "question": "Will it rain in Seattle?",
            "closed": True,
            "resolved": True,
            "outcomes": ["Yes", "No"],
            "outcomePrices": ["0", "1"],  # NO won
        }

        bot_runner.client.get_market.return_value = mock_market

        result = bot_runner._get_polymarket_status(market_id)

        assert result is not None
        assert result["resolved"] is True
        assert result["outcome"] == "no"

    def test_get_polymarket_status_not_resolved(self, bot_runner):
        """Test _get_polymarket_status for active market."""
        market_id = "test-market-789"

        # Mock active market (not resolved)
        mock_market = {
            "id": market_id,
            "conditionId": "0xghi789",
            "question": "Will Denver temperature exceed 50°F?",
            "closed": False,
            "resolved": False,
            "outcomes": ["Yes", "No"],
            "outcomePrices": ["0.65", "0.35"],  # Market still trading
        }

        bot_runner.client.get_market.return_value = mock_market

        result = bot_runner._get_polymarket_status(market_id)

        assert result is not None
        assert result["resolved"] is False

    def test_get_polymarket_status_market_not_found(self, bot_runner):
        """Test _get_polymarket_status when market doesn't exist."""
        market_id = "nonexistent-market"

        bot_runner.client.get_market.return_value = None

        result = bot_runner._get_polymarket_status(market_id)

        assert result is None

    def test_get_polymarket_status_clob_fallback(self, bot_runner):
        """Test _get_polymarket_status falls back to CLOB client."""
        market_id = "test-market-fallback"

        # Market without outcomePrices
        mock_market = {
            "id": market_id,
            "conditionId": "0xfallback123",
            "question": "Will Chicago see snow?",
            "closed": True,
            "resolved": True,
            "outcomes": ["Yes", "No"],
            "outcomePrices": [],  # No prices, trigger fallback
        }

        # CLOB fallback data
        mock_clob_market = {
            "closed": True,
            "tokens": [
                {"outcome": "Yes", "price": 1.0},
                {"outcome": "No", "price": 0.0},
            ]
        }

        bot_runner.client.get_market.return_value = mock_market
        bot_runner.client.clob_client.get_market.return_value = mock_clob_market

        result = bot_runner._get_polymarket_status(market_id)

        assert result is not None
        assert result["resolved"] is True
        assert result["outcome"] == "yes"

    def test_calculate_trade_outcome_yes_wins(self, bot_runner):
        """Test _calculate_trade_outcome when YES position wins."""
        trade = {
            "trade_id": "trade-123",
            "token_id": "yes_token_abc",
            "market_id": "market-123",
        }
        market_info = {"resolved": True, "outcome": "yes"}

        result = bot_runner._calculate_trade_outcome(trade, market_info)

        assert result is True  # Trade won

    def test_calculate_trade_outcome_yes_loses(self, bot_runner):
        """Test _calculate_trade_outcome when YES position loses."""
        trade = {
            "trade_id": "trade-456",
            "token_id": "yes_token_def",
            "market_id": "market-456",
        }
        market_info = {"resolved": True, "outcome": "no"}

        result = bot_runner._calculate_trade_outcome(trade, market_info)

        assert result is False  # Trade lost

    def test_calculate_trade_outcome_no_wins(self, bot_runner):
        """Test _calculate_trade_outcome when NO position wins."""
        trade = {
            "trade_id": "trade-789",
            "token_id": "no_token_ghi",
            "market_id": "market-789",
        }
        market_info = {"resolved": True, "outcome": "no"}

        result = bot_runner._calculate_trade_outcome(trade, market_info)

        assert result is True  # Trade won

    def test_calculate_trade_outcome_no_loses(self, bot_runner):
        """Test _calculate_trade_outcome when NO position loses."""
        trade = {
            "trade_id": "trade-101",
            "token_id": "no_token_jkl",
            "market_id": "market-101",
        }
        market_info = {"resolved": True, "outcome": "yes"}

        result = bot_runner._calculate_trade_outcome(trade, market_info)

        assert result is False  # Trade lost

    def test_calculate_pnl_win(self, bot_runner):
        """Test _calculate_pnl for winning trade."""
        trade = {
            "trade_id": "trade-pnl-1",
            "price": 0.10,  # Bought at 10 cents
            "size": 1.0,   # $1 position
            "cost": 1.0,
        }

        pnl = bot_runner._calculate_pnl(trade, won=True)

        # Bought at 10 cents, $1 position = 10 shares
        # Win pays $1 per share = $10 payout
        # Profit = $10 - $1 = $9
        assert pnl == 9.0

    def test_calculate_pnl_loss(self, bot_runner):
        """Test _calculate_pnl for losing trade."""
        trade = {
            "trade_id": "trade-pnl-2",
            "price": 0.25,
            "size": 2.0,
            "cost": 2.0,
        }

        pnl = bot_runner._calculate_pnl(trade, won=False)

        # Loss = -cost
        assert pnl == -2.0


class TestPolymarketResolutionIntegration:
    """Full integration test for resolution checking flow."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = Mock()
        config.gamma_api_url = "https://gamma-api.polymarket.com"
        config.chainstack_rpc_url = "https://mock-rpc.example.com"
        config.chainstack_ws_url = "wss://mock-ws.example.com"
        config.polygon_wallet_private_key = "0x" + "a" * 64
        config.usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        config.clob_url = "https://clob.polymarket.com"
        config.chain_id = 137
        config.clob_api_key = "test_key"
        config.clob_secret = "test_secret"
        config.clob_pass_phrase = "test_passphrase"
        config.scan_interval_hours = 6
        config.resolution_check_hours = 0.25
        config.max_trades_per_scan = 20
        config.max_trades_per_day = 50
        config.max_trades_per_city = 3
        config.bankroll = 1000.0
        config.max_daily_exposure_pct = 5.0
        return config

    def test_full_resolution_flow(self, mock_config):
        """Test the complete resolution checking flow."""
        with patch("bot.application.bot_runner.get_config") as mock_get_config, \
             patch("bot.application.bot_runner.setup_logger") as mock_logger, \
             patch("bot.application.bot_runner.TradeHistoryDB") as mock_db_class, \
             patch("bot.application.bot_runner.WeatherConnector") as mock_weather, \
             patch("bot.application.bot_runner.PolymarketClient") as mock_poly_client, \
             patch("bot.application.bot_runner.ExtremeValueStrategy") as mock_strategy:

            mock_get_config.return_value = mock_config
            mock_logger.return_value = MagicMock()

            # Setup mock database
            mock_db = MagicMock()
            mock_db_class.return_value = mock_db

            # Open trades to check
            open_trades = [
                {
                    "trade_id": "trade-win",
                    "market_id": "market-resolved-yes",
                    "token_id": "yes_token_123",
                    "price": 0.10,
                    "size": 1.0,
                    "cost": 1.0,
                },
                {
                    "trade_id": "trade-loss",
                    "market_id": "market-resolved-no",
                    "token_id": "yes_token_456",  # Bought YES but NO won
                    "price": 0.20,
                    "size": 2.0,
                    "cost": 2.0,
                },
                {
                    "trade_id": "trade-open",
                    "market_id": "market-still-open",
                    "token_id": "yes_token_789",
                    "price": 0.50,
                    "size": 1.0,
                    "cost": 1.0,
                },
            ]
            mock_db.get_open_trades.return_value = open_trades

            # Setup Polymarket client mock
            mock_client = MagicMock()
            mock_poly_client.return_value = mock_client

            def get_market_side_effect(market_id):
                if market_id == "market-resolved-yes":
                    return {
                        "id": market_id,
                        "conditionId": "0xyes",
                        "closed": True,
                        "resolved": True,
                        "outcomes": ["Yes", "No"],
                        "outcomePrices": ["1", "0"],
                    }
                elif market_id == "market-resolved-no":
                    return {
                        "id": market_id,
                        "conditionId": "0xno",
                        "closed": True,
                        "resolved": True,
                        "outcomes": ["Yes", "No"],
                        "outcomePrices": ["0", "1"],
                    }
                else:
                    return {
                        "id": market_id,
                        "conditionId": "0xopen",
                        "closed": False,
                        "resolved": False,
                        "outcomes": ["Yes", "No"],
                        "outcomePrices": ["0.50", "0.50"],
                    }

            mock_client.get_market.side_effect = get_market_side_effect

            # Create bot runner
            from bot.application.bot_runner import BotRunner
            runner = BotRunner(platform="polymarket", simulation=True)

            # Run resolution check
            runner._check_resolutions()

            # Verify update_resolution was called correctly
            calls = mock_db.update_resolution.call_args_list

            # Should have 2 calls (2 resolved markets)
            assert len(calls) == 2

            # First call: trade-win should have won
            call1_kwargs = calls[0][1]
            assert call1_kwargs["trade_id"] == "trade-win"
            assert call1_kwargs["won"] is True
            assert call1_kwargs["pnl"] == 9.0  # 10 shares * $1 - $1 cost

            # Second call: trade-loss should have lost
            call2_kwargs = calls[1][1]
            assert call2_kwargs["trade_id"] == "trade-loss"
            assert call2_kwargs["won"] is False
            assert call2_kwargs["pnl"] == -2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
