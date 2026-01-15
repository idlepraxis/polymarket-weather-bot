"""Configuration management for the Polymarket Weather Bot."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load environment variables
load_dotenv()


class Config(BaseSettings):
    """Bot configuration from environment variables."""

    # Blockchain & Wallet
    polygon_wallet_private_key: str = Field(..., alias="POLYGON_WALLET_PRIVATE_KEY")
    wallet_address: Optional[str] = Field(None, alias="WALLET_ADDRESS")

    # Chainstack Configuration
    chainstack_rpc_url: str = Field(..., alias="CHAINSTACK_RPC_URL")
    chainstack_ws_url: str = Field(..., alias="CHAINSTACK_WS_URL")

    # Polymarket API
    clob_api_key: Optional[str] = Field(None, alias="CLOB_API_KEY")
    clob_secret: Optional[str] = Field(None, alias="CLOB_SECRET")
    clob_pass_phrase: Optional[str] = Field(None, alias="CLOB_PASS_PHRASE")

    # Weather APIs
    openweather_api_key: str = Field(..., alias="OPENWEATHER_API_KEY")
    weatherapi_key: Optional[str] = Field(None, alias="WEATHERAPI_KEY")
    noaa_api_key: Optional[str] = Field(None, alias="NOAA_API_KEY")

    # Telegram Bot
    telegram_bot_token: Optional[str] = Field(None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(None, alias="TELEGRAM_CHAT_ID")

    # Kalshi API (supports both API key and email/password)
    kalshi_api_key_id: Optional[str] = Field(None, alias="KALSHI_API_KEY_ID")
    kalshi_api_private_key: Optional[str] = Field(None, alias="KALSHI_API_PRIVATE_KEY")
    kalshi_email: Optional[str] = Field(None, alias="KALSHI_EMAIL")
    kalshi_password: Optional[str] = Field(None, alias="KALSHI_PASSWORD")
    kalshi_use_demo: bool = Field(False, alias="KALSHI_USE_DEMO")

    # Trading Parameters
    max_position_size_usdc: float = Field(5.0, alias="MAX_POSITION_SIZE_USDC")
    min_edge_threshold: float = Field(0.05, alias="MIN_EDGE_THRESHOLD")
    min_confidence: float = Field(0.70, alias="MIN_CONFIDENCE")
    max_daily_trades: int = Field(50, alias="MAX_DAILY_TRADES")
    max_open_positions: int = Field(20, alias="MAX_OPEN_POSITIONS")

    # Extreme Value Strategy Parameters
    extreme_yes_max_price: float = Field(0.15, alias="EXTREME_YES_MAX_PRICE")
    extreme_yes_ideal_price: float = Field(0.10, alias="EXTREME_YES_IDEAL_PRICE")
    extreme_no_min_yes_price: float = Field(0.40, alias="EXTREME_NO_MIN_YES_PRICE")
    extreme_no_ideal_yes_price: float = Field(0.50, alias="EXTREME_NO_IDEAL_YES_PRICE")
    extreme_min_position: float = Field(0.50, alias="EXTREME_MIN_POSITION")
    extreme_max_position: float = Field(1.00, alias="EXTREME_MAX_POSITION")
    extreme_aggressive_max: float = Field(5.00, alias="EXTREME_AGGRESSIVE_MAX")

    # Risk Management
    bankroll_usdc: float = Field(1000.0, alias="BANKROLL_USDC")
    position_size_pct: float = Field(0.01, alias="POSITION_SIZE_PCT")
    stop_loss_pct: float = Field(0.50, alias="STOP_LOSS_PCT")

    # Bot Runner Configuration
    bankroll: float = Field(1000.0, alias="BANKROLL")
    scan_interval_hours: int = Field(6, alias="SCAN_INTERVAL_HOURS")
    max_trades_per_scan: int = Field(20, alias="MAX_TRADES_PER_SCAN")
    max_trades_per_day: int = Field(50, alias="MAX_TRADES_PER_DAY")
    max_trades_per_city: int = Field(3, alias="MAX_TRADES_PER_CITY")
    max_daily_exposure_pct: float = Field(5.0, alias="MAX_DAILY_EXPOSURE_PCT")
    resolution_check_hours: int = Field(1, alias="RESOLUTION_CHECK_HOURS")

    # Bot Behavior
    poll_interval_minutes: int = Field(15, alias="POLL_INTERVAL_MINUTES")
    simulation_mode: bool = Field(True, alias="SIMULATION_MODE")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # Data Storage
    cache_dir: str = Field("./data/cache", alias="CACHE_DIR")
    weather_db_dir: str = Field("./data/weather_db", alias="WEATHER_DB_DIR")
    log_dir: str = Field("./logs", alias="LOG_DIR")

    # Optional: Advanced Features
    enable_ml_forecasts: bool = Field(False, alias="ENABLE_ML_FORECASTS")
    enable_ensemble_models: bool = Field(True, alias="ENABLE_ENSEMBLE_MODELS")

    # Polymarket Constants
    clob_url: str = "https://clob.polymarket.com"
    gamma_api_url: str = "https://gamma-api.polymarket.com"
    chain_id: int = 137  # Polygon mainnet

    # Contract Addresses (Polygon)
    neg_risk_exchange_address: str = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
    ctf_exchange_address: str = "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"
    usdc_address: str = "0x3c499c542cEF5E3811e1192ce70d8cc03d5c3359"  # USDC (new)
    ctf_address: str = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        populate_by_name = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create necessary directories
        self._ensure_directories()

    def _ensure_directories(self):
        """Create necessary directories if they don't exist."""
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.weather_db_dir).mkdir(parents=True, exist_ok=True)
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.simulation_mode

    def validate_required_fields(self) -> list[str]:
        """Validate required configuration fields and return missing ones."""
        missing = []

        if not self.polygon_wallet_private_key:
            missing.append("POLYGON_WALLET_PRIVATE_KEY")
        if not self.chainstack_rpc_url:
            missing.append("CHAINSTACK_RPC_URL")
        if not self.chainstack_ws_url:
            missing.append("CHAINSTACK_WS_URL")
        if not self.openweather_api_key:
            missing.append("OPENWEATHER_API_KEY")

        return missing


# Global config instance
config = Config()


# Convenience function
def get_config() -> Config:
    """Get the global config instance."""
    return config
