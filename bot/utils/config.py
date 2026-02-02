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

    # Blockchain & Wallet (Polymarket)
    polygon_wallet_private_key: Optional[str] = Field(None, alias="POLYGON_WALLET_PRIVATE_KEY")
    wallet_address: Optional[str] = Field(None, alias="WALLET_ADDRESS")

    # Chainstack Configuration (Polymarket)
    chainstack_rpc_url: Optional[str] = Field(None, alias="CHAINSTACK_RPC_URL")
    chainstack_ws_url: Optional[str] = Field(None, alias="CHAINSTACK_WS_URL")

    # Polymarket CLOB API (optional)
    clob_api_key: Optional[str] = Field(None, alias="CLOB_API_KEY")
    clob_secret: Optional[str] = Field(None, alias="CLOB_SECRET")
    clob_pass_phrase: Optional[str] = Field(None, alias="CLOB_PASS_PHRASE")

    # Weather APIs (optional - only needed for forecast-based strategy)
    openweather_api_key: Optional[str] = Field(None, alias="OPENWEATHER_API_KEY")
    weatherapi_key: Optional[str] = Field(None, alias="WEATHERAPI_KEY")
    noaa_api_key: Optional[str] = Field(None, alias="NOAA_API_KEY")

    # Telegram Bot
    telegram_bot_token: Optional[str] = Field(None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(None, alias="TELEGRAM_CHAT_ID")

    # Trading Parameters
    max_position_size_usdc: float = Field(5.0, alias="MAX_POSITION_SIZE_USDC")
    min_edge_threshold: float = Field(0.10, alias="MIN_EDGE_THRESHOLD")  # 10% min edge (was 5%)
    min_confidence: float = Field(0.70, alias="MIN_CONFIDENCE")
    max_daily_trades: int = Field(25, alias="MAX_DAILY_TRADES")  # Reduced from 50
    max_open_positions: int = Field(15, alias="MAX_OPEN_POSITIONS")  # Reduced from 20

    # Extreme Value Strategy Parameters
    extreme_yes_max_price: float = Field(0.12, alias="EXTREME_YES_MAX_PRICE")  # Tighter: was 0.15
    extreme_yes_min_price: float = Field(0.03, alias="EXTREME_YES_MIN_PRICE")  # v2.5.0: Skip sub-3¢ traps (0% win rate)
    extreme_yes_ideal_price: float = Field(0.08, alias="EXTREME_YES_IDEAL_PRICE")  # Tighter: was 0.10
    extreme_no_min_yes_price: float = Field(0.50, alias="EXTREME_NO_MIN_YES_PRICE")  # Stricter: was 0.40
    extreme_no_ideal_yes_price: float = Field(0.60, alias="EXTREME_NO_IDEAL_YES_PRICE")  # Stricter: was 0.50
    extreme_no_min_price: float = Field(0.03, alias="EXTREME_NO_MIN_PRICE")  # v2.5.1: Skip sub-3¢ NO traps (same as YES)
    # Position sizing - larger positions since fewer trades (~$2.50 average)
    extreme_min_position: float = Field(1.50, alias="EXTREME_MIN_POSITION")  # Was 0.50
    extreme_max_position: float = Field(2.50, alias="EXTREME_MAX_POSITION")  # Was 1.00
    extreme_aggressive_max: float = Field(5.00, alias="EXTREME_AGGRESSIVE_MAX")  # Was 1.50
    # Trade type preferences (v2.5.0)
    prefer_no_on_range: bool = Field(True, alias="PREFER_NO_ON_RANGE")  # NO/RANGE has 18.2% win rate vs 4% YES
    skip_yes_on_threshold: bool = Field(False, alias="SKIP_YES_ON_THRESHOLD")  # Optionally skip YES threshold bets

    # Risk Management
    bankroll_usdc: float = Field(1000.0, alias="BANKROLL_USDC")
    position_size_pct: float = Field(0.01, alias="POSITION_SIZE_PCT")
    stop_loss_pct: float = Field(0.50, alias="STOP_LOSS_PCT")

    # Bot Runner Configuration
    bankroll: float = Field(1000.0, alias="BANKROLL")
    scan_interval_hours: int = Field(4, alias="SCAN_INTERVAL_HOURS")  # More frequent scans
    max_trades_per_scan: int = Field(10, alias="MAX_TRADES_PER_SCAN")  # Reduced from 20
    max_trades_per_day: int = Field(25, alias="MAX_TRADES_PER_DAY")  # Reduced from 50
    max_trades_per_city: int = Field(2, alias="MAX_TRADES_PER_CITY")  # Reduced from 3
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
    enable_ensemble_models: bool = Field(False, alias="ENABLE_ENSEMBLE_MODELS")  # v2.5.0: NWS-only by default (Kalshi uses NWS)
    prefer_nws_only: bool = Field(True, alias="PREFER_NWS_ONLY")  # v2.5.0: Use NWS exclusively when available

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

        # Polymarket requires wallet and RPC
        if not self.polygon_wallet_private_key:
            missing.append("POLYGON_WALLET_PRIVATE_KEY")
        if not self.chainstack_rpc_url:
            missing.append("CHAINSTACK_RPC_URL")

        return missing


# Global config instance
config = Config()


# Convenience function
def get_config() -> Config:
    """Get the global config instance."""
    return config
