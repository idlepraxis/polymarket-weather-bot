"""Tests for weather API endpoint."""

import pytest
from datetime import datetime, timedelta, timezone

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

    def test_timezone_aware_datetime(self, weather_connector):
        """Test that timezone-aware datetimes work correctly.

        This test verifies the fix for:
        TypeError: can't subtract offset-naive and offset-aware datetimes
        """
        # Create a timezone-aware datetime (UTC)
        target_date_utc = datetime.now(timezone.utc) + timedelta(days=1)

        forecast = weather_connector._get_openweather_forecast("Miami", target_date_utc)

        assert forecast is not None, "Should handle timezone-aware datetime"
        assert forecast.location == "Miami"

        print(f"\nForecast for Miami (using UTC datetime) on {target_date_utc.date()}:")
        print(f"  High: {forecast.temp_high_f:.1f}°F")

    def test_timezone_aware_with_offset(self, weather_connector):
        """Test with a non-UTC timezone offset."""
        # Create datetime with EST offset (-5 hours)
        est = timezone(timedelta(hours=-5))
        target_date_est = datetime.now(est) + timedelta(days=1)

        forecast = weather_connector._get_openweather_forecast("Boston", target_date_est)

        assert forecast is not None, "Should handle datetime with timezone offset"
        assert forecast.location == "Boston"

        print(f"\nForecast for Boston (using EST datetime) on {target_date_est.date()}:")
        print(f"  High: {forecast.temp_high_f:.1f}°F")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])