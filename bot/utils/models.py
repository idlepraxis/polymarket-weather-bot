"""Pydantic models for type-safe data handling."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TradeSide(str, Enum):
    """Trade side enum."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enum."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"
    FOK = "FOK"  # Fill or Kill
    GTC = "GTC"  # Good till cancel


class MarketStatus(str, Enum):
    """Market status enum."""

    ACTIVE = "active"
    CLOSED = "closed"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class WeatherMarket(BaseModel):
    """Weather prediction market data."""

    market_id: str = Field(..., description="Unique market ID")
    condition_id: str = Field(..., description="Condition ID for the market")
    question: str = Field(..., description="Market question")
    description: Optional[str] = Field(None, description="Market description")

    # Tokens
    yes_token_id: str = Field(..., description="Yes outcome token ID")
    no_token_id: str = Field(..., description="No outcome token ID")

    # Pricing
    yes_price: float = Field(..., ge=0.0, le=1.0, description="Current Yes price")
    no_price: float = Field(..., ge=0.0, le=1.0, description="Current No price")
    spread: float = Field(0.0, description="Bid-ask spread")

    # Market metadata
    status: MarketStatus = Field(MarketStatus.ACTIVE, description="Market status")
    end_date: datetime = Field(..., description="Market resolution date")
    liquidity: float = Field(0.0, description="Market liquidity in USDC")
    volume: float = Field(0.0, description="Total volume traded")

    # Weather-specific
    location: Optional[str] = Field(None, description="City/location for weather")
    temperature_threshold: Optional[float] = Field(None, description="Temp threshold in question")
    weather_type: Optional[str] = Field(None, description="Weather event type")

    # URLs
    market_url: Optional[str] = Field(None, description="Polymarket URL")

    class Config:
        use_enum_values = True


class WeatherForecast(BaseModel):
    """Weather forecast data."""

    location: str = Field(..., description="Location name")
    date: datetime = Field(..., description="Forecast date")

    # Temperature data
    temp_high_f: Optional[float] = Field(None, description="High temp in Fahrenheit")
    temp_low_f: Optional[float] = Field(None, description="Low temp in Fahrenheit")
    temp_high_c: Optional[float] = Field(None, description="High temp in Celsius")
    temp_low_c: Optional[float] = Field(None, description="Low temp in Celsius")

    # Probabilities
    prob_precipitation: Optional[float] = Field(None, ge=0.0, le=1.0)
    prob_snow: Optional[float] = Field(None, ge=0.0, le=1.0)
    prob_thunderstorm: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Conditions
    conditions: Optional[str] = Field(None, description="Weather conditions")
    humidity: Optional[float] = Field(None, description="Humidity %")
    wind_speed: Optional[float] = Field(None, description="Wind speed mph")

    # Metadata
    source: str = Field(..., description="Data source (e.g., OpenWeather)")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Forecast confidence")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TradeSignal(BaseModel):
    """Trading signal with analysis."""

    market: WeatherMarket = Field(..., description="Target market")
    forecast: Optional[WeatherForecast] = Field(None, description="Weather forecast (optional for extreme value strategy)")

    # Analysis
    fair_probability: float = Field(..., ge=0.0, le=1.0, description="Computed fair probability")
    market_probability: float = Field(..., ge=0.0, le=1.0, description="Market implied probability")
    edge: float = Field(..., description="Edge = fair_prob - market_prob")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Signal confidence")

    # Trade recommendation
    action: TradeSide = Field(..., description="Recommended action")
    token_id: str = Field(..., description="Token to trade")
    price: float = Field(..., ge=0.0, le=1.0, description="Target price")
    size: float = Field(..., gt=0.0, description="Position size in USDC")

    # Reasoning
    reasoning: str = Field(..., description="Why this trade makes sense")

    class Config:
        use_enum_values = True


class Trade(BaseModel):
    """Executed trade record."""

    trade_id: str = Field(..., description="Unique trade ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Market info
    market_id: str
    question: str
    token_id: str

    # Trade details
    side: TradeSide
    price: float = Field(..., ge=0.0, le=1.0)
    size: float = Field(..., gt=0.0)
    cost: float = Field(..., description="Total cost in USDC")

    # Status
    simulation: bool = Field(False, description="Was this a simulated trade?")
    tx_hash: Optional[str] = Field(None, description="Transaction hash")
    status: str = Field("pending", description="Trade status")

    # Analysis
    fair_probability: float
    edge: float
    reasoning: str

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class Position(BaseModel):
    """Open position tracking."""

    position_id: str = Field(..., description="Unique position ID")
    market_id: str
    question: str
    token_id: str

    # Entry
    entry_price: float = Field(..., ge=0.0, le=1.0)
    quantity: float = Field(..., gt=0.0, description="Number of shares")
    cost_basis: float = Field(..., description="Total cost in USDC")
    entry_time: datetime

    # Current
    current_price: float = Field(..., ge=0.0, le=1.0)
    current_value: float = Field(..., description="Current value in USDC")
    unrealized_pnl: float = Field(..., description="Unrealized P&L")

    # Status
    is_open: bool = Field(True)
    close_price: Optional[float] = Field(None)
    close_time: Optional[datetime] = Field(None)
    realized_pnl: Optional[float] = Field(None)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class Portfolio(BaseModel):
    """Portfolio summary."""

    total_value: float = Field(..., description="Total portfolio value in USDC")
    cash_balance: float = Field(..., description="Available USDC")
    invested: float = Field(..., description="Value in open positions")

    # Performance
    total_pnl: float = Field(0.0, description="Total realized + unrealized P&L")
    realized_pnl: float = Field(0.0, description="Realized P&L")
    unrealized_pnl: float = Field(0.0, description="Unrealized P&L")

    # Statistics
    total_trades: int = Field(0)
    winning_trades: int = Field(0)
    losing_trades: int = Field(0)
    win_rate: float = Field(0.0, ge=0.0, le=1.0)

    # Risk
    open_positions: int = Field(0)
    max_position_size: float = Field(0.0)
    total_exposure: float = Field(0.0)

    # Timestamp
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class BotStatus(BaseModel):
    """Bot runtime status."""

    is_running: bool = Field(False)
    simulation_mode: bool = Field(True)

    # Runtime stats
    start_time: Optional[datetime] = Field(None)
    last_scan_time: Optional[datetime] = Field(None)
    total_scans: int = Field(0)

    # Trading stats
    trades_today: int = Field(0)
    last_trade_time: Optional[datetime] = Field(None)

    # Errors
    error_count: int = Field(0)
    last_error: Optional[str] = Field(None)
    last_error_time: Optional[datetime] = Field(None)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
