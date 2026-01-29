"""Weather data connector for multiple APIs."""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.utils.config import Config
from bot.utils.models import WeatherForecast


class WeatherConnector:
    """Unified weather data connector supporting multiple APIs."""

    def __init__(self, config: Config):
        self.config = config
        self.cache: Dict[str, tuple[datetime, WeatherForecast]] = {}
        self.cache_ttl = 900  # 15 minutes

    def get_forecast(
        self, location: str, date: datetime, use_ensemble: bool = True
    ) -> Optional[WeatherForecast]:
        """Get weather forecast with optional ensemble from multiple sources."""
        # Check cache first
        cache_key = f"{location}_{date.date()}"
        if cache_key in self.cache:
            cached_time, forecast = self.cache[cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < self.cache_ttl:
                return forecast

        if use_ensemble and self.config.enable_ensemble_models:
            forecast = self._get_ensemble_forecast(location, date)
        else:
            forecast = self._get_openweather_forecast(location, date)

        # Cache the result
        if forecast:
            self.cache[cache_key] = (datetime.utcnow(), forecast)

        return forecast

    def _get_ensemble_forecast(self, location: str, date: datetime) -> Optional[WeatherForecast]:
        """Get ensemble forecast by averaging multiple sources."""
        forecasts = []

        # Try OpenWeather
        ow_forecast = self._get_openweather_forecast(location, date)
        if ow_forecast:
            forecasts.append(ow_forecast)

        # Try WeatherAPI if available
        if self.config.weatherapi_key:
            wa_forecast = self._get_weatherapi_forecast(location, date)
            if wa_forecast:
                forecasts.append(wa_forecast)

        # Try NOAA if available (US locations only)
        if self.config.noaa_api_key:
            noaa_forecast = self._get_noaa_forecast(location, date)
            if noaa_forecast:
                forecasts.append(noaa_forecast)

        if not forecasts:
            return None

        # Average the forecasts
        return self._ensemble_average(forecasts, location, date)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get_openweather_forecast(self, location: str, date: datetime) -> Optional[WeatherForecast]:
        """Get forecast from OpenWeatherMap API."""
        try:
            # First, get coordinates for location
            geo_url = "http://api.openweathermap.org/geo/1.0/direct"
            geo_params = {"q": location, "limit": 1, "appid": self.config.openweather_api_key}

            geo_response = httpx.get(geo_url, params=geo_params, timeout=10.0)
            if geo_response.status_code != 200:
                print(f"OpenWeather geocoding failed: {geo_response.status_code}")
                return None

            geo_data = geo_response.json()
            if not geo_data:
                print(f"Location not found: {location}")
                return None

            lat = geo_data[0]["lat"]
            lon = geo_data[0]["lon"]

            # Get forecast
            forecast_url = "http://api.openweathermap.org/data/2.5/forecast"
            forecast_params = {
                "lat": lat,
                "lon": lon,
                "appid": self.config.openweather_api_key,
                "units": "metric",
            }

            forecast_response = httpx.get(forecast_url, params=forecast_params, timeout=10.0)
            if forecast_response.status_code != 200:
                print(f"OpenWeather forecast failed: {forecast_response.status_code}")
                return None

            forecast_data = forecast_response.json()

            # Find forecast closest to target date
            target_forecast = self._find_closest_forecast(forecast_data["list"], date)
            if not target_forecast:
                return None

            # Parse forecast
            temp_c = target_forecast["main"]["temp"]
            temp_f = (temp_c * 9 / 5) + 32

            return WeatherForecast(
                location=location,
                date=date,
                temp_high_f=temp_f,
                temp_low_f=temp_f - 5,  # Rough estimate
                temp_high_c=temp_c,
                temp_low_c=temp_c - 3,
                prob_precipitation=target_forecast.get("pop", 0.0),
                conditions=target_forecast["weather"][0]["description"],
                humidity=target_forecast["main"]["humidity"],
                wind_speed=target_forecast["wind"]["speed"] * 2.237,  # m/s to mph
                source="OpenWeather",
                confidence=0.8,
            )

        except Exception as e:
            print(f"Error fetching OpenWeather forecast: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get_weatherapi_forecast(self, location: str, date: datetime) -> Optional[WeatherForecast]:
        """Get forecast from WeatherAPI.com."""
        try:
            url = "http://api.weatherapi.com/v1/forecast.json"
            params = {
                "key": self.config.weatherapi_key,
                "q": location,
                "days": 10,
            }

            response = httpx.get(url, params=params, timeout=10.0)
            if response.status_code != 200:
                print(f"WeatherAPI failed: {response.status_code}")
                return None

            data = response.json()

            # Find the forecast for target date
            target_date_str = date.strftime("%Y-%m-%d")
            forecast_day = None

            for day in data["forecast"]["forecastday"]:
                if day["date"] == target_date_str:
                    forecast_day = day
                    break

            if not forecast_day:
                return None

            day_data = forecast_day["day"]

            return WeatherForecast(
                location=location,
                date=date,
                temp_high_f=day_data["maxtemp_f"],
                temp_low_f=day_data["mintemp_f"],
                temp_high_c=day_data["maxtemp_c"],
                temp_low_c=day_data["mintemp_c"],
                prob_precipitation=day_data.get("daily_chance_of_rain", 0) / 100.0,
                prob_snow=day_data.get("daily_chance_of_snow", 0) / 100.0,
                conditions=day_data["condition"]["text"],
                humidity=day_data["avghumidity"],
                wind_speed=day_data["maxwind_mph"],
                source="WeatherAPI",
                confidence=0.85,
            )

        except Exception as e:
            print(f"Error fetching WeatherAPI forecast: {e}")
            return None

    def _get_noaa_forecast(self, location: str, date: datetime) -> Optional[WeatherForecast]:
        """Get forecast from NOAA (US only)."""
        # NOAA API is more complex and requires specific grid points
        # This is a simplified placeholder
        # TODO: Implement full NOAA integration for US locations
        return None

    def _find_closest_forecast(
        self, forecast_list: List[Dict], target_date: datetime
    ) -> Optional[Dict]:
        """Find forecast entry closest to target date."""
        closest = None
        min_diff = float("inf")

        for item in forecast_list:
            forecast_time = datetime.fromtimestamp(item["dt"])
            diff = abs((forecast_time - target_date).total_seconds())

            if diff < min_diff:
                min_diff = diff
                closest = item

        return closest

    def _ensemble_average(
        self, forecasts: List[WeatherForecast], location: str, date: datetime
    ) -> WeatherForecast:
        """Average multiple forecasts into ensemble."""
        if len(forecasts) == 1:
            return forecasts[0]

        # Average temperature predictions
        avg_temp_high_f = sum(f.temp_high_f for f in forecasts if f.temp_high_f) / len(
            [f for f in forecasts if f.temp_high_f]
        )
        avg_temp_low_f = sum(f.temp_low_f for f in forecasts if f.temp_low_f) / len(
            [f for f in forecasts if f.temp_low_f]
        )

        avg_temp_high_c = (avg_temp_high_f - 32) * 5 / 9
        avg_temp_low_c = (avg_temp_low_f - 32) * 5 / 9

        # Average precipitation probability
        precip_forecasts = [f.prob_precipitation for f in forecasts if f.prob_precipitation]
        avg_precip = sum(precip_forecasts) / len(precip_forecasts) if precip_forecasts else None

        # Use highest confidence
        max_confidence = max(f.confidence for f in forecasts)

        return WeatherForecast(
            location=location,
            date=date,
            temp_high_f=avg_temp_high_f,
            temp_low_f=avg_temp_low_f,
            temp_high_c=avg_temp_high_c,
            temp_low_c=avg_temp_low_c,
            prob_precipitation=avg_precip,
            conditions=forecasts[0].conditions,  # Take from first source
            source=f"Ensemble({len(forecasts)})",
            confidence=min(max_confidence + 0.1, 1.0),  # Ensemble bonus
        )

    def calculate_probability(
        self, forecast: WeatherForecast, threshold: float, threshold_type: str = "high_temp_f"
    ) -> float:
        """Calculate probability that threshold will be exceeded/met.

        Args:
            forecast: Weather forecast data
            threshold: Threshold value (e.g., 70 for 70°F)
            threshold_type: Type of threshold (high_temp_f, low_temp_f, precipitation, etc.)

        Returns:
            Probability between 0.0 and 1.0
        """
        if threshold_type == "high_temp_f":
            predicted = forecast.temp_high_f
            if predicted is None:
                return 0.5

            # Simple probabilistic model with uncertainty
            # Assume ±5°F standard deviation
            diff = predicted - threshold
            std_dev = 5.0

            # Convert to probability using normal distribution approximation
            # If predicted is 5°F above threshold, ~84% chance
            # If predicted equals threshold, ~50% chance
            # If predicted is 5°F below threshold, ~16% chance
            from math import erf, sqrt

            z_score = diff / (std_dev * sqrt(2))
            probability = 0.5 * (1 + erf(z_score))

            return max(0.01, min(0.99, probability))

        elif threshold_type == "low_temp_f":
            predicted = forecast.temp_low_f
            if predicted is None:
                return 0.5

            diff = predicted - threshold
            std_dev = 5.0
            from math import erf, sqrt

            z_score = diff / (std_dev * sqrt(2))
            probability = 0.5 * (1 + erf(z_score))

            return max(0.01, min(0.99, probability))

        elif threshold_type == "precipitation":
            return forecast.prob_precipitation if forecast.prob_precipitation else 0.5

        else:
            return 0.5  # Unknown threshold type

    def calculate_range_probability(
        self, forecast: WeatherForecast, range_low: float, range_high: float,
        threshold_type: str = "high_temp_f"
    ) -> float:
        """Calculate probability that temperature falls within a range.

        For Kalshi markets like "Will temp be 48-49°?"

        Args:
            forecast: Weather forecast data
            range_low: Lower bound of range (e.g., 48)
            range_high: Upper bound of range (e.g., 49)
            threshold_type: Type of threshold (high_temp_f, low_temp_f)

        Returns:
            Probability between 0.0 and 1.0
        """
        from math import erf, sqrt

        if threshold_type == "high_temp_f":
            predicted = forecast.temp_high_f
        elif threshold_type == "low_temp_f":
            predicted = forecast.temp_low_f
        else:
            return 0.1  # Default low probability for unknown types

        if predicted is None:
            return 0.1

        # Weather forecast uncertainty (standard deviation)
        # Typically 2-4°F for 1-day forecasts, 4-6°F for 3+ day forecasts
        std_dev = 4.0

        # Calculate P(range_low <= temp < range_high) using normal CDF
        # P(a < X < b) = Phi((b - mu) / sigma) - Phi((a - mu) / sigma)
        z_low = (range_low - predicted) / (std_dev * sqrt(2))
        z_high = (range_high - predicted) / (std_dev * sqrt(2))

        prob_below_high = 0.5 * (1 + erf(z_high))
        prob_below_low = 0.5 * (1 + erf(z_low))

        probability = prob_below_high - prob_below_low

        # Clamp to reasonable bounds
        return max(0.01, min(0.99, probability))

    def parse_market_question(self, question: str) -> Dict[str, any]:
        """Parse market question to extract location, threshold, and type.

        Supports Kalshi formats:
        - Ranges: "48-49°", "56° to 57°"
        - Thresholds: ">13°", "<13°", "above 70", "below 70"
        - Dates: "Jan 27, 2026", "MM/DD/YYYY", "YYYY-MM-DD"

        Returns:
            Dict with keys: location, threshold, threshold_type, date,
                           range_low, range_high, is_range
        """
        import re
        from datetime import datetime

        result = {
            "location": None,
            "threshold": None,
            "threshold_type": None,
            "date": None,
            "range_low": None,
            "range_high": None,
            "is_range": False,
        }

        # Extract location (common cities)
        cities = [
            "New York",
            "NYC",
            "Los Angeles",
            "LA",
            "Chicago",
            "London",
            "Paris",
            "Tokyo",
            "Denver",
            "Miami",
            "Boston",
            "Seattle",
            "San Francisco",
            "SF",
            "Phoenix",
            "Atlanta",
        ]

        question_lower = question.lower()
        for city in cities:
            if city.lower() in question_lower:
                result["location"] = city
                break

        # Determine if it's about high or low temp FIRST
        if "low" in question_lower or "minimum" in question_lower:
            result["threshold_type"] = "low_temp_f"
        elif "high" in question_lower or "maximum" in question_lower:
            result["threshold_type"] = "high_temp_f"
        else:
            result["threshold_type"] = "high_temp_f"  # default

        # Extract temperature - check for RANGE first (Kalshi format)
        # Patterns: "48-49°", "56° to 57°", "48 to 49°"
        range_patterns = [
            r"(\d+)-(\d+)°",  # 48-49°
            r"(\d+)°?\s*to\s*(\d+)°",  # 56° to 57° or 56 to 57°
        ]

        for pattern in range_patterns:
            match = re.search(pattern, question)
            if match:
                result["range_low"] = float(match.group(1))
                result["range_high"] = float(match.group(2))
                result["threshold"] = (result["range_low"] + result["range_high"]) / 2
                result["is_range"] = True
                break

        # If no range found, check for threshold (>, <, above, below)
        if not result["is_range"]:
            threshold_patterns = [
                (r">\s*(\d+)°?", "above"),  # >13°
                (r"<\s*(\d+)°?", "below"),  # <13°
                (r"above\s+(\d+)", "above"),  # above 70
                (r"below\s+(\d+)", "below"),  # below 70
                (r"exceed\s+(\d+)", "above"),  # exceed 70
                (r"(\d+)\s*°?[fF]", None),  # 70F or 70°F (generic)
                (r"(\d+)\s*degrees?\s*[fF]", None),  # 70 degrees F
            ]

            for pattern, direction in threshold_patterns:
                match = re.search(pattern, question)
                if match:
                    result["threshold"] = float(match.group(1))
                    if direction:
                        result["threshold_direction"] = direction
                    break

        # Extract date - support "Jan 27, 2026" format (Kalshi)
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

        # Try "Jan 27, 2026" format first
        month_date_match = re.search(
            r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2}),?\s*(\d{4})",
            question_lower
        )
        if month_date_match:
            try:
                month = month_map[month_date_match.group(1)]
                day = int(month_date_match.group(2))
                year = int(month_date_match.group(3))
                result["date"] = datetime(year, month, day)
            except:
                pass

        # Fallback to other date patterns
        if not result["date"]:
            date_patterns = [
                r"(\d{1,2})/(\d{1,2})/(\d{4})",  # MM/DD/YYYY
                r"(\d{4})-(\d{2})-(\d{2})",  # YYYY-MM-DD
            ]

            for pattern in date_patterns:
                match = re.search(pattern, question)
                if match:
                    try:
                        if "/" in pattern:
                            month, day, year = match.groups()
                            result["date"] = datetime(int(year), int(month), int(day))
                        else:
                            year, month, day = match.groups()
                            result["date"] = datetime(int(year), int(month), int(day))
                    except:
                        pass
                    break

        return result
