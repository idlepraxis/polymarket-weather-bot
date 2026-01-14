"""Kalshi connector for weather prediction markets."""

import base64
import hashlib
import hmac
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from bot.utils.config import Config
from bot.utils.logger import get_logger
from bot.utils.models import WeatherMarket, MarketStatus


class KalshiClient:
    """Client for interacting with Kalshi prediction markets."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger()

        # API endpoints
        if config.kalshi_use_demo:
            self.api_base = "https://demo-api.kalshi.co/trade-api/v2"
        else:
            self.api_base = "https://trading-api.kalshi.com/trade-api/v2"

        # Authentication credentials
        self.api_key_id = config.kalshi_api_key_id
        self.api_private_key_pem = config.kalshi_api_private_key
        self.email = config.kalshi_email
        self.password = config.kalshi_password

        self.token = None
        self.token_expiry = None
        self.auth_method = None
        self.private_key = None  # Loaded RSA private key object

        # HTTP client with persistent session
        self.client = httpx.Client(timeout=30.0)

        # Authenticate
        self._authenticate()

        print(f"Connected to Kalshi ({self.api_base})")
        if self.auth_method == "api_key":
            print(f"Authentication: API Key (ID: {self.api_key_id[:10]}...)")
        else:
            print(f"Authentication: Email/Password ({self.email})")

    def _authenticate(self):
        """Authenticate with Kalshi API using API key or email/password."""
        # Prefer API key authentication if available
        if self.api_key_id and self.api_private_key:
            try:
                self._authenticate_with_api_key()
                self.auth_method = "api_key"
                return
            except Exception as e:
                self.logger.warning(f"API key authentication failed: {e}")
                # Fall through to email/password if available

        # Fall back to email/password authentication
        if self.email and self.password:
            self._authenticate_with_password()
            self.auth_method = "password"
            return

        raise ConnectionError(
            "No valid Kalshi credentials found. "
            "Please provide either (KALSHI_API_KEY_ID + KALSHI_API_PRIVATE_KEY) "
            "or (KALSHI_EMAIL + KALSHI_PASSWORD) in your .env file."
        )

    def _authenticate_with_api_key(self):
        """Authenticate using API key (RSA-PSS request signing method)."""
        if not CRYPTO_AVAILABLE:
            raise ConnectionError(
                "cryptography library is required for API key authentication. "
                "Install with: pip install cryptography"
            )

        try:
            # Load the RSA private key from PEM format
            self.private_key = serialization.load_pem_private_key(
                self.api_private_key_pem.encode('utf-8'),
                password=None,
                backend=default_backend()
            )

            # Test the authentication by making a signed request
            # We'll use a custom request method that signs the request
            response = self._signed_request("GET", "/portfolio/balance")

            if response.status_code == 200:
                self.logger.info("Kalshi API key authentication successful")
                # API keys don't expire like session tokens
                self.token_expiry = None  # No expiry for API keys
                return
            else:
                raise ConnectionError(
                    f"API key test failed: {response.status_code} - {response.text}"
                )

        except Exception as e:
            self.logger.error(f"API key authentication failed: {e}")
            raise

    def _sign_request(self, timestamp: str, method: str, path: str) -> str:
        """Sign a request using RSA-PSS with SHA256.

        Args:
            timestamp: Timestamp in milliseconds
            method: HTTP method (GET, POST, etc.)
            path: Request path without query parameters

        Returns:
            Base64-encoded signature
        """
        # Message format: timestamp + method + path
        msg_string = timestamp + method + path
        msg_bytes = msg_string.encode('utf-8')

        # Sign using RSA-PSS with SHA256
        signature = self.private_key.sign(
            msg_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )

        # Return base64-encoded signature
        return base64.b64encode(signature).decode('utf-8')

    def _signed_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """Make a signed request using API key authentication.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            path: Request path (e.g., "/portfolio/balance")
            params: Query parameters
            json_data: JSON body data

        Returns:
            httpx.Response object
        """
        # Generate timestamp in milliseconds
        timestamp_ms = str(int(time.time() * 1000))

        # Strip query parameters from path for signing
        path_for_signing = path.split('?')[0]

        # Sign the request
        signature = self._sign_request(timestamp_ms, method.upper(), path_for_signing)

        # Set headers for signed request
        headers = {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "Content-Type": "application/json",
        }

        # Make the request
        url = f"{self.api_base}{path}"
        response = self.client.request(
            method=method,
            url=url,
            params=params,
            json=json_data,
            headers=headers
        )

        return response

    def _authenticate_with_password(self):
        """Authenticate using email and password."""
        try:
            response = self.client.post(
                f"{self.api_base}/login",
                json={"email": self.email, "password": self.password}
            )

            if response.status_code != 200:
                raise ConnectionError(f"Authentication failed: {response.status_code} - {response.text}")

            data = response.json()
            self.token = data.get("token")

            if not self.token:
                raise ConnectionError("No token received from authentication")

            # Set token in headers for all future requests
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

            # Token expires in 30 minutes
            self.token_expiry = time.time() + (30 * 60)

            self.logger.info("Kalshi email/password authentication successful")

        except Exception as e:
            self.logger.error(f"Kalshi authentication failed: {e}")
            raise

    def _ensure_authenticated(self):
        """Ensure we have a valid token, refresh if needed."""
        # API keys don't expire
        if self.auth_method == "api_key":
            return

        # Password-based tokens expire after 30 minutes
        if self.auth_method == "password":
            if not self.token or (self.token_expiry and time.time() >= self.token_expiry - 60):
                self.logger.info("Token expired or about to expire, re-authenticating...")
                self._authenticate_with_password()

    def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """Make an authenticated request (supports both API key and password auth).

        Args:
            method: HTTP method
            path: Request path
            params: Query parameters
            json_data: JSON body

        Returns:
            httpx.Response
        """
        self._ensure_authenticated()

        if self.auth_method == "api_key":
            # Use signed requests for API key auth
            return self._signed_request(method, path, params, json_data)
        else:
            # Use regular bearer token for password auth
            url = f"{self.api_base}{path}"
            return self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_balance(self) -> float:
        """Get account balance in cents."""
        try:
            response = self._make_request("GET", "/portfolio/balance")

            if response.status_code != 200:
                self.logger.error(f"Error fetching balance: {response.status_code}")
                return 0.0

            data = response.json()
            # Balance is in cents, convert to dollars
            balance_cents = data.get("balance", 0)
            return balance_cents / 100.0

        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}")
            return 0.0

    def get_all_markets(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Fetch all active markets from Kalshi API.

        Args:
            limit: Max markets per request (default 200)

        Returns:
            List of market dictionaries
        """
        all_markets = []
        cursor = None

        while True:
            try:
                params = {
                    "limit": limit,
                    "status": "open",  # Only get open markets
                }

                if cursor:
                    params["cursor"] = cursor

                response = self._make_request("GET", "/markets", params=params)

                if response.status_code != 200:
                    self.logger.error(f"Error fetching markets: {response.status_code}")
                    break

                data = response.json()
                markets = data.get("markets", [])

                if not markets:
                    break

                all_markets.extend(markets)

                # Check for pagination
                cursor = data.get("cursor")
                if not cursor:
                    break

                time.sleep(0.2)  # Rate limiting

            except Exception as e:
                self.logger.error(f"Error fetching markets: {e}")
                break

        return all_markets

    def filter_weather_markets(self, markets: List[Dict[str, Any]]) -> List[WeatherMarket]:
        """Filter markets for weather-related predictions.

        Kalshi weather markets are in the "Climate and Weather" category
        and typically include temperature, precipitation, and snow markets.

        Args:
            markets: List of market dictionaries from API

        Returns:
            List of parsed WeatherMarket objects
        """
        # Weather-related series/tickers
        weather_series = [
            "KXHIGH",  # High temperature series
            "KXLOW",   # Low temperature series
            "KXRAIN",  # Rainfall series
            "KXSNOW",  # Snowfall series
            "KXTEMP",  # Temperature series
        ]

        # Weather keywords
        weather_keywords = [
            "temperature",
            "celsius",
            "fahrenheit",
            "degrees",
            "high temp",
            "low temp",
            "precipitation",
            "rainfall",
            "snowfall",
            "rain",
            "snow",
        ]

        weather_markets = []

        for market_data in markets:
            try:
                ticker = market_data.get("ticker", "")
                title = market_data.get("title", "").lower()
                subtitle = market_data.get("subtitle", "").lower()
                category = market_data.get("category", "").lower()

                # Check if it's a weather series
                is_weather_series = any(series in ticker.upper() for series in weather_series)

                # Check if category is climate/weather
                is_weather_category = "climate" in category or "weather" in category

                # Check if title/subtitle contains weather keywords
                has_weather_keywords = any(
                    keyword in title or keyword in subtitle
                    for keyword in weather_keywords
                )

                if is_weather_series or is_weather_category or has_weather_keywords:
                    weather_market = self._parse_weather_market(market_data)
                    if weather_market:
                        weather_markets.append(weather_market)

            except Exception as e:
                self.logger.error(f"Error filtering market: {e}")
                continue

        return weather_markets

    def _parse_weather_market(self, market_data: Dict[str, Any]) -> Optional[WeatherMarket]:
        """Parse raw Kalshi market data into WeatherMarket model.

        Args:
            market_data: Raw market data from API

        Returns:
            Parsed WeatherMarket or None if parsing fails
        """
        try:
            # Extract basic info
            ticker = market_data.get("ticker", "")
            event_ticker = market_data.get("event_ticker", "")
            title = market_data.get("title", "")
            subtitle = market_data.get("subtitle", "")

            # Combine title and subtitle for question
            question = f"{title} - {subtitle}" if subtitle else title

            # Get prices (Kalshi uses cents: 0-100)
            yes_bid = market_data.get("yes_bid", 50) / 100.0  # Convert to 0-1
            yes_ask = market_data.get("yes_ask", 50) / 100.0
            no_bid = market_data.get("no_bid", 50) / 100.0
            no_ask = market_data.get("no_ask", 50) / 100.0

            # Use mid-price (average of bid and ask)
            yes_price = (yes_bid + yes_ask) / 2.0
            no_price = (no_bid + no_ask) / 2.0

            # Parse close time
            close_time_str = market_data.get("close_time", "")
            if not close_time_str:
                return None

            # Kalshi uses ISO 8601 format
            end_date = datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))

            # Extract location and threshold
            location = self._extract_location(question)
            temp_threshold = self._extract_temperature(question)

            # Get market metrics
            volume = market_data.get("volume", 0)
            liquidity = market_data.get("liquidity", 0)  # open_interest can be used as proxy
            open_interest = market_data.get("open_interest", 0)

            # Status
            status_str = market_data.get("status", "open")
            status = MarketStatus.ACTIVE if status_str == "open" else MarketStatus.CLOSED

            return WeatherMarket(
                market_id=ticker,  # Use ticker as market_id
                condition_id=event_ticker,  # Use event_ticker as condition_id
                question=question,
                description=subtitle,
                yes_token_id=f"{ticker}_YES",  # Synthetic token IDs
                no_token_id=f"{ticker}_NO",
                yes_price=yes_price,
                no_price=no_price,
                spread=abs(yes_price + no_price - 1.0),
                status=status,
                end_date=end_date,
                liquidity=float(liquidity or open_interest),
                volume=float(volume),
                location=location,
                temperature_threshold=temp_threshold,
                weather_type=self._extract_weather_type(question),
                market_url=f"https://kalshi.com/events/{event_ticker}/{ticker}",
            )

        except Exception as e:
            self.logger.error(f"Error parsing Kalshi market: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def execute_limit_order(
        self,
        ticker: str,
        side: str,  # "yes" or "no"
        count: int,  # Number of contracts
        price: int,  # Price in cents (0-100)
        simulation: bool = False
    ) -> Optional[str]:
        """Execute a limit order on Kalshi.

        Args:
            ticker: Market ticker
            side: "yes" or "no"
            count: Number of contracts to buy
            price: Price in cents (0-100)
            simulation: If True, simulate the order

        Returns:
            Order ID if successful
        """
        if simulation:
            print(f"[SIMULATION] Kalshi limit order: BUY {count} {side.upper()} @ {price}¢ on {ticker}")
            return f"sim_{ticker}_{int(time.time())}"

        try:
            order_params = {
                "ticker": ticker,
                "client_order_id": str(uuid.uuid4()),
                "type": "limit",
                "action": "buy",  # We only buy for now
                "side": side.lower(),
                "count": count,
                f"{side.lower()}_price": price,  # yes_price or no_price
            }

            response = self._make_request("POST", "/portfolio/orders", json_data=order_params)

            if response.status_code not in [200, 201]:
                self.logger.error(f"Order failed: {response.status_code} - {response.text}")
                raise Exception(f"Order execution failed: {response.text}")

            data = response.json()
            order_id = data.get("order", {}).get("order_id")

            self.logger.info(f"Kalshi order placed: {order_id}")
            return order_id

        except Exception as e:
            self.logger.error(f"Error executing Kalshi order: {e}")
            raise

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open orders for the account."""
        try:
            response = self._make_request("GET", "/portfolio/orders")

            if response.status_code != 200:
                self.logger.error(f"Error fetching orders: {response.status_code}")
                return []

            data = response.json()
            return data.get("orders", [])

        except Exception as e:
            self.logger.error(f"Error fetching open orders: {e}")
            return []

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions for the account."""
        try:
            response = self._make_request("GET", "/portfolio/positions")

            if response.status_code != 200:
                self.logger.error(f"Error fetching positions: {response.status_code}")
                return []

            data = response.json()
            return data.get("positions", [])

        except Exception as e:
            self.logger.error(f"Error fetching positions: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        try:
            response = self._make_request("DELETE", f"/portfolio/orders/{order_id}")

            if response.status_code not in [200, 204]:
                self.logger.error(f"Error cancelling order: {response.status_code}")
                return False

            self.logger.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return False

    def _extract_location(self, question: str) -> Optional[str]:
        """Extract city/location from market question."""
        # Common cities in Kalshi weather markets
        cities = [
            "New York",
            "NYC",
            "Central Park",
            "Chicago",
            "Miami",
            "Austin",
            "Los Angeles",
            "LA",
            "Boston",
            "Seattle",
            "San Francisco",
            "Washington DC",
            "Denver",
        ]

        question_lower = question.lower()
        for city in cities:
            if city.lower() in question_lower:
                return city

        return None

    def _extract_temperature(self, question: str) -> Optional[float]:
        """Extract temperature threshold from question."""
        import re

        # Look for patterns like "70°F", "70 degrees", "70F", or ranges "51° to 52°"
        patterns = [
            r"(\d+\.?\d*)\s*°?[fF]",  # 70F or 70°F
            r"(\d+\.?\d*)\s*°?[cC]",  # 20C or 20°C
            r"(\d+\.?\d*)\s*degrees",  # 70 degrees
            r"(\d+\.?\d*)\s*°",  # 70°
        ]

        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                return float(match.group(1))

        return None

    def _extract_weather_type(self, question: str) -> Optional[str]:
        """Extract weather event type from question."""
        question_lower = question.lower()

        if "temperature" in question_lower or "degrees" in question_lower or "high" in question_lower or "low" in question_lower:
            return "temperature"
        elif "rain" in question_lower or "precipitation" in question_lower:
            return "precipitation"
        elif "snow" in question_lower:
            return "snow"
        else:
            return "other"
