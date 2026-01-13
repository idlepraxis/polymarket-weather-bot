"""Basic tests for bot functionality."""

import pytest
from datetime import datetime

from bot.utils.models import WeatherMarket, WeatherForecast, MarketStatus


def test_weather_market_creation():
    """Test WeatherMarket model creation."""
    market = WeatherMarket(
        market_id="test_123",
        condition_id="cond_456",
        question="Will NYC temperature exceed 70°F on 2026-01-15?",
        yes_token_id="token_yes",
        no_token_id="token_no",
        yes_price=0.45,
        no_price=0.55,
        status=MarketStatus.ACTIVE,
        end_date=datetime(2026, 1, 15),
    )

    assert market.market_id == "test_123"
    assert market.yes_price == 0.45
    assert market.status == MarketStatus.ACTIVE


def test_weather_forecast_creation():
    """Test WeatherForecast model creation."""
    forecast = WeatherForecast(
        location="New York",
        date=datetime(2026, 1, 15),
        temp_high_f=72.5,
        temp_low_f=65.0,
        temp_high_c=22.5,
        temp_low_c=18.3,
        prob_precipitation=0.3,
        source="OpenWeather",
        confidence=0.85,
    )

    assert forecast.location == "New York"
    assert forecast.temp_high_f == 72.5
    assert forecast.confidence == 0.85


def test_probability_bounds():
    """Test that probabilities are bounded between 0 and 1."""
    market = WeatherMarket(
        market_id="test",
        condition_id="cond",
        question="Test",
        yes_token_id="yes",
        no_token_id="no",
        yes_price=0.5,
        no_price=0.5,
        status=MarketStatus.ACTIVE,
        end_date=datetime.now(),
    )

    # Prices should be between 0 and 1
    assert 0 <= market.yes_price <= 1
    assert 0 <= market.no_price <= 1


def test_edge_calculation():
    """Test edge calculation logic."""
    fair_prob = 0.65
    market_price = 0.50
    edge = fair_prob - market_price

    assert edge == 0.15
    assert edge > 0  # Positive edge = opportunity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
