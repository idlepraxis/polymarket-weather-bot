"""Tests for weather API endpoint."""

import pytest
from datetime import datetime, timedelta

from bot.connectors.weather import WeatherConnector
from bot.utils.config import Config


@pytest.fixture
def config():
    """Load configuration from environment."""
    return Config()


@pytest.fixture
def weather_connector(config):
    """Create WeatherConnector instance."""
    return WeatherConnector(config)


class TestOpenWeatherAPI:
    """Integration tests for OpenWeather API."""

    def test_get_openweather_forecast_nyc(self, weather_connector):
        """Test fetching forecast for New York City."""
        target_date = datetime.now() + timedelta(days=1)

        forecast = weather_connector._get_openweather_forecast("New York", target_date)

        assert forecast is not None, "Forecast should not be None"
        assert forecast.location == "New York"
        assert forecast.source == "OpenWeather"
        assert forecast.temp_high_f is not None
        assert forecast.temp_low_f is not None
        assert forecast.temp_high_c is not None
        assert forecast.temp_low_c is not None
        assert 0 <= forecast.confidence <= 1

        print(f"\nForecast for New York on {target_date.date()}:")
        print(f"  High: {forecast.temp_high_f:.1f}°F ({forecast.temp_high_c:.1f}°C)")
        print(f"  Low: {forecast.temp_low_f:.1f}°F ({forecast.temp_low_c:.1f}°C)")
        print(f"  Conditions: {forecast.conditions}")
        print(f"  Precipitation: {forecast.prob_precipitation:.0%}")

    def test_get_openweather_forecast_london(self, weather_connector):
        """Test fetching forecast for London."""
        target_date = datetime.now() + timedelta(days=2)

        forecast = weather_connector._get_openweather_forecast("London", target_date)

        assert forecast is not None, "Forecast should not be None"
        assert forecast.location == "London"
        assert forecast.source == "OpenWeather"

        print(f"\nForecast for London on {target_date.date()}:")
        print(f"  High: {forecast.temp_high_f:.1f}°F ({forecast.temp_high_c:.1f}°C)")
        print(f"  Conditions: {forecast.conditions}")

    def test_get_openweather_forecast_invalid_location(self, weather_connector):
        """Test that invalid location returns None."""
        target_date = datetime.now() + timedelta(days=1)

        forecast = weather_connector._get_openweather_forecast("InvalidCityXYZ123", target_date)

        assert forecast is None, "Invalid location should return None"

    def test_temperature_conversion_sanity(self, weather_connector):
        """Test that temperature conversions are reasonable."""
        target_date = datetime.now() + timedelta(days=1)

        forecast = weather_connector._get_openweather_forecast("Chicago", target_date)

        assert forecast is not None

        # Verify F to C conversion is roughly correct
        # C = (F - 32) * 5/9
        expected_high_c = (forecast.temp_high_f - 32) * 5 / 9
        assert abs(forecast.temp_high_c - expected_high_c) < 1, "Temperature conversion mismatch"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])