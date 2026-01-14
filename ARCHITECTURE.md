# Polymarket Weather Bot: Complete Architecture Map

**Version:** 2.0.0 (Multi-Platform)
**Last Updated:** January 14, 2026
**Purpose:** Comprehensive program map for context preservation and future development

**New in v2.0:** Multi-platform support - now trades on both Polymarket AND Kalshi!

---

## 📋 Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Data Flow](#data-flow)
3. [File-by-File Breakdown](#file-by-file-breakdown)
4. [Core Functions Reference](#core-functions-reference)
5. [Integration Points](#integration-points)
6. [Common Issues & Solutions](#common-issues--solutions)
7. [How to Modify/Extend](#how-to-modifyextend)

---

## High-Level Architecture (v2.0 - Multi-Platform)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                                  │
│                     bot/cli/cli.py (Typer + Rich)                      │
│  Commands: extreme-scan --platform [polymarket|kalshi]                 │
│            extreme-trade --platform [polymarket|kalshi]                │
└────────────────┬────────────────────────────────────────────────────────┘
                 │
    ┌────────────┴─────────────┐
    │                          │
    ▼                          ▼
┌─────────────────┐    ┌──────────────────┐
│   APPLICATION   │    │   APPLICATION    │
│     LAYER       │    │      LAYER       │
│                 │    │                  │
│  trader.py      │    │  extreme_value   │
│  (Forecast      │    │  _strategy.py    │
│   Arbitrage)    │    │  (Price-driven)  │
│                 │    │  ** PLATFORM-    │
│                 │    │   AGNOSTIC **    │
└────────┬────────┘    └────────┬─────────┘
         │                      │
         └──────────┬───────────┘
                    │
    ┌───────────────┴─────────────────────┐
    │                                     │
    ▼                                     ▼
┌───────────────────┐         ┌──────────────────┐
│   CONNECTORS      │         │    CONNECTORS    │
│                   │         │                  │
│  polymarket.py    │         │   kalshi.py      │
│  - Chainstack     │         │   - RSA-PSS Auth │
│  - CLOB API       │         │   - REST API     │
│  - Web3           │         │   - 10 Cities    │
│  - 175+ markets   │         │   - 72 markets   │
└──────────┬────────┘         └────────┬─────────┘
           │                           │
           └──────────┬────────────────┘
                      │
       ┌──────────────┴─────────────────┐
       │                                │
       ▼                                ▼
┌──────────────────┐         ┌──────────────────┐
│   weather.py     │         │   EXTERNAL APIs  │
│   - OpenWeather  │         │                  │
│   - WeatherAPI   │         │  - Polygon RPC   │
│   - NOAA         │         │  - Polymarket    │
└──────────────────┘         │  - Kalshi        │
                             │  - Weather APIs  │
                             └──────────────────┘

┌─────────────────────────────────────────────┐
│              UTILS LAYER                    │
│  - config.py (loads both platform creds)   │
│  - models.py (unified WeatherMarket)       │
│  - logger.py                               │
└─────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Key Functions |
|-----------|---------------|---------------|
| **CLI** | User interface, multi-platform routing | `extreme_scan()`, `extreme_trade()`, `--platform` flag |
| **ExtremeValueStrategy** | Price-driven trading (platform-agnostic) | `scan_for_opportunities()`, `_check_yes_opportunity()` |
| **Trader** | Forecast-driven trading logic | `analyze_market()`, `scan_and_trade()` |
| **PolymarketClient** | Polymarket blockchain & market data | `get_all_markets()`, `execute_market_order()`, `batch_get_token_prices()` |
| **KalshiClient** | Kalshi REST API & trading | `get_all_markets()`, `execute_limit_order()`, `_discover_weather_series()` |
| **WeatherConnector** | Weather forecasts | `get_forecast()`, `calculate_probability()` |
| **Config** | Configuration management | Load/validate `.env` for both platforms |
| **Models** | Type-safe data structures | `WeatherMarket`, `TradeSignal`, `Trade` (unified across platforms) |

---

## Data Flow

### Extreme Value Trading Flow (Primary Strategy)

```
1. USER → CLI
   python bot.py extreme-scan --limit 20

2. CLI → PolymarketClient
   get_all_markets()
   └→ Gamma API: GET /markets?closed=false

3. PolymarketClient → filter_weather_markets()
   ├→ Extract weather markets (temperature keywords)
   ├→ Collect all token IDs
   └→ batch_get_token_prices(token_ids)
      └→ ThreadPoolExecutor(5 workers)
         └→ CLOB API: get_price(token_id, side="BUY")
            Returns: {'price': '0.59'}

4. PolymarketClient → ExtremeValueStrategy
   Returns: List[WeatherMarket] with prices

5. ExtremeValueStrategy → scan_for_opportunities()
   For each market:
     ├→ _check_yes_opportunity()
     │  ├→ if yes_price <= 0.15:
     │  │  ├→ Calculate position size
     │  │  ├→ Estimate fair_probability
     │  │  └→ Return TradeSignal
     │  └→ else: return None
     │
     └→ _check_no_opportunity()
        ├→ if yes_price >= 0.40:
        │  ├→ Calculate position size
        │  ├→ Estimate fair_probability
        │  └→ Return TradeSignal
        └→ else: return None

6. ExtremeValueStrategy → Filter & Sort
   ├→ filter_by_time_to_resolution()
   ├→ filter_by_liquidity()
   └→ Sort by EV (highest first)

7. CLI → Display Results
   Rich table with opportunities

8. TRADE EXECUTION (if --live mode):
   CLI → PolymarketClient.execute_market_order()
   └→ CLOB API: create_market_order()
      └→ Blockchain: Sign & submit transaction
```

### Price Fetching Optimization (Critical Performance Feature)

```
OLD WAY (Sequential):
for token_id in token_ids:
    price = get_price(token_id)  # 0.1s per call
Total: 700 tokens × 0.1s = 70 seconds

NEW WAY (Batch Concurrent):
batch_get_token_prices(token_ids):
    ThreadPoolExecutor(max_workers=5):
        for token_id in token_ids:
            future = submit(get_price, token_id)
            time.sleep(0.05)  # Rate limit

Total: 700 tokens ÷ 5 workers ≈ 10-15 seconds (5-7x faster!)
```

---

## File-by-File Breakdown

### 📁 `bot/cli/cli.py` (510 lines)

**Purpose:** Command-line interface using Typer + Rich

#### Key Functions:

```python
@app.command()
def extreme_scan(limit: int, yes_max: float, no_min_yes: float):
    """Scan for extreme value opportunities without trading"""
    # 1. Initialize connectors
    # 2. Fetch all markets
    # 3. Filter weather markets
    # 4. Run extreme value strategy scan
    # 5. Display results in Rich table
    # Returns: None (prints to console)

@app.command()
def extreme_trade(dry_run: bool, max_trades: int, ...):
    """Execute extreme value trades (simulation or live)"""
    # 1. Get opportunities from extreme_scan logic
    # 2. Iterate through top N opportunities
    # 3. Execute trades via polymarket.execute_market_order()
    # 4. Track success/failures
    # Returns: None (prints to console)

@app.command()
def status():
    """Show portfolio status"""
    # 1. Get trader instance
    # 2. Fetch portfolio data
    # 3. Display metrics: balance, P&L, win rate, positions
    # Returns: None (prints to console)

@app.command()
def balance():
    """Check USDC balance"""
    # 1. Connect to PolymarketClient
    # 2. Call get_usdc_balance()
    # 3. Display balance
    # Returns: None (prints to console)
```

**Critical Logic:**
- Line 482: `signal.action` NOT `signal.action.value` (enum already converted to string)
- Line 473-477: execute_market_order() with simulation flag
- Lines 375-401: Rich table formatting for opportunities

---

### 📁 `bot/application/extreme_value_strategy.py` (372 lines)

**Purpose:** Core extreme value betting strategy (THE MONEY-MAKER)

#### Key Functions:

```python
class ExtremeValueStrategy:
    def scan_for_opportunities(markets: List[WeatherMarket]) -> List[TradeSignal]:
        """Main entry point: scan all markets for extreme values"""
        signals = []
        for market in markets:
            yes_signal = self._check_yes_opportunity(market)
            if yes_signal:
                signals.append(yes_signal)

            no_signal = self._check_no_opportunity(market)
            if no_signal:
                signals.append(no_signal)

        # Sort by EV (expected value)
        signals.sort(key=lambda s: self._calculate_ev(s), reverse=True)
        return signals

    def _check_yes_opportunity(market: WeatherMarket) -> Optional[TradeSignal]:
        """Check if YES shares are cheap enough"""
        yes_price = market.yes_price

        # CRITICAL THRESHOLDS
        if yes_price >= 0.15:  # Max threshold
            return None

        # Position sizing based on extremity
        if yes_price <= 0.05:
            size = 5.00  # Super cheap
        elif yes_price <= 0.10:
            size = 1.00  # Ideal
        else:
            size = 0.50  # Acceptable

        # Estimate fair probability (conservative)
        fair_prob = max(yes_price * 2.5, 0.20)
        edge = fair_prob - yes_price

        return TradeSignal(
            market=market,
            fair_probability=fair_prob,
            market_probability=yes_price,
            edge=edge,
            action=TradeSide.BUY,
            token_id=market.yes_token_id,
            price=yes_price,
            size=size,
            ...
        )

    def _check_no_opportunity(market: WeatherMarket) -> Optional[TradeSignal]:
        """Check if NO shares are cheap (YES overpriced)"""
        yes_price = market.yes_price

        # CRITICAL THRESHOLDS
        if yes_price <= 0.40:  # Min threshold
            return None

        # Position sizing
        if yes_price >= 0.60:
            size = 5.00  # NO very cheap
        elif yes_price >= 0.50:
            size = 1.00  # NO cheap
        else:
            size = 0.50  # NO acceptable

        # Similar logic to YES
        ...

    def _calculate_ev(signal: TradeSignal) -> float:
        """Calculate expected value"""
        # EV = (win_prob × win_amount) - (lose_prob × lose_amount)
        win_prob = signal.fair_probability
        lose_prob = 1 - win_prob
        win_amount = signal.size * (1 - signal.price)
        lose_amount = signal.size * signal.price
        return (win_prob * win_amount) - (lose_prob * lose_amount)
```

**Critical Constants:**
- `EXTREME_YES_MAX_PRICE = 0.15` (never buy YES above 15¢)
- `EXTREME_NO_MIN_YES_PRICE = 0.40` (never buy NO when YES below 40¢)
- Position sizes: $0.50 min, $1.00 standard, $5.00 aggressive max

**Key Insight:** This strategy is price-driven, NOT forecast-driven. It exploits market microstructure inefficiencies.

---

### 📁 `bot/connectors/polymarket.py` (450+ lines)

**Purpose:** Interface to Polymarket (Chainstack, CLOB API, Web3)

#### Critical Functions:

```python
class PolymarketClient:
    def __init__(config: Config):
        """Initialize connections"""
        # 1. Setup Web3 with Chainstack RPC
        self.web3 = Web3(Web3.HTTPProvider(config.chainstack_rpc_url))

        # 2. Setup CLOB client
        self.clob_client = ClobClient(
            host="https://clob.polymarket.com",
            key=account.key
        )

        # 3. Inject PoA middleware for Polygon
        try:
            from web3.middleware import geth_poa_middleware
        except ImportError:
            from web3.middleware import ExtraDataToPOAMiddleware
            geth_poa_middleware = ExtraDataToPOAMiddleware

        self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)

    def get_all_markets(limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch all active markets from Gamma API"""
        all_markets = []
        offset = 0

        while True:
            params = {
                "closed": False,  # API v4 change: use "closed" not "active"
                "limit": limit,
                "offset": offset,
            }

            response = httpx.get(
                f"{self.config.gamma_api_url}/markets",
                params=params,
                timeout=30.0,
            )

            if response.status_code != 200:
                break

            markets = response.json()
            if not markets:
                break

            all_markets.extend(markets)
            offset += limit

        return all_markets

    def filter_weather_markets(markets: List[Dict]) -> List[WeatherMarket]:
        """Filter for weather markets only"""
        # CRITICAL: Two-pass processing for performance

        # PASS 1: Filter & collect token IDs
        weather_market_data = []
        all_token_ids = []

        for market_data in markets:
            question = market_data.get("question", "").lower()

            # Check weather keywords
            if not any(kw in question for kw in weather_keywords):
                continue

            # Exclude sports markets
            if any(exc in question for exc in sports_exclusions):
                continue

            # Parse token IDs from clobTokenIds JSON string
            clob_token_ids = json.loads(market_data.get("clobTokenIds"))
            all_token_ids.extend(clob_token_ids[:2])
            weather_market_data.append(market_data)

        # PASS 2: Batch fetch all prices concurrently
        price_cache = self.batch_get_token_prices(all_token_ids)

        # PASS 3: Parse markets using cached prices
        weather_markets = []
        for market_data in weather_market_data:
            market = self._parse_weather_market(market_data, price_cache)
            if market:
                weather_markets.append(market)

        return weather_markets

    def batch_get_token_prices(token_ids: List[str], max_workers: int = 5) -> Dict[str, float]:
        """CRITICAL PERFORMANCE FUNCTION - Fetch prices concurrently"""
        prices = {}

        def fetch_single_price(token_id: str):
            time.sleep(0.05)  # Rate limit: 50ms delay
            price = self.get_token_price(token_id, silent=True)
            return token_id, price

        # Concurrent fetching with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_token = {
                executor.submit(fetch_single_price, token_id): token_id
                for token_id in token_ids
            }

            for future in as_completed(future_to_token):
                try:
                    token_id, price = future.result()
                    prices[token_id] = price
                except Exception:
                    prices[token_id] = 0.5  # Fallback

        return prices

    def get_token_price(token_id: str, silent: bool = False) -> float:
        """Get single token price"""
        try:
            # py-clob-client v0.34+ requires 'side' parameter
            price_data = self.clob_client.get_price(token_id, side="BUY")

            # Handle dict response: {'price': '0.59'}
            if isinstance(price_data, dict):
                price = price_data.get("price")
                if price is not None:
                    price_float = float(price)
                    # CRITICAL: Prevent division by zero
                    return price_float if price_float > 0 else 0.5
                return 0.5
            else:
                # Direct numeric value
                if price_data:
                    price_float = float(price_data)
                    return price_float if price_float > 0 else 0.5
                return 0.5
        except Exception as e:
            if not silent:
                print(f"Error fetching price for {token_id}: {e}")
            return 0.5

    def execute_market_order(token_id: str, amount: float, simulation: bool = False) -> Optional[str]:
        """Execute market order (buy/sell)"""
        if simulation:
            print(f"[SIMULATION] Market order: {amount} USDC on token {token_id}")
            return f"sim_{token_id}_{int(time.time())}"

        # Live execution
        order = self.clob_client.create_market_order(
            token_id=token_id,
            amount=amount,
        )
        return order.get("orderID")
```

**Critical Implementation Details:**

1. **Web3 Middleware**: Must inject PoA middleware for Polygon compatibility
2. **API v4 Changes**: Use `closed=False` instead of `active=True`
3. **Response Parsing**: `clobTokenIds` is JSON string, must parse with `json.loads()`
4. **Price Response**: Returns dict `{'price': '0.59'}`, not direct float
5. **Batch Fetching**: 5 workers, 50ms delay to avoid rate limits
6. **Division by Zero**: Always check `price > 0` before using

---

### 📁 `bot/utils/models.py` (238 lines)

**Purpose:** Pydantic models for type-safe data handling

#### Key Models:

```python
class WeatherMarket(BaseModel):
    """Weather prediction market data"""
    market_id: str
    condition_id: str
    question: str

    # Token IDs
    yes_token_id: str
    no_token_id: str

    # Pricing
    yes_price: float = Field(..., ge=0.0, le=1.0)
    no_price: float = Field(..., ge=0.0, le=1.0)

    # Metadata
    status: MarketStatus = MarketStatus.ACTIVE
    end_date: datetime
    liquidity: float = 0.0
    volume: float = 0.0

    # Weather-specific
    location: Optional[str] = None
    temperature_threshold: Optional[float] = None

    class Config:
        use_enum_values = True  # Auto-convert enums to strings

class TradeSignal(BaseModel):
    """Trading signal with analysis"""
    market: WeatherMarket
    forecast: Optional[WeatherForecast] = Field(None)  # CRITICAL: Optional for extreme value

    # Analysis
    fair_probability: float = Field(..., ge=0.0, le=1.0)
    market_probability: float = Field(..., ge=0.0, le=1.0)
    edge: float  # fair_prob - market_prob
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Trade recommendation
    action: TradeSide  # "BUY" or "SELL"
    token_id: str
    price: float = Field(..., ge=0.0, le=1.0)
    size: float = Field(..., gt=0.0)

    reasoning: str

    class Config:
        use_enum_values = True  # CRITICAL: This makes action a string

class Trade(BaseModel):
    """Executed trade record"""
    trade_id: str
    timestamp: datetime

    # Market info
    market_id: str
    question: str
    token_id: str

    # Trade details
    side: TradeSide
    price: float
    size: float
    cost: float

    # Status
    simulation: bool = False
    tx_hash: Optional[str] = None
    status: str = "pending"
```

**Critical Configuration:**
- `use_enum_values = True` in Config class means `TradeSide.BUY` is auto-converted to string `"BUY"`
- This is why we use `signal.action` NOT `signal.action.value` (common error!)
- `forecast` field is Optional for extreme value strategy

---

### 📁 `bot/utils/config.py` (150+ lines)

**Purpose:** Configuration management with Pydantic

```python
class Config(BaseSettings):
    """Bot configuration from .env file"""

    # Blockchain
    polygon_wallet_private_key: str = Field(..., alias="POLYGON_WALLET_PRIVATE_KEY")
    chainstack_rpc_url: str = Field(..., alias="CHAINSTACK_RPC_URL")
    chainstack_ws_url: Optional[str] = Field(None, alias="CHAINSTACK_WS_URL")

    # Polymarket APIs
    clob_url: str = Field("https://clob.polymarket.com", alias="CLOB_URL")
    gamma_api_url: str = Field("https://gamma-api.polymarket.com", alias="GAMMA_API_URL")

    # Extreme Value Strategy Parameters
    extreme_yes_max_price: float = Field(0.15, alias="EXTREME_YES_MAX_PRICE")
    extreme_yes_ideal_price: float = Field(0.10, alias="EXTREME_YES_IDEAL_PRICE")
    extreme_no_min_yes_price: float = Field(0.40, alias="EXTREME_NO_MIN_YES_PRICE")
    extreme_no_ideal_yes_price: float = Field(0.50, alias="EXTREME_NO_IDEAL_YES_PRICE")
    extreme_min_position: float = Field(0.50, alias="EXTREME_MIN_POSITION")
    extreme_max_position: float = Field(1.00, alias="EXTREME_MAX_POSITION")
    extreme_aggressive_max: float = Field(5.00, alias="EXTREME_AGGRESSIVE_MAX")

    # Risk Management
    simulation_mode: bool = Field(True, alias="SIMULATION_MODE")
    max_daily_trades: int = Field(50, alias="MAX_DAILY_TRADES")
    max_open_positions: int = Field(20, alias="MAX_OPEN_POSITIONS")
    bankroll_usdc: float = Field(1000.0, alias="BANKROLL_USDC")

    class Config:
        env_file = ".env"
        case_sensitive = False

def get_config() -> Config:
    """Get configuration (singleton pattern)"""
    return Config()
```

**Key Features:**
- Loads from `.env` file automatically
- Type validation with Pydantic
- Default values for all settings
- Field aliases map to env var names

---

## Core Functions Reference

### Market Scanning Flow

```
get_all_markets()
  ↓
filter_weather_markets()
  ↓
[Weather markets with prices]
  ↓
scan_for_opportunities()
  ↓
[List of TradeSignal objects sorted by EV]
```

### Trade Execution Flow

```
TradeSignal
  ↓
execute_market_order(
    token_id=signal.token_id,
    amount=signal.size,
    simulation=True/False
)
  ↓
If simulation:
    Print message
    Return mock order_id

If live:
    clob_client.create_market_order()
      ↓
    Sign transaction with wallet
      ↓
    Submit to Polygon blockchain
      ↓
    Return transaction hash
```

---

## Integration Points

### 1. Chainstack (Polygon RPC)

**Endpoint:** `https://polygon-mainnet.core.chainstack.com/{API_KEY}`

**Usage:**
- Get USDC balance: `web3.eth.contract(...).functions.balanceOf(address).call()`
- Check chain ID: `web3.eth.chain_id`
- Sign transactions: `web3.eth.account.sign_transaction()`

**Rate Limits:** 3M requests/month (we use ~500k)

### 2. Polymarket Gamma API

**Endpoint:** `https://gamma-api.polymarket.com`

**Key Endpoints:**
```
GET /markets?closed=false&limit=100&offset=0
Returns: List of market objects

Market Object Structure (v4):
{
  "id": "...",
  "question": "Will the highest temperature...",
  "clobTokenIds": "[\"token1\", \"token2\"]",  // JSON string!
  "endDateIso": "2026-01-15T00:00:00.000Z",
  "liquidityNum": 1500.5,
  "volumeNum": 5000.0,
  "conditionId": "...",
  ...
}
```

**Critical Changes (v3 → v4):**
- `active=True` → `closed=false`
- `tokens` array → `clobTokenIds` JSON string
- `liquidity` → `liquidityNum`
- `volume` → `volumeNum`
- `endDate` → `endDateIso`

### 3. Polymarket CLOB API

**Endpoint:** `https://clob.polymarket.com`

**Authentication:**
```python
# Derive credentials from private key
credentials = clob_client.create_or_derive_api_creds()

# Or use pre-derived
credentials = {
    "api_key": "...",
    "secret": "...",
    "passphrase": "..."
}

clob_client.set_api_creds(credentials)
```

**Key Methods:**
```python
# Get token price
clob_client.get_price(token_id, side="BUY")
Returns: {"price": "0.59"}

# Create market order
clob_client.create_market_order(
    token_id="...",
    amount=5.0
)
Returns: {"orderID": "...", "status": "..."}

# Get orderbook
clob_client.get_order_book(token_id)
Returns: {"bids": [...], "asks": [...]}
```

**CRITICAL:** v0.34+ requires `side` parameter in `get_price()`

### 4. Weather APIs (Optional - for Forecast Arbitrage)

**OpenWeather API:**
```
Endpoint: https://api.openweathermap.org/data/2.5/forecast
Usage: 5-day forecast, 3-hour intervals
```

**WeatherAPI:**
```
Endpoint: https://api.weatherapi.com/v1/forecast.json
Usage: 14-day forecast
```

---

## Common Issues & Solutions

### Issue 1: `'str' object has no attribute 'value'`

**Cause:** Trying to access `.value` on enum that's already converted to string

**Location:** `bot/cli/cli.py` lines 151, 482

**Solution:**
```python
# WRONG
print(signal.action.value)

# CORRECT
print(signal.action)
```

**Why:** Pydantic's `use_enum_values = True` auto-converts `TradeSide.BUY` → `"BUY"`

---

### Issue 2: `float() argument must be a string or a real number, not 'dict'`

**Cause:** API returns `{'price': '0.59'}` but code expects float

**Location:** `bot/connectors/polymarket.py` line 315

**Solution:**
```python
price_data = self.clob_client.get_price(token_id, side="BUY")

# Handle dict response
if isinstance(price_data, dict):
    price = price_data.get("price")
    return float(price) if price is not None else 0.5
else:
    return float(price_data) if price_data else 0.5
```

---

### Issue 3: `division by zero`

**Cause:** Token price returns 0.0, then `payoff_ratio = (1 - price) / price` crashes

**Location:** `bot/connectors/polymarket.py` line 338

**Solution:**
```python
price_float = float(price)
# ALWAYS check before using
return price_float if price_float > 0 else 0.5
```

---

### Issue 4: Cloudflare Rate Limiting (400 Bad Request)

**Cause:** Too many concurrent requests (20 workers) triggers DDoS protection

**Location:** `bot/connectors/polymarket.py` line 344

**Solution:**
```python
# Reduce workers
ThreadPoolExecutor(max_workers=5)  # NOT 20

# Add delay
def fetch_single_price(token_id):
    time.sleep(0.05)  # 50ms delay
    return get_price(token_id)
```

---

### Issue 5: Sports Markets Passing Through Filter

**Cause:** Team names like "Hurricanes" match weather keywords

**Location:** `bot/connectors/polymarket.py` line 159

**Solution:**
```python
# Add sports exclusions
sports_exclusions = ["vs", "vs.", "o/u", "over/under", "spread"]

# Exclude team names
team_exclusions = ["hurricanes", "storm", "heat", "thunder"]

# Check context
has_team_name = any(team in question for team in team_exclusions)
has_temp_context = any(word in question for word in ["temperature", "degrees"])

if has_team_name and not has_temp_context:
    continue  # Skip sports market
```

---

### Issue 6: `ClobClient.get_price() missing 1 required positional argument: 'side'`

**Cause:** py-clob-client v0.34+ changed API

**Location:** `bot/connectors/polymarket.py` line 274

**Solution:**
```python
# OLD (v0.22)
price = self.clob_client.get_price(token_id)

# NEW (v0.34+)
price = self.clob_client.get_price(token_id, side="BUY")
```

---

### Issue 7: Web3 Middleware Import Error

**Cause:** web3.py v6+ renamed middleware

**Location:** `bot/connectors/polymarket.py` line 13-23

**Solution:**
```python
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    try:
        from web3.middleware import ExtraDataToPOAMiddleware
        geth_poa_middleware = ExtraDataToPOAMiddleware
    except ImportError:
        geth_poa_middleware = lambda make_request, web3: make_request
```

---

## How to Modify/Extend

### Change Price Thresholds

**File:** `bot/application/extreme_value_strategy.py`

**Lines:** 87-88, 140

```python
# Current
if yes_price >= 0.15:  # Max 15¢ for YES
    return None

# More aggressive (find more opportunities)
if yes_price >= 0.20:  # Max 20¢ for YES
    return None

# More conservative (fewer but better opportunities)
if yes_price >= 0.10:  # Max 10¢ for YES
    return None
```

---

### Change Position Sizing

**File:** `bot/application/extreme_value_strategy.py`

**Lines:** 189-202

```python
# Current
if yes_price <= 0.05:
    size = 5.00  # Super cheap
elif yes_price <= 0.10:
    size = 1.00  # Ideal
else:
    size = 0.50  # Acceptable

# More aggressive
if yes_price <= 0.05:
    size = 10.00  # Double down on extreme values
elif yes_price <= 0.10:
    size = 2.00
else:
    size = 1.00
```

---

### Add New CLI Command

**File:** `bot/cli/cli.py`

```python
@app.command()
def my_new_command(
    param1: int = typer.Option(10, help="Description"),
    param2: bool = typer.Option(False, help="Description"),
):
    """My new command description"""
    try:
        # 1. Get config
        config = get_config()

        # 2. Initialize connectors
        polymarket = PolymarketClient(config)

        # 3. Do your logic
        result = polymarket.some_method(param1)

        # 4. Display results
        console.print(f"Result: {result}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
```

---

### Add New Data Source

**File:** `bot/connectors/new_source.py`

```python
class NewDataSource:
    """New data source connector"""

    def __init__(self, config: Config):
        self.api_key = config.new_source_api_key
        self.base_url = "https://api.newsource.com"

    def fetch_data(self, params: dict) -> dict:
        """Fetch data from new source"""
        response = httpx.get(
            f"{self.base_url}/endpoint",
            params=params,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0
        )
        return response.json()
```

Then integrate in strategy:
```python
# bot/application/extreme_value_strategy.py
from bot.connectors.new_source import NewDataSource

class ExtremeValueStrategy:
    def __init__(self, config, polymarket, weather):
        self.new_source = NewDataSource(config)

    def _check_yes_opportunity(self, market):
        # Use new data source
        extra_data = self.new_source.fetch_data({"market_id": market.market_id})
        # Incorporate into decision...
```

---

### Change Logging

**File:** `bot/utils/logger.py`

```python
def setup_logger(level: str = "INFO", log_dir: str = "logs"):
    """Setup structured logging"""
    logger = logging.getLogger("polymarket_bot")

    # Change log level
    logger.setLevel(getattr(logging, level.upper()))

    # Add new handler
    new_handler = logging.handlers.RotatingFileHandler(
        f"{log_dir}/new_log.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )

    # Change format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    new_handler.setFormatter(formatter)
    logger.addHandler(new_handler)
```

---

## Performance Optimization Checklist

✅ **Batch Price Fetching** - Use `batch_get_token_prices()` not individual calls
✅ **Rate Limiting** - 5 workers max, 50ms delay between requests
✅ **Caching** - Cache prices for 15 seconds to avoid redundant calls
✅ **Filtering First** - Filter weather markets before fetching prices
✅ **Async/Threading** - Use ThreadPoolExecutor for I/O-bound operations
✅ **Fallback Values** - Always have defaults (0.5 for price)
✅ **Silent Mode** - Suppress errors in batch operations

---

## Testing Checklist

Before going live:

1. ✅ Run `python bot.py config-check` - All green?
2. ✅ Run `python bot.py balance` - Shows correct USDC balance?
3. ✅ Run `python bot.py extreme-scan --limit 5` - Finds opportunities?
4. ✅ Run `python bot.py extreme-trade --dry-run --max-trades 3` - Executes without errors?
5. ✅ Check logs in `logs/` directory - No critical errors?
6. ✅ Verify `.env` file has all required fields
7. ✅ Test with small amounts first ($0.25-0.50)

---

## Emergency Contacts & Resources

**If something breaks:**
1. Check this document first (Common Issues section)
2. Check `SESSION_SUMMARY.md` for recent changes
3. Check git history: `git log --oneline`
4. Check logs: `tail -f logs/bot.log`

**External Resources:**
- Polymarket API docs: https://docs.polymarket.com
- py-clob-client: https://github.com/Polymarket/py-clob-client
- Web3.py docs: https://web3py.readthedocs.io
- Chainstack docs: https://docs.chainstack.com

**Key Files for Debugging:**
- `logs/bot.log` - Application logs
- `.env` - Configuration (check for typos!)
- `bot/connectors/polymarket.py` - Most common issues
- `bot/cli/cli.py` - UI errors

---

**END OF ARCHITECTURE MAP**

This document provides a complete map of the codebase for:
- Understanding how the bot works
- Debugging issues quickly
- Extending functionality
- Context preservation across sessions

**Last Updated:** January 14, 2026
**Version:** 1.0.0 - Fully Functional
