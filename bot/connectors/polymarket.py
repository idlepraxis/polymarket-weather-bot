"""Polymarket connector using Chainstack node and CLOB API."""

import time
from typing import Any, Dict, List, Optional

import httpx
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType
from tenacity import retry, stop_after_attempt, wait_exponential
from web3 import Web3

# Handle different web3.py versions
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    # web3.py v6+ uses ExtraDataToPOAMiddleware
    try:
        from web3.middleware import ExtraDataToPOAMiddleware
        geth_poa_middleware = ExtraDataToPOAMiddleware
    except ImportError:
        # If neither works, define a no-op middleware
        geth_poa_middleware = lambda make_request, web3: make_request

from bot.utils.config import Config
from bot.utils.models import WeatherMarket, MarketStatus


class PolymarketClient:
    """Client for interacting with Polymarket via Chainstack and CLOB API."""

    def __init__(self, config: Config):
        self.config = config
        self._setup_web3()
        self._setup_clob_client()

    def _setup_web3(self):
        """Initialize Web3 connection to Chainstack Polygon node."""
        # Primary: HTTP RPC
        self.web3 = Web3(Web3.HTTPProvider(self.config.chainstack_rpc_url))

        # Inject POA middleware for Polygon (if available)
        try:
            if callable(geth_poa_middleware):
                self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        except Exception as e:
            print(f"Warning: Could not inject POA middleware: {e}")

        # WebSocket for real-time events (optional, for monitoring)
        try:
            self.web3_ws = Web3(Web3.WebsocketProvider(self.config.chainstack_ws_url))
            try:
                if callable(geth_poa_middleware):
                    self.web3_ws.middleware_onion.inject(geth_poa_middleware, layer=0)
            except:
                pass
        except Exception as e:
            print(f"Warning: WebSocket connection failed: {e}")
            self.web3_ws = None

        # Verify connection
        if not self.web3.is_connected():
            raise ConnectionError("Failed to connect to Chainstack Polygon node")

        # Load account
        self.account = Account.from_key(self.config.polygon_wallet_private_key)
        self.address = self.account.address

        print(f"Connected to Polygon via Chainstack")
        print(f"Wallet address: {self.address}")
        print(f"Chain ID: {self.web3.eth.chain_id}")

    def _setup_clob_client(self):
        """Initialize Polymarket CLOB client."""
        self.clob_client = ClobClient(
            host=self.config.clob_url,
            key=self.config.polygon_wallet_private_key,
            chain_id=self.config.chain_id,
        )

        # Create or derive API credentials
        try:
            if all([self.config.clob_api_key, self.config.clob_secret, self.config.clob_pass_phrase]):
                # Use pre-derived credentials
                self.credentials = {
                    "apiKey": self.config.clob_api_key,
                    "secret": self.config.clob_secret,
                    "passphrase": self.config.clob_pass_phrase,
                }
            else:
                # Derive new credentials
                self.credentials = self.clob_client.create_or_derive_api_creds()

            self.clob_client.set_api_creds(self.credentials)
            print(f"CLOB client initialized for {self.config.clob_url}")

        except Exception as e:
            print(f"Warning: CLOB credential setup failed: {e}")
            self.credentials = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_usdc_balance(self) -> float:
        """Get USDC balance using Chainstack node."""
        usdc_contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(self.config.usdc_address),
            abi=[
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function",
                }
            ],
        )

        balance_wei = usdc_contract.functions.balanceOf(self.address).call()
        # USDC has 6 decimals
        balance_usdc = balance_wei / 1e6
        return balance_usdc

    def get_all_markets(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch all active markets from Gamma API."""
        all_markets = []
        offset = 0

        while True:
            params = {
                "closed": False,  # Only get open markets
                "limit": limit,
                "offset": offset,
            }

            response = httpx.get(
                f"{self.config.gamma_api_url}/markets",
                params=params,
                timeout=30.0,
            )

            if response.status_code != 200:
                print(f"Error fetching markets: {response.status_code}")
                break

            markets = response.json()
            if not markets:
                break

            all_markets.extend(markets)

            if len(markets) < limit:
                break

            offset += limit
            time.sleep(0.5)  # Rate limiting

        return all_markets

    def filter_weather_markets(self, markets: List[Dict[str, Any]]) -> List[WeatherMarket]:
        """Filter markets for weather-related predictions."""
        weather_keywords = [
            "temperature",
            "rain",
            "snow",
            "weather",
            "celsius",
            "fahrenheit",
            "precipitation",
            "storm",
            "hurricane",
            "tornado",
            "forecast",
            "high temp",
            "low temp",
            "degrees",
        ]

        weather_markets = []

        for market_data in markets:
            try:
                question = market_data.get("question", "").lower()

                # Check if market is weather-related
                if not any(keyword in question for keyword in weather_keywords):
                    continue

                # Parse market data
                weather_market = self._parse_weather_market(market_data)
                if weather_market:
                    weather_markets.append(weather_market)

            except Exception as e:
                print(f"Error parsing market: {e}")
                continue

        return weather_markets

    def _parse_weather_market(self, market_data: Dict[str, Any]) -> Optional[WeatherMarket]:
        """Parse raw market data into WeatherMarket model."""
        try:
            import json
            from datetime import datetime

            # Extract token IDs from clobTokenIds (it's a JSON string)
            clob_token_ids_str = market_data.get("clobTokenIds")
            if not clob_token_ids_str:
                return None

            try:
                clob_token_ids = json.loads(clob_token_ids_str)
                if not isinstance(clob_token_ids, list) or len(clob_token_ids) < 2:
                    return None
            except (json.JSONDecodeError, TypeError):
                return None

            # First token is usually YES, second is NO
            yes_token_id = clob_token_ids[0]
            no_token_id = clob_token_ids[1]

            # Get prices from orderbook
            yes_price = self.get_token_price(yes_token_id)
            no_price = self.get_token_price(no_token_id)

            # Parse end date - use endDateIso or endDate
            end_date_str = market_data.get("endDateIso") or market_data.get("endDate")
            if not end_date_str:
                return None

            if isinstance(end_date_str, str):
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            else:
                end_date = datetime.fromisoformat(str(end_date_str))

            # Extract location and threshold from question
            question = market_data.get("question", "")
            if not question:
                return None

            location = self._extract_location(question)
            temp_threshold = self._extract_temperature(question)

            # Get condition ID
            condition_id = market_data.get("conditionId", "")

            return WeatherMarket(
                market_id=str(market_data.get("id", "")),
                condition_id=condition_id,
                question=question,
                description=market_data.get("description"),
                yes_token_id=yes_token_id,
                no_token_id=no_token_id,
                yes_price=yes_price,
                no_price=no_price,
                spread=abs(yes_price + no_price - 1.0),
                status=MarketStatus.ACTIVE,
                end_date=end_date,
                liquidity=float(market_data.get("liquidityNum", 0) or market_data.get("liquidity", 0) or 0),
                volume=float(market_data.get("volumeNum", 0) or market_data.get("volume", 0) or 0),
                location=location,
                temperature_threshold=temp_threshold,
                weather_type=self._extract_weather_type(question),
                market_url=f"https://polymarket.com/event/{market_data.get('slug', '')}",
            )

        except Exception as e:
            print(f"Error parsing weather market: {e}")
            return None

    def get_token_price(self, token_id: str) -> float:
        """Get current token price from orderbook."""
        try:
            price = self.clob_client.get_price(token_id)
            return float(price) if price else 0.5  # Default to 0.5 if no price
        except Exception as e:
            print(f"Error fetching price for {token_id}: {e}")
            return 0.5

    def get_orderbook(self, token_id: str) -> Dict[str, Any]:
        """Get full orderbook for a token."""
        try:
            return self.clob_client.get_order_book(token_id)
        except Exception as e:
            print(f"Error fetching orderbook for {token_id}: {e}")
            return {}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def execute_limit_order(
        self, token_id: str, price: float, size: float, side: str, simulation: bool = False
    ) -> Optional[str]:
        """Execute a limit order."""
        if simulation:
            print(f"[SIMULATION] Limit order: {side} {size} shares @ ${price:.3f}")
            return f"sim_{token_id}_{int(time.time())}"

        try:
            order_args = OrderArgs(
                price=price,
                size=size,
                side=side,
                token_id=token_id,
            )

            order_id = self.clob_client.create_and_post_order(order_args)
            print(f"Limit order placed: {order_id}")
            return order_id

        except Exception as e:
            print(f"Error executing limit order: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def execute_market_order(
        self, token_id: str, amount: float, simulation: bool = False
    ) -> Optional[str]:
        """Execute a market order (FOK)."""
        if simulation:
            print(f"[SIMULATION] Market order: {amount} USDC on token {token_id}")
            return f"sim_market_{token_id}_{int(time.time())}"

        try:
            order_args = MarketOrderArgs(token_id=token_id, amount=amount)
            signed_order = self.clob_client.create_market_order(order_args)
            response = self.clob_client.post_order(signed_order, OrderType.FOK)
            print(f"Market order executed: {response}")
            return response.get("orderID")

        except Exception as e:
            print(f"Error executing market order: {e}")
            raise

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open orders for the account."""
        try:
            return self.clob_client.get_orders()
        except Exception as e:
            print(f"Error fetching open orders: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        try:
            self.clob_client.cancel(order_id)
            print(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            print(f"Error cancelling order {order_id}: {e}")
            return False

    def _extract_location(self, question: str) -> Optional[str]:
        """Extract city/location from market question."""
        # Common cities in weather markets
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
        ]

        question_lower = question.lower()
        for city in cities:
            if city.lower() in question_lower:
                return city

        return None

    def _extract_temperature(self, question: str) -> Optional[float]:
        """Extract temperature threshold from question."""
        import re

        # Look for patterns like "70°F", "70 degrees", "70F"
        patterns = [
            r"(\d+)\s*°?[fF]",  # 70F or 70°F
            r"(\d+)\s*°?[cC]",  # 20C or 20°C
            r"(\d+)\s*degrees",  # 70 degrees
        ]

        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                return float(match.group(1))

        return None

    def _extract_weather_type(self, question: str) -> Optional[str]:
        """Extract weather event type from question."""
        question_lower = question.lower()

        if "temperature" in question_lower or "degrees" in question_lower:
            return "temperature"
        elif "rain" in question_lower or "precipitation" in question_lower:
            return "precipitation"
        elif "snow" in question_lower:
            return "snow"
        elif "storm" in question_lower or "hurricane" in question_lower:
            return "storm"
        else:
            return "other"
