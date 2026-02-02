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
        """Get weather forecast with optional ensemble from multiple sources.

        v2.5.0: Added prefer_nws_only mode - uses NWS exclusively when available
        since Kalshi uses NWS station data for market resolution.
        """
        # Check cache first
        cache_key = f"{location}_{date.date()}"
        if cache_key in self.cache:
            cached_time, forecast = self.cache[cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < self.cache_ttl:
                return forecast

        forecast = None

        # v2.5.0: Prefer NWS-only mode (Kalshi uses NWS for resolution)
        prefer_nws = getattr(self.config, "prefer_nws_only", True)
        if prefer_nws:
            forecast = self._get_noaa_forecast(location, date)
            if forecast:
                # Got NWS data, use it exclusively
                self.cache[cache_key] = (datetime.utcnow(), forecast)
                return forecast
            # NWS failed, fall through to ensemble/fallback

        if use_ensemble and self.config.enable_ensemble_models:
            forecast = self._get_ensemble_forecast(location, date)
        else:
            # Try NWS first even in non-ensemble mode
            forecast = self._get_noaa_forecast(location, date)
            if not forecast:
                forecast = self._get_openweather_forecast(location, date)

        # Cache the result
        if forecast:
            self.cache[cache_key] = (datetime.utcnow(), forecast)

        return forecast

    def _get_ensemble_forecast(self, location: str, date: datetime) -> Optional[WeatherForecast]:
        """Get ensemble forecast by averaging multiple sources.

        Priority order:
        1. NWS (National Weather Service) - likely Kalshi's resolution source
        2. WeatherAPI - commercial, high quality
        3. OpenWeather - fallback

        For US locations, NWS is weighted more heavily as it's the official source.
        """
        forecasts = []

        # Try NWS first (US locations) - this is likely what Kalshi uses
        # NWS is free and doesn't require API key
        nws_forecast = self._get_noaa_forecast(location, date)
        if nws_forecast:
            forecasts.append(nws_forecast)
            # For US locations with NWS data, we can return early with high confidence
            # or continue to get ensemble for comparison

        # Try WeatherAPI if available
        if self.config.weatherapi_key:
            wa_forecast = self._get_weatherapi_forecast(location, date)
            if wa_forecast:
                forecasts.append(wa_forecast)

        # Try OpenWeather as fallback
        if self.config.openweather_api_key:
            ow_forecast = self._get_openweather_forecast(location, date)
            if ow_forecast:
                forecasts.append(ow_forecast)

        if not forecasts:
            return None

        # If we have NWS data, weight it more heavily in ensemble
        # since it's likely Kalshi's resolution source
        if nws_forecast and len(forecasts) > 1:
            return self._weighted_ensemble_average(forecasts, location, date, nws_weight=2.0)

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

    # City coordinates for NWS API (major US cities that Kalshi covers)
    CITY_COORDINATES = {
        "new york": (40.7128, -74.0060),
        "nyc": (40.7128, -74.0060),
        "los angeles": (34.0522, -118.2437),
        "la": (34.0522, -118.2437),
        "chicago": (41.8781, -87.6298),
        "miami": (25.7617, -80.1918),
        "denver": (39.7392, -104.9903),
        "seattle": (47.6062, -122.3321),
        "san francisco": (37.7749, -122.4194),
        "sf": (37.7749, -122.4194),
        "phoenix": (33.4484, -112.0740),
        "atlanta": (33.7490, -84.3880),
        "boston": (42.3601, -71.0589),
        "dallas": (32.7767, -96.7970),
        "houston": (29.7604, -95.3698),
        "philadelphia": (39.9526, -75.1652),
    }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get_noaa_forecast(self, location: str, date: datetime) -> Optional[WeatherForecast]:
        """Get forecast from NWS (National Weather Service) API.

        This is the official US government weather source, likely used by Kalshi
        for market resolution. No API key required.

        API docs: https://www.weather.gov/documentation/services-web-api
        """
        try:
            # Get coordinates for the location
            location_lower = location.lower()
            coords = self.CITY_COORDINATES.get(location_lower)

            if not coords:
                # Try partial match
                for city, coord in self.CITY_COORDINATES.items():
                    if city in location_lower or location_lower in city:
                        coords = coord
                        break

            if not coords:
                print(f"NWS: No coordinates for location: {location}")
                return None

            lat, lon = coords

            # Step 1: Get the grid point for this location
            points_url = f"https://api.weather.gov/points/{lat},{lon}"
            headers = {
                "User-Agent": "(polymarket-weather-bot, contact@example.com)",
                "Accept": "application/geo+json"
            }

            points_response = httpx.get(points_url, headers=headers, timeout=10.0)
            if points_response.status_code != 200:
                print(f"NWS points failed: {points_response.status_code}")
                return None

            points_data = points_response.json()
            forecast_url = points_data["properties"]["forecast"]

            # Step 2: Get the forecast
            forecast_response = httpx.get(forecast_url, headers=headers, timeout=10.0)
            if forecast_response.status_code != 200:
                print(f"NWS forecast failed: {forecast_response.status_code}")
                return None

            forecast_data = forecast_response.json()

            # Step 3: Find the forecast period for the target date
            target_date_str = date.strftime("%Y-%m-%d")
            periods = forecast_data["properties"]["periods"]

            # NWS returns periods like "Today", "Tonight", "Monday", etc.
            # We need to find the daytime period for our target date
            day_high = None
            night_low = None
            conditions = None

            for period in periods:
                # Parse the start time to get the date
                start_time = period.get("startTime", "")
                if target_date_str in start_time:
                    temp = period.get("temperature")
                    if period.get("isDaytime", True):
                        day_high = temp
                        conditions = period.get("shortForecast", "")
                    else:
                        night_low = temp

                    # If we have both, we're done
                    if day_high is not None and night_low is not None:
                        break

            if day_high is None:
                print(f"NWS: No forecast found for {target_date_str}")
                return None

            # NWS returns temperatures in Fahrenheit
            temp_high_f = float(day_high)
            temp_low_f = float(night_low) if night_low else temp_high_f - 15

            return WeatherForecast(
                location=location,
                date=date,
                temp_high_f=temp_high_f,
                temp_low_f=temp_low_f,
                temp_high_c=(temp_high_f - 32) * 5 / 9,
                temp_low_c=(temp_low_f - 32) * 5 / 9,
                prob_precipitation=None,  # NWS uses probability phrases, not percentages
                conditions=conditions,
                source="NWS",
                confidence=0.90,  # Higher confidence - official source
            )

        except Exception as e:
            print(f"Error fetching NWS forecast: {e}")
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

    def _weighted_ensemble_average(
        self, forecasts: List[WeatherForecast], location: str, date: datetime,
        nws_weight: float = 2.0
    ) -> WeatherForecast:
        """Weighted average with NWS data weighted more heavily.

        NWS is the official US government source and likely what Kalshi uses
        for market resolution, so we weight it more heavily.
        """
        if len(forecasts) == 1:
            return forecasts[0]

        # Build weights (NWS gets higher weight)
        weights = []
        for f in forecasts:
            if f.source == "NWS":
                weights.append(nws_weight)
            else:
                weights.append(1.0)

        total_weight = sum(weights)

        # Weighted average temperature predictions
        high_temps = [(f.temp_high_f, w) for f, w in zip(forecasts, weights) if f.temp_high_f]
        low_temps = [(f.temp_low_f, w) for f, w in zip(forecasts, weights) if f.temp_low_f]

        avg_temp_high_f = sum(t * w for t, w in high_temps) / sum(w for _, w in high_temps)
        avg_temp_low_f = sum(t * w for t, w in low_temps) / sum(w for _, w in low_temps)

        avg_temp_high_c = (avg_temp_high_f - 32) * 5 / 9
        avg_temp_low_c = (avg_temp_low_f - 32) * 5 / 9

        # Average precipitation probability (unweighted, many sources don't have it)
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
            conditions=forecasts[0].conditions,  # Take from first source (NWS)
            source=f"WeightedEnsemble({len(forecasts)},NWS={nws_weight}x)",
            confidence=min(max_confidence + 0.1, 1.0),
        )

    def calculate_probability(
        self, forecast: WeatherForecast, threshold: float, threshold_type: str = "high_temp_f",
        direction: str = "above"
    ) -> float:
        """Calculate probability that threshold will be exceeded or not met.

        Args:
            forecast: Weather forecast data
            threshold: Threshold value (e.g., 70 for 70°F)
            threshold_type: Type of threshold (high_temp_f, low_temp_f, precipitation, etc.)
            direction: "above" for P(temp > threshold), "below" for P(temp < threshold)

        Returns:
            Probability between 0.0 and 1.0
        """
        from math import erf, sqrt

        # Weather forecast uncertainty - see calculate_range_probability() for detailed docs
        # v2.5.0: Increased from 4.0 to 7.0 based on actual trading results
        # Analysis showed forecast errors of 6-10°F in many cases, causing overconfident
        # probability estimates (97% fair prob trades were losing)
        std_dev = 7.0

        if threshold_type == "high_temp_f":
            predicted = forecast.temp_high_f
            if predicted is None:
                return 0.5

            # Calculate P(temp > threshold) using normal CDF
            # If predicted is 4°F above threshold, ~84% chance
            # If predicted equals threshold, ~50% chance
            # If predicted is 4°F below threshold, ~16% chance
            diff = predicted - threshold
            z_score = diff / (std_dev * sqrt(2))
            probability = 0.5 * (1 + erf(z_score))  # P(temp > threshold)

            # If direction is "below", we want P(temp < threshold)
            if direction == "below":
                probability = 1 - probability

            return max(0.01, min(0.99, probability))

        elif threshold_type == "low_temp_f":
            predicted = forecast.temp_low_f
            if predicted is None:
                return 0.5

            diff = predicted - threshold
            z_score = diff / (std_dev * sqrt(2))
            probability = 0.5 * (1 + erf(z_score))  # P(temp > threshold)

            # If direction is "below", we want P(temp < threshold)
            if direction == "below":
                probability = 1 - probability

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
        #
        # v2.5.0: Increased from 4.0 to 7.0 based on actual trading results
        # Analysis showed forecast errors of 6-10°F, causing overconfident probabilities.
        # With 4.0°F, a forecast 4°F away gave 84% confidence, but actual accuracy was ~15%.
        #
        # Original rationale (kept for reference):
        # - NWS studies show 1-day forecasts have RMSE of 2-3°F, 3-day of 4-5°F
        # - But real-world trading showed much larger effective errors
        # - Possible causes: data source mismatch, measurement period differences
        #
        # CALIBRATION: If win rate exceeds predictions, reduce std_dev; if lower, increase it.
        std_dev = 7.0

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
        # Patterns: "48-49°", "56° to 57°", "48 to 49°", "-1-0°" (negative temps)
        range_patterns = [
            r"(-?\d+)-(-?\d+)°",  # 48-49° or -1-0° (supports negative temps)
            r"(-?\d+)°?\s*to\s*(-?\d+)°",  # 56° to 57° or -5° to -3°
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
                (r">\s*(-?\d+)°?", "above"),  # >13° or >-5°
                (r"<\s*(-?\d+)°?", "below"),  # <13° or <-1°
                (r"above\s+(-?\d+)", "above"),  # above 70 or above -10
                (r"below\s+(-?\d+)", "below"),  # below 70 or below -5
                (r"exceed\s+(-?\d+)", "above"),  # exceed 70
                (r"(-?\d+)\s*°?[fF]", None),  # 70F or -5°F (generic)
                (r"(-?\d+)\s*degrees?\s*[fF]", None),  # 70 degrees F
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
