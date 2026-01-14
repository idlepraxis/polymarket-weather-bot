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
from bot.application.extreme_value_strategy import ExtremeValueStrategy
from bot.connectors.polymarket import PolymarketClient
from bot.connectors.kalshi import KalshiClient
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
                    signal.action,
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
def balance(
    platform: str = typer.Option("polymarket", help="Platform: polymarket or kalshi"),
):
    """Check balance on specified platform."""
    try:
        config = get_config()

        if platform.lower() == "kalshi":
            client = KalshiClient(config)
            balance = client.get_balance()
            console.print(f"\n[green]Kalshi Balance:[/green] ${balance:.2f}\n")
        else:
            client = PolymarketClient(config)
            balance = client.get_usdc_balance()
            console.print(f"\n[green]Polymarket USDC Balance:[/green] ${balance:.2f}\n")

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
def extreme_scan(
    limit: int = typer.Option(20, help="Max opportunities to show"),
    yes_max: float = typer.Option(0.15, help="Max YES price to buy"),
    no_min_yes: float = typer.Option(0.40, help="Min YES price to buy NO"),
    platform: str = typer.Option("polymarket", help="Platform: polymarket or kalshi"),
):
    """Scan for EXTREME VALUE opportunities (mispriced shares).

    This implements the successful trader strategy:
    - Buy YES shares ONLY when < 10-15¢
    - Buy NO shares ONLY when YES > 40-50¢
    - Small positions, high volume, asymmetric payoffs
    """
    try:
        config = get_config()
        weather = WeatherConnector(config)

        # Initialize the appropriate client based on platform
        if platform.lower() == "kalshi":
            client = KalshiClient(config)
            platform_name = "Kalshi"
        else:  # Default to Polymarket
            client = PolymarketClient(config)
            platform_name = "Polymarket"

        # Override config with CLI params
        config.extreme_yes_max_price = yes_max
        config.extreme_no_min_yes_price = no_min_yes

        strategy = ExtremeValueStrategy(config, client, weather)

        console.print(f"[cyan]Scanning {platform_name} for EXTREME VALUE opportunities...[/cyan]")
        console.print(f"Rules: YES < {yes_max:.0%}, NO when YES > {no_min_yes:.0%}\n")

        # Fetch markets
        with console.status(f"[bold green]Fetching {platform_name} markets..."):
            # For Kalshi, use direct weather series fetching (much faster)
            # For Polymarket, fetch all and filter (already optimized)
            if platform.lower() == "kalshi":
                all_markets = client.get_weather_markets_direct(limit=200)
                weather_markets = client.filter_weather_markets(all_markets)
            else:
                all_markets = client.get_all_markets()
                weather_markets = client.filter_weather_markets(all_markets)

        console.print(f"Found {len(weather_markets)} weather markets")

        if not weather_markets:
            console.print("[yellow]No weather markets found[/yellow]")
            return

        # Find opportunities
        with console.status("[bold green]Analyzing for extreme values..."):
            signals = strategy.scan_for_opportunities(weather_markets)

            # Filter by time and liquidity
            signals = strategy.filter_by_time_to_resolution(signals)
            signals = strategy.filter_by_liquidity(signals)

        if signals:
            table = Table(
                title=f"🎯 EXTREME VALUE Opportunities (Top {limit})",
                box=box.HEAVY_HEAD
            )
            table.add_column("Market", style="white", width=45)
            table.add_column("Side", style="cyan", justify="center")
            table.add_column("Price", style="yellow", justify="right")
            table.add_column("Size", style="blue", justify="right")
            table.add_column("EV", style="green", justify="right")
            table.add_column("Payoff", style="magenta", justify="right")

            for signal in signals[:limit]:
                ev = strategy._calculate_ev(signal)
                payoff_ratio = (1 - signal.price) / signal.price

                side_icon = "📈 YES" if signal.action == "BUY" else "📉 NO"

                table.add_row(
                    signal.market.question[:42] + "...",
                    side_icon,
                    f"{signal.price:.1%}",
                    f"${signal.size:.2f}",
                    f"${ev:+.2f}",
                    f"{payoff_ratio:.1f}x",
                )

            console.print(table)
            console.print(f"\n[green]Found {len(signals)} extreme value opportunities[/green]")

            # Summary stats
            total_ev = sum(strategy._calculate_ev(s) for s in signals[:limit])
            total_risk = sum(s.size * s.price for s in signals[:limit])

            console.print(f"Total EV if all {limit} trades hit: ${total_ev:.2f}")
            console.print(f"Total capital at risk: ${total_risk:.2f}")
            console.print(f"EV/Risk ratio: {total_ev/total_risk:.1%}" if total_risk > 0 else "")

        else:
            console.print("[yellow]No extreme value opportunities found[/yellow]")
            console.print("[dim]Try relaxing thresholds: --yes-max 0.20 --no-min-yes 0.35[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def extreme_trade(
    dry_run: bool = typer.Option(True, "--dry-run/--live", help="Simulate trades"),
    yes_max: float = typer.Option(0.15, help="Max YES price"),
    no_min_yes: float = typer.Option(0.40, help="Min YES price for NO"),
    max_trades: int = typer.Option(10, help="Max trades to execute"),
    platform: str = typer.Option("polymarket", help="Platform: polymarket or kalshi"),
):
    """Execute EXTREME VALUE trades (mispriced shares).

    This is the high-ROI strategy that has generated $25k+ profits.
    """
    try:
        config = get_config()
        weather = WeatherConnector(config)

        # Initialize the appropriate client based on platform
        if platform.lower() == "kalshi":
            client = KalshiClient(config)
            platform_name = "Kalshi"
        else:  # Default to Polymarket
            client = PolymarketClient(config)
            platform_name = "Polymarket"

        # Override settings
        config.extreme_yes_max_price = yes_max
        config.extreme_no_min_yes_price = no_min_yes
        config.simulation_mode = dry_run

        strategy = ExtremeValueStrategy(config, client, weather)

        mode = "SIMULATION" if dry_run else "LIVE"
        mode_color = "yellow" if dry_run else "red"

        console.print(f"[{mode_color} bold]EXTREME VALUE Trading on {platform_name} - {mode} Mode[/{mode_color} bold]")

        if not dry_run:
            confirm = typer.confirm("⚠️  Execute LIVE trades with real funds?")
            if not confirm:
                raise typer.Exit(0)

        # Scan for opportunities
        with console.status(f"[bold green]Fetching {platform_name} markets..."):
            if platform.lower() == "kalshi":
                all_markets = client.get_weather_markets_direct(limit=200)
                weather_markets = client.filter_weather_markets(all_markets)
            else:
                all_markets = client.get_all_markets()
                weather_markets = client.filter_weather_markets(all_markets)

        signals = strategy.scan_for_opportunities(weather_markets)
        signals = strategy.filter_by_time_to_resolution(signals)
        signals = strategy.filter_by_liquidity(signals)

        if not signals:
            console.print("[yellow]No opportunities found[/yellow]")
            return

        console.print(f"Found {len(signals)} opportunities, executing top {max_trades}...")

        executed = 0
        for signal in signals[:max_trades]:
            try:
                # Execute trade based on platform
                if platform.lower() == "kalshi":
                    # Kalshi uses ticker, side, count, and price in cents
                    ticker = signal.market.market_id  # ticker stored in market_id
                    side = "yes" if signal.action == "BUY" else "no"
                    price_cents = int(signal.price * 100)  # Convert 0-1 to cents
                    count = int(signal.size / signal.price)  # Number of contracts

                    order_id = client.execute_limit_order(
                        ticker=ticker,
                        side=side,
                        count=count,
                        price=price_cents,
                        simulation=dry_run,
                    )
                else:
                    # Polymarket uses token_id and USDC amount
                    order_id = client.execute_market_order(
                        token_id=signal.token_id,
                        amount=signal.size,
                        simulation=dry_run,
                    )

                executed += 1

                console.print(
                    f"[green]✓[/green] {signal.action} {signal.size:.2f} USDC @ {signal.price:.1%} "
                    f"- {signal.market.question[:40]}..."
                )

                time.sleep(1)  # Rate limiting

            except Exception as e:
                console.print(f"[red]✗ Failed:[/red] {e}")

        console.print(f"\n[green]Executed {executed}/{max_trades} trades[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    console.print("\n[bold cyan]Polymarket Weather Bot[/bold cyan]")
    console.print("Version: [green]1.0.0[/green]")
    console.print("Author: [blue]@idlepraxis[/blue]")
    console.print("Strategies: [yellow]Forecast Arbitrage + Extreme Value Betting[/yellow]")
    console.print()


if __name__ == "__main__":
    app()
