"""CLI interface for the Polymarket Weather Bot."""

import time
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from bot.application.trader import WeatherTrader
from bot.connectors.polymarket import PolymarketClient
from bot.connectors.weather import WeatherConnector
from bot.utils.config import Config, get_config
from bot.utils.logger import setup_logger, get_logger

app = typer.Typer(
    name="polymarket-weather-bot",
    help="Automated trading bot for Polymarket weather prediction markets",
    add_completion=False,
)

console = Console()


def get_trader() -> WeatherTrader:
    """Initialize and return trader instance."""
    config = get_config()

    # Validate config
    missing = config.validate_required_fields()
    if missing:
        console.print(f"[red]Error: Missing required configuration:[/red]")
        for field in missing:
            console.print(f"  - {field}")
        console.print("\n[yellow]Please set these in your .env file[/yellow]")
        raise typer.Exit(1)

    # Setup logger
    logger = setup_logger(level=config.log_level, log_dir=config.log_dir)

    # Initialize components
    polymarket = PolymarketClient(config)
    weather = WeatherConnector(config)
    trader = WeatherTrader(config, polymarket, weather)

    return trader


@app.command()
def status():
    """Show bot status and portfolio summary."""
    try:
        trader = get_trader()
        portfolio = trader.get_portfolio()

        # Create status panel
        status_table = Table(show_header=False, box=box.SIMPLE)
        status_table.add_column("Metric", style="cyan")
        status_table.add_column("Value", style="green")

        mode = "SIMULATION" if trader.config.simulation_mode else "LIVE"
        mode_color = "yellow" if trader.config.simulation_mode else "red"

        status_table.add_row("Trading Mode", f"[{mode_color}]{mode}[/{mode_color}]")
        status_table.add_row("Cash Balance", f"${portfolio.cash_balance:.2f}")
        status_table.add_row("Total Trades", str(portfolio.total_trades))
        status_table.add_row("Win Rate", f"{portfolio.win_rate:.1%}")
        status_table.add_row("Total P&L", f"${portfolio.total_pnl:.2f}")
        status_table.add_row("Open Positions", str(portfolio.open_positions))

        console.print(Panel(status_table, title="Portfolio Status", border_style="blue"))

        # Recent trades
        if trader.trades:
            trades_table = Table(title="Recent Trades", box=box.ROUNDED)
            trades_table.add_column("Time", style="dim")
            trades_table.add_column("Side", style="cyan")
            trades_table.add_column("Market", style="white")
            trades_table.add_column("Size", style="yellow")
            trades_table.add_column("Edge", style="green")

            for trade in trader.trades[-5:]:  # Last 5 trades
                trades_table.add_row(
                    trade.timestamp.strftime("%m/%d %H:%M"),
                    trade.side,
                    trade.question[:40] + "...",
                    f"${trade.size:.2f}",
                    f"{trade.edge:.1%}",
                )

            console.print(trades_table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def scan(
    limit: int = typer.Option(10, help="Max weather markets to show"),
    min_edge: float = typer.Option(0.05, help="Minimum edge to display"),
):
    """Scan markets and show potential trades without executing."""
    try:
        trader = get_trader()
        logger = get_logger()

        console.print("[cyan]Scanning Polymarket for weather markets...[/cyan]")

        # Fetch markets
        all_markets = trader.polymarket.get_all_markets()
        weather_markets = trader.polymarket.filter_weather_markets(all_markets)

        console.print(
            f"Found [green]{len(weather_markets)}[/green] weather markets out of {len(all_markets)} total"
        )

        if not weather_markets:
            console.print("[yellow]No weather markets found[/yellow]")
            return

        # Analyze markets
        signals = []
        with console.status("[bold green]Analyzing markets..."):
            for market in weather_markets:
                signal = trader.analyze_market(market)
                if signal and abs(signal.edge) >= min_edge:
                    signals.append(signal)

        # Sort by edge
        signals.sort(key=lambda s: abs(s.edge), reverse=True)

        # Display results
        if signals:
            table = Table(title=f"Top Trading Opportunities (Edge ≥ {min_edge:.0%})", box=box.ROUNDED)
            table.add_column("Market", style="white", width=50)
            table.add_column("Side", style="cyan")
            table.add_column("Price", style="yellow")
            table.add_column("Fair", style="magenta")
            table.add_column("Edge", style="green")
            table.add_column("Size", style="blue")

            for signal in signals[:limit]:
                edge_color = "green" if signal.edge > 0 else "red"
                table.add_row(
                    signal.market.question[:47] + "...",
                    signal.action.value,
                    f"{signal.market_probability:.1%}",
                    f"{signal.fair_probability:.1%}",
                    f"[{edge_color}]{signal.edge:+.1%}[/{edge_color}]",
                    f"${signal.size:.2f}",
                )

            console.print(table)
        else:
            console.print("[yellow]No opportunities found with sufficient edge[/yellow]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def trade_once(
    dry_run: bool = typer.Option(True, "--dry-run/--live", help="Simulate trades without executing"),
):
    """Run one trading cycle (scan, analyze, execute)."""
    try:
        trader = get_trader()

        # Override simulation mode if specified
        if not dry_run:
            trader.config.simulation_mode = False
            console.print("[red bold]⚠️  LIVE TRADING MODE - REAL FUNDS AT RISK[/red bold]")
            confirm = typer.confirm("Are you sure you want to execute live trades?")
            if not confirm:
                console.print("[yellow]Aborted[/yellow]")
                raise typer.Exit(0)
        else:
            trader.config.simulation_mode = True
            console.print("[yellow]Running in simulation mode[/yellow]")

        # Execute trading cycle
        with console.status("[bold green]Running trading cycle..."):
            results = trader.scan_and_trade()

        # Display results
        console.print("\n[bold cyan]Trading Cycle Complete[/bold cyan]")
        console.print(f"Markets scanned: {results['markets_scanned']}")
        console.print(f"Weather markets: {results['weather_markets']}")
        console.print(f"Signals generated: {results['signals_generated']}")
        console.print(f"Trades executed: [green]{results['trades_executed']}[/green]")

        if results["errors"]:
            console.print(f"\n[red]Errors encountered: {len(results['errors'])}[/red]")
            for error in results["errors"][:3]:  # Show first 3
                console.print(f"  - {error}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def run(
    interval: int = typer.Option(15, help="Minutes between trading cycles"),
    max_cycles: int = typer.Option(0, help="Max cycles to run (0 = infinite)"),
    dry_run: bool = typer.Option(True, "--dry-run/--live", help="Simulation mode"),
):
    """Run bot continuously with specified interval."""
    try:
        trader = get_trader()

        # Override simulation mode
        trader.config.simulation_mode = dry_run

        mode = "SIMULATION" if dry_run else "LIVE"
        mode_color = "yellow" if dry_run else "red"

        console.print(f"[{mode_color} bold]Starting bot in {mode} mode[/{mode_color} bold]")
        console.print(f"Interval: {interval} minutes")
        console.print(f"Max cycles: {max_cycles if max_cycles > 0 else 'Unlimited'}")
        console.print("\n[dim]Press Ctrl+C to stop[/dim]\n")

        if not dry_run:
            confirm = typer.confirm("⚠️  You are about to run LIVE trading. Continue?")
            if not confirm:
                raise typer.Exit(0)

        cycle_count = 0
        while True:
            cycle_count += 1
            console.print(f"\n[bold cyan]--- Cycle {cycle_count} at {datetime.now().strftime('%H:%M:%S')} ---[/bold cyan]")

            try:
                results = trader.scan_and_trade()
                console.print(
                    f"✓ Scanned {results['weather_markets']} weather markets, "
                    f"executed {results['trades_executed']} trades"
                )

            except Exception as e:
                console.print(f"[red]Cycle error: {e}[/red]")

            # Check if should stop
            if max_cycles > 0 and cycle_count >= max_cycles:
                console.print(f"\n[green]Completed {cycle_count} cycles. Stopping.[/green]")
                break

            # Sleep until next cycle
            console.print(f"[dim]Next cycle in {interval} minutes...[/dim]")
            time.sleep(interval * 60)

    except KeyboardInterrupt:
        console.print("\n[yellow]Bot stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Fatal error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def balance():
    """Check USDC balance."""
    try:
        config = get_config()
        polymarket = PolymarketClient(config)

        balance = polymarket.get_usdc_balance()
        console.print(f"\n[green]USDC Balance:[/green] ${balance:.2f}\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def config_check():
    """Verify configuration and connections."""
    try:
        config = get_config()

        table = Table(title="Configuration Check", box=box.ROUNDED)
        table.add_column("Setting", style="cyan")
        table.add_column("Status", style="white")

        # Check required fields
        missing = config.validate_required_fields()
        if missing:
            table.add_row(
                "Required Fields",
                f"[red]Missing: {', '.join(missing)}[/red]",
            )
        else:
            table.add_row("Required Fields", "[green]✓ All set[/green]")

        # Check connections
        try:
            polymarket = PolymarketClient(config)
            table.add_row("Chainstack Connection", "[green]✓ Connected[/green]")
        except Exception as e:
            table.add_row("Chainstack Connection", f"[red]✗ Failed: {e}[/red]")

        # Check weather API
        try:
            weather = WeatherConnector(config)
            test_forecast = weather.get_forecast("New York", datetime.now(), use_ensemble=False)
            if test_forecast:
                table.add_row("Weather API", "[green]✓ Working[/green]")
            else:
                table.add_row("Weather API", "[yellow]⚠ No data returned[/yellow]")
        except Exception as e:
            table.add_row("Weather API", f"[red]✗ Failed: {e}[/red]")

        # Mode
        mode = "SIMULATION" if config.simulation_mode else "LIVE"
        mode_color = "yellow" if config.simulation_mode else "red"
        table.add_row("Trading Mode", f"[{mode_color}]{mode}[/{mode_color}]")

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    console.print("\n[bold cyan]Polymarket Weather Bot[/bold cyan]")
    console.print("Version: [green]1.0.0[/green]")
    console.print("Author: [blue]@idlepraxis[/blue]")
    console.print()


if __name__ == "__main__":
    app()
