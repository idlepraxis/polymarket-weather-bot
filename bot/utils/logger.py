"""Logging utilities for the bot."""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_logger(
    name: str = "polymarket_weather_bot",
    level: str = "INFO",
    log_dir: Optional[str] = None,
) -> logging.Logger:
    """Set up structured logging with both file and console handlers.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Console handler with Rich formatting
    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
    )
    console_handler.setLevel(getattr(logging, level.upper()))
    console_formatter = logging.Formatter("%(message)s", datefmt="[%X]")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler if log directory specified
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Main log file
        file_handler = logging.FileHandler(log_path / "bot.log")
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Separate error log
        error_handler = logging.FileHandler(log_path / "errors.log")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)

    return logger


def log_trade(logger: logging.Logger, trade_data: dict, simulation: bool = False):
    """Log a trade with structured formatting."""
    mode = "[yellow]SIMULATION[/yellow]" if simulation else "[green]LIVE[/green]"

    logger.info(
        f"{mode} Trade: {trade_data['side']} {trade_data['size']} shares @ "
        f"${trade_data['price']:.3f} | Edge: {trade_data.get('edge', 0):.2%} | "
        f"Market: {trade_data['question']}"
    )


def log_scan_results(logger: logging.Logger, total_markets: int, weather_markets: int):
    """Log market scanning results."""
    logger.info(
        f"Scanned {total_markets} markets, found {weather_markets} weather markets"
    )


def log_error(logger: logging.Logger, error: Exception, context: str = ""):
    """Log an error with context."""
    logger.error(f"Error in {context}: {str(error)}", exc_info=True)


# Global logger instance
_global_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """Get the global logger instance with file logging enabled."""
    global _global_logger
    if _global_logger is None:
        _global_logger = setup_logger(log_dir="logs")
    return _global_logger
