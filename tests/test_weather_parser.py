"""Tests for weather parser and probability calculations.

Tests cover:
- parse_market_question() with Kalshi formats (ranges, thresholds, dates)
- calculate_range_probability() for bucket markets
- calculate_probability() for threshold markets
"""

import pytest
from datetime import datetime
from math import isclose

from bot.connectors.weather import WeatherConnector
from bot.utils.models import WeatherForecast


@pytest.fixture
def weather_connector():
    """Create a WeatherConnector without API keys for testing."""
    class MockConfig:
        openweather_api_key = None
        weatherapi_key = None
        noaa_api_key = None
        enable_ensemble_models = False

    return WeatherConnector(MockConfig())


@pytest.fixture
def sample_forecast():
    """Create a sample forecast for testing probability calculations."""
    return WeatherForecast(
        location="Chicago",
        date=datetime(2026, 1, 29),
        temp_high_f=25.0,
        temp_low_f=10.0,
        temp_high_c=-4.0,
        temp_low_c=-12.0,
        prob_precipitation=0.1,
        source="Test",
        confidence=0.9,
    )


class TestParseMarketQuestion:
    """Tests for parse_market_question() function."""

    def test_parse_kalshi_range_low_temp(self, weather_connector):
        """Test parsing Kalshi-style range market for low temperature."""
        question = "Will the minimum temperature in Chicago be 3-4° on Jan 27, 2026?"
        parsed = weather_connector.parse_market_question(question)

        assert parsed["location"] == "Chicago"
        assert parsed["is_range"] == True
        assert parsed["range_low"] == 3.0
        assert parsed["range_high"] == 4.0
        assert parsed["threshold_type"] == "low_temp_f"
        assert parsed["date"] == datetime(2026, 1, 27)

    def test_parse_kalshi_range_high_temp(self, weather_connector):
        """Test parsing Kalshi-style range market for high temperature."""
        question = "Will the maximum temperature in Seattle be 54-55° on Jan 29, 2026?"
        parsed = weather_connector.parse_market_question(question)

        assert parsed["location"] == "Seattle"
        assert parsed["is_range"] == True
        assert parsed["range_low"] == 54.0
        assert parsed["range_high"] == 55.0
        assert parsed["threshold_type"] == "high_temp_f"
        assert parsed["date"] == datetime(2026, 1, 29)

    def test_parse_kalshi_threshold_above(self, weather_connector):
        """Test parsing Kalshi-style threshold market (above)."""
        question = "Will the minimum temperature in New York be >13° on Jan 28, 2026?"
        parsed = weather_connector.parse_market_question(question)

        assert parsed["location"] == "New York"
        assert parsed["is_range"] == False
        assert parsed["threshold"] == 13.0
        assert parsed["threshold_type"] == "low_temp_f"
        assert parsed["date"] == datetime(2026, 1, 28)

    def test_parse_kalshi_threshold_below(self, weather_connector):
        """Test parsing Kalshi-style threshold market (below)."""
        question = "Will the maximum temperature in Denver be <50° on Feb 1, 2026?"
        parsed = weather_connector.parse_market_question(question)

        assert parsed["location"] == "Denver"
        assert parsed["is_range"] == False
        assert parsed["threshold"] == 50.0
        assert parsed["threshold_type"] == "high_temp_f"

    def test_parse_various_cities(self, weather_connector):
        """Test parsing markets for different cities."""
        cities = [
            ("Los Angeles", "Will the minimum temperature in Los Angeles be 48-49° on Jan 27, 2026?"),
            ("Miami", "Will the minimum temperature in Miami be 49-50° on Jan 27, 2026?"),
            ("San Francisco", "Will the maximum temperature in San Francisco be >65° on Jan 28, 2026?"),
            ("Boston", "Will the minimum temperature in Boston be 20-25° on Jan 30, 2026?"),
        ]

        for expected_city, question in cities:
            parsed = weather_connector.parse_market_question(question)
            assert parsed["location"] == expected_city, f"Failed for: {question}"

    def test_parse_date_formats(self, weather_connector):
        """Test parsing different date formats."""
        # Kalshi format: "Jan 27, 2026"
        parsed = weather_connector.parse_market_question(
            "Will temp in Chicago be 30-35° on Jan 27, 2026?"
        )
        assert parsed["date"] == datetime(2026, 1, 27)

        # Kalshi format without comma: "Jan 27 2026"
        parsed = weather_connector.parse_market_question(
            "Will temp in Chicago be 30-35° on Feb 15 2026?"
        )
        assert parsed["date"] == datetime(2026, 2, 15)

    def test_parse_unknown_location_returns_none(self, weather_connector):
        """Test that unknown locations return None (not crash)."""
        question = "Will the temperature in Toronto be 30-35° on Jan 27, 2026?"
        parsed = weather_connector.parse_market_question(question)

        # Toronto is not in the city list, should return None
        assert parsed["location"] is None
        # But range should still be parsed
        assert parsed["is_range"] == True
        assert parsed["range_low"] == 30.0

    def test_parse_no_threshold_returns_none(self, weather_connector):
        """Test that questions without temperature return None threshold."""
        question = "Will it rain in Chicago on Jan 27, 2026?"
        parsed = weather_connector.parse_market_question(question)

        assert parsed["location"] == "Chicago"
        assert parsed["threshold"] is None
        assert parsed["is_range"] == False

    def test_parse_negative_threshold_below(self, weather_connector):
        """Test parsing negative temperature threshold (below)."""
        question = "Will the minimum temperature in Chicago be <-1° on Jan 30, 2026?"
        parsed = weather_connector.parse_market_question(question)

        assert parsed["location"] == "Chicago"
        assert parsed["is_range"] == False
        assert parsed["threshold"] == -1.0
        assert parsed["threshold_direction"] == "below"
        assert parsed["threshold_type"] == "low_temp_f"

    def test_parse_negative_threshold_above(self, weather_connector):
        """Test parsing negative temperature threshold (above)."""
        question = "Will the minimum temperature in Chicago be >-5° on Jan 30, 2026?"
        parsed = weather_connector.parse_market_question(question)

        assert parsed["location"] == "Chicago"
        assert parsed["is_range"] == False
        assert parsed["threshold"] == -5.0
        assert parsed["threshold_direction"] == "above"

    def test_parse_negative_range(self, weather_connector):
        """Test parsing negative temperature range."""
        question = "Will the minimum temperature in Chicago be -1-0° on Jan 30, 2026?"
        parsed = weather_connector.parse_market_question(question)

        assert parsed["location"] == "Chicago"
        assert parsed["is_range"] == True
        assert parsed["range_low"] == -1.0
        assert parsed["range_high"] == 0.0
        assert parsed["threshold"] == -0.5  # midpoint

    def test_parse_zero_threshold(self, weather_connector):
        """Test parsing zero temperature threshold (edge case for truthiness)."""
        question = "Will the minimum temperature in New York be <0° on Jan 31, 2026?"
        parsed = weather_connector.parse_market_question(question)

        assert parsed["location"] == "New York"
        assert parsed["is_range"] == False
        assert parsed["threshold"] == 0.0  # Must be 0.0, not None
        assert parsed["threshold_direction"] == "below"


class TestCalculateRangeProbability:
    """Tests for calculate_range_probability() function."""

    def test_forecast_at_range_midpoint(self, weather_connector, sample_forecast):
        """When forecast equals range midpoint, probability should be moderate."""
        # Forecast low is 10°F, test range 8-12° (midpoint 10°F)
        prob = weather_connector.calculate_range_probability(
            sample_forecast, 8.0, 12.0, "low_temp_f"
        )

        # With std_dev=4, range of 4° centered on forecast should be ~38%
        assert 0.30 < prob < 0.50, f"Expected ~38%, got {prob:.1%}"

    def test_forecast_outside_range(self, weather_connector, sample_forecast):
        """When forecast is far from range, probability should be low."""
        # Forecast low is 10°F, test range 25-30° (far above)
        prob = weather_connector.calculate_range_probability(
            sample_forecast, 25.0, 30.0, "low_temp_f"
        )

        # Should be very low probability
        assert prob < 0.05, f"Expected <5%, got {prob:.1%}"

    def test_forecast_at_range_edge(self, weather_connector, sample_forecast):
        """When forecast is at range edge, probability should be moderate-low."""
        # Forecast low is 10°F, test range 10-12° (forecast at lower edge)
        prob = weather_connector.calculate_range_probability(
            sample_forecast, 10.0, 12.0, "low_temp_f"
        )

        # Should capture roughly half the distribution above 10
        assert 0.15 < prob < 0.35, f"Expected ~25%, got {prob:.1%}"

    def test_narrow_range_low_probability(self, weather_connector, sample_forecast):
        """Narrow 1° range should have low probability even if centered."""
        # Forecast low is 10°F, test range 9-10° (1° bucket)
        prob = weather_connector.calculate_range_probability(
            sample_forecast, 9.0, 10.0, "low_temp_f"
        )

        # 1° range with std_dev=4 should be ~10%
        assert 0.05 < prob < 0.15, f"Expected ~10%, got {prob:.1%}"

    def test_wide_range_high_probability(self, weather_connector, sample_forecast):
        """Wide range centered on forecast should have high probability."""
        # Forecast low is 10°F, test range 0-20° (20° bucket centered on 10)
        prob = weather_connector.calculate_range_probability(
            sample_forecast, 0.0, 20.0, "low_temp_f"
        )

        # Should capture most of distribution
        assert prob > 0.80, f"Expected >80%, got {prob:.1%}"

    def test_high_temp_uses_correct_forecast_field(self, weather_connector, sample_forecast):
        """Test that high_temp_f uses temp_high_f from forecast."""
        # Forecast high is 25°F, test range 23-27° (centered on high)
        prob = weather_connector.calculate_range_probability(
            sample_forecast, 23.0, 27.0, "high_temp_f"
        )

        # Should be moderate-high probability
        assert 0.30 < prob < 0.50, f"Expected ~38%, got {prob:.1%}"


class TestCalculateProbability:
    """Tests for calculate_probability() threshold function."""

    def test_forecast_above_threshold(self, weather_connector, sample_forecast):
        """When forecast is above threshold, probability should be high."""
        # Forecast high is 25°F, threshold is 20°F
        prob = weather_connector.calculate_probability(
            sample_forecast, 20.0, "high_temp_f"
        )

        # 5° above threshold with std_dev=5 should be ~84%
        assert prob > 0.75, f"Expected >75%, got {prob:.1%}"

    def test_forecast_below_threshold(self, weather_connector, sample_forecast):
        """When forecast is below threshold, probability should be low."""
        # Forecast high is 25°F, threshold is 35°F
        prob = weather_connector.calculate_probability(
            sample_forecast, 35.0, "high_temp_f"
        )

        # 10° below threshold should be very low
        assert prob < 0.10, f"Expected <10%, got {prob:.1%}"

    def test_forecast_at_threshold(self, weather_connector, sample_forecast):
        """When forecast equals threshold, probability should be ~50%."""
        # Forecast high is 25°F, threshold is 25°F
        prob = weather_connector.calculate_probability(
            sample_forecast, 25.0, "high_temp_f"
        )

        # At threshold should be ~50%
        assert 0.45 < prob < 0.55, f"Expected ~50%, got {prob:.1%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
