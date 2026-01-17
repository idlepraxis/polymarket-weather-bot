"""CLI interface for the Polymarket Weather Bot."""

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from bot.application.trader import WeatherTrader
from bot.application.extreme_value_strategy import ExtremeValueStrategy
from bot.application.bot_runner import BotRunner
from bot.connectors.polymarket import PolymarketClient
from bot.connectors.kalshi import KalshiClient
from bot.connectors.weather import WeatherConnector
from bot.database.trade_history import TradeHistoryDB
from bot.utils.config import Config, get_config
from bot.utils.logger import setup_logger, get_logger
from bot.utils.models import Trade, TradeSide

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

        # Initialize trade history database
        trade_db = TradeHistoryDB()

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

                # Create Trade object and log to database
                trade = Trade(
                    trade_id=order_id or str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    market_id=signal.market.market_id,
                    question=signal.market.question,
                    token_id=signal.token_id,
                    side=TradeSide.BUY,  # Both platforms are buying in this strategy
                    price=signal.price,
                    size=signal.size,
                    cost=signal.size * signal.price,
                    simulation=dry_run,
                    tx_hash=order_id,
                    status="executed",
                    fair_probability=signal.fair_probability,
                    edge=signal.edge,
                    reasoning=signal.reasoning
                )

                trade_db.log_trade(trade, platform=platform)

                # Display action properly for each platform
                if platform.lower() == "kalshi":
                    # Kalshi: show "BUY YES" or "BUY NO"
                    action_display = f"BUY {side.upper()}"
                else:
                    # Polymarket: show "BUY" or "SELL"
                    action_display = signal.action

                console.print(
                    f"[green]✓[/green] {action_display} {signal.size:.2f} USDC @ {signal.price:.1%} "
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


@app.command()
def pnl(
    simulation: bool = typer.Option(False, "--simulation", help="Show simulation trades P&L"),
    platform: Optional[str] = typer.Option(None, "--platform", help="Filter by platform (polymarket, kalshi)"),
):
    """View profit & loss summary."""
    try:
        trade_db = TradeHistoryDB()
        stats = trade_db.get_pnl_summary(simulation=simulation, platform=platform)

        mode = "SIMULATION" if simulation else "LIVE"
        mode_color = "yellow" if simulation else "green"
        platform_text = f" ({platform.upper()})" if platform else " (ALL PLATFORMS)"

        console.print(f"\n[{mode_color} bold]{mode} Trading P&L{platform_text}[/{mode_color} bold]\n")

        # Create summary table
        table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Total Trades", str(stats['total_trades']))
        table.add_row("Winning Trades", f"[green]{stats['winning_trades']}[/green]")
        table.add_row("Losing Trades", f"[red]{stats['losing_trades']}[/red]")
        table.add_row("Win Rate", f"{stats['win_rate']:.1f}%")
        table.add_row("", "")  # Spacer

        # P&L metrics
        pnl_color = "green" if stats['realized_pnl'] >= 0 else "red"
        roi_color = "green" if stats['roi'] >= 0 else "red"

        table.add_row("Realized P&L", f"[{pnl_color}]${stats['realized_pnl']:.2f}[/{pnl_color}]")
        table.add_row("Total Invested", f"${stats['total_invested']:.2f}")
        table.add_row("ROI", f"[{roi_color}]{stats['roi']:.1f}%[/{roi_color}]")
        table.add_row("", "")  # Spacer

        # Trade metrics
        avg_color = "green" if stats['avg_pnl_per_trade'] >= 0 else "red"
        best_color = "green" if stats['best_trade'] >= 0 else "red"
        worst_color = "green" if stats['worst_trade'] >= 0 else "red"

        table.add_row("Avg P&L per Trade", f"[{avg_color}]${stats['avg_pnl_per_trade']:.2f}[/{avg_color}]")
        table.add_row("Best Trade", f"[{best_color}]${stats['best_trade']:.2f}[/{best_color}]")
        table.add_row("Worst Trade", f"[{worst_color}]${stats['worst_trade']:.2f}[/{worst_color}]")
        table.add_row("", "")  # Spacer

        # Strategy metrics
        table.add_row("Avg Entry Price", f"{stats['avg_entry_price']:.1%}")
        table.add_row("Avg Edge", f"{stats['avg_edge']:.1%}")

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def trades(
    simulation: bool = typer.Option(False, "--simulation", help="Show simulation trades"),
    platform: Optional[str] = typer.Option(None, "--platform", help="Filter by platform"),
    limit: int = typer.Option(20, help="Number of trades to show"),
):
    """View recent trades."""
    try:
        trade_db = TradeHistoryDB()
        trade_list = trade_db.get_trades(simulation=simulation, platform=platform, limit=limit)

        if not trade_list:
            console.print("[yellow]No trades found[/yellow]")
            return

        mode = "SIMULATION" if simulation else "LIVE"
        mode_color = "yellow" if simulation else "green"

        console.print(f"\n[{mode_color} bold]Recent {mode} Trades[/{mode_color} bold]\n")

        # Create trades table
        table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        table.add_column("Date", style="cyan")
        table.add_column("Platform", style="magenta")
        table.add_column("Side", style="yellow")
        table.add_column("Price", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("Question", style="dim", max_width=40)

        for trade in trade_list:
            timestamp = datetime.fromisoformat(trade['timestamp'])
            date_str = timestamp.strftime("%m/%d %H:%M")

            # P&L display
            if trade['resolved']:
                pnl = trade['pnl']
                pnl_color = "green" if pnl >= 0 else "red"
                pnl_str = f"[{pnl_color}]${pnl:.2f}[/{pnl_color}]"
            else:
                pnl_str = "[dim]pending[/dim]"

            table.add_row(
                date_str,
                trade['platform'].upper(),
                trade['side'],
                f"{trade['price']:.1%}",
                f"${trade['size']:.2f}",
                f"${trade['cost']:.2f}",
                pnl_str,
                trade['question'][:37] + "..." if len(trade['question']) > 40 else trade['question']
            )

        console.print(table)
        console.print(f"\nShowing {len(trade_list)} most recent trades")
        console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def stats(
    simulation: bool = typer.Option(False, "--simulation", help="Show simulation stats"),
):
    """View statistics by platform."""
    try:
        trade_db = TradeHistoryDB()
        platform_stats = trade_db.get_stats_by_platform(simulation=simulation)

        if not platform_stats:
            console.print("[yellow]No trades found[/yellow]")
            return

        mode = "SIMULATION" if simulation else "LIVE"
        mode_color = "yellow" if simulation else "green"

        console.print(f"\n[{mode_color} bold]{mode} Trading Statistics by Platform[/{mode_color} bold]\n")

        for platform, stats in platform_stats.items():
            table = Table(
                title=f"[bold magenta]{platform.upper()}[/bold magenta]",
                show_header=True,
                header_style="bold cyan",
                box=box.ROUNDED
            )
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")

            table.add_row("Total Trades", str(stats['total_trades']))
            table.add_row("Win Rate", f"{stats['win_rate']:.1f}%")

            pnl_color = "green" if stats['realized_pnl'] >= 0 else "red"
            roi_color = "green" if stats['roi'] >= 0 else "red"

            table.add_row("Realized P&L", f"[{pnl_color}]${stats['realized_pnl']:.2f}[/{pnl_color}]")
            table.add_row("ROI", f"[{roi_color}]{stats['roi']:.1f}%[/{roi_color}]")
            table.add_row("Avg Entry Price", f"{stats['avg_entry_price']:.1%}")

            console.print(table)
            console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command(name="bot-start")
def bot_start(
    platform: str = typer.Option("kalshi", help="Platform: polymarket or kalshi"),
    simulation: bool = typer.Option(True, "--simulation/--live", help="Run in simulation mode"),
):
    """Start the automated trading bot.

    The bot will:
    - Scan for opportunities every 6 hours
    - Execute trades automatically (20-30 per day max)
    - Check for market resolutions every hour
    - Update P&L automatically
    - Apply risk management (max 5% daily exposure)
    """
    try:
        mode = "SIMULATION" if simulation else "LIVE"
        mode_color = "yellow" if simulation else "red"

        console.print(f"\n[{mode_color} bold]Starting {mode} Bot on {platform.upper()}[/{mode_color} bold]\n")

        if not simulation:
            confirm = typer.confirm("⚠️  Start LIVE trading with real funds?")
            if not confirm:
                raise typer.Exit(0)

        # Initialize and start bot
        bot = BotRunner(platform=platform, simulation=simulation)

        console.print("[green]Bot started successfully![/green]")
        console.print("\nConfiguration:")
        console.print(f"  Platform: {platform.upper()}")
        console.print(f"  Mode: {mode}")
        console.print(f"  Scan interval: 6 hours")
        console.print(f"  Max trades/scan: 20")
        console.print(f"  Max trades/day: 50")
        console.print(f"  Max exposure/day: 5% of bankroll")
        console.print(f"  Resolution checks: Every 1 hour")
        console.print("\nCommands:")
        console.print("  python bot.py bot-status   - Check bot status and P&L")
        console.print("  python bot.py bot-stop     - Stop the bot")
        console.print("  Ctrl+C                     - Stop the bot")
        console.print()

        # Start bot (blocking)
        bot.start()

    except KeyboardInterrupt:
        console.print("\n[yellow]Bot stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command(name="bot-stop")
def bot_stop():
    """Stop the running bot."""
    try:
        bot = BotRunner()

        if not bot.is_running():
            console.print("[yellow]Bot is not running[/yellow]")
            return

        bot.stop()
        console.print("[green]Bot stopped successfully[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command(name="bot-status")
def bot_status(
    simulation: bool = typer.Option(False, "--simulation", help="Show simulation status"),
    platform: str = typer.Option("kalshi", help="Platform to check"),
):
    """Show comprehensive bot status and performance.

    Displays:
    - Bot running status
    - Today's trading activity
    - P&L summary (total, win rate, ROI)
    - Open positions
    - Recent trades
    - Win rate and average edge
    """
    try:
        trade_db = TradeHistoryDB()

        # Get P&L summary
        pnl_stats = trade_db.get_pnl_summary(simulation=simulation, platform=platform)

        # Get open trades
        open_trades = trade_db.get_open_trades(simulation=simulation, platform=platform)

        # Get recent trades
        recent_trades = trade_db.get_trades(simulation=simulation, platform=platform, limit=5)

        mode = "SIMULATION" if simulation else "LIVE"
        mode_color = "yellow" if simulation else "green"

        # Header
        console.print(f"\n[{mode_color} bold]Bot Status - {mode} Mode ({platform.upper()})[/{mode_color} bold]\n")

        # Main stats table
        table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED, title="Performance Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        # Trading stats
        table.add_row("Total Trades", str(pnl_stats['total_trades']))
        table.add_row("Open Positions", str(len(open_trades)))
        table.add_row("Win Rate", f"{pnl_stats['win_rate']:.1f}%")
        table.add_row("", "")

        # P&L
        pnl_color = "green" if pnl_stats['realized_pnl'] >= 0 else "red"
        roi_color = "green" if pnl_stats['roi'] >= 0 else "red"

        table.add_row("Realized P&L", f"[{pnl_color}]${pnl_stats['realized_pnl']:.2f}[/{pnl_color}]")
        table.add_row("Total Invested", f"${pnl_stats['total_invested']:.2f}")
        table.add_row("ROI", f"[{roi_color}]{pnl_stats['roi']:.1f}%[/{roi_color}]")
        table.add_row("", "")

        # Trade quality
        avg_pnl_color = "green" if pnl_stats['avg_pnl_per_trade'] >= 0 else "red"
        table.add_row("Avg P&L/Trade", f"[{avg_pnl_color}]${pnl_stats['avg_pnl_per_trade']:.2f}[/{avg_pnl_color}]")
        table.add_row("Best Trade", f"[green]${pnl_stats['best_trade']:.2f}[/green]")
        table.add_row("Worst Trade", f"[red]${pnl_stats['worst_trade']:.2f}[/red]")
        table.add_row("", "")

        # Strategy metrics
        table.add_row("Avg Entry Price", f"{pnl_stats['avg_entry_price']:.1%}")
        table.add_row("Avg Edge", f"{pnl_stats['avg_edge']:.1%}")

        console.print(table)
        console.print()

        # Recent trades
        if recent_trades:
            console.print("[bold]Recent Trades:[/bold]\n")

            trades_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
            trades_table.add_column("Date", style="dim")
            trades_table.add_column("Side", style="yellow")
            trades_table.add_column("Price", justify="right")
            trades_table.add_column("Size", justify="right")
            trades_table.add_column("P&L", justify="right")
            trades_table.add_column("Question", max_width=40)

            for trade in recent_trades[:5]:
                timestamp = datetime.fromisoformat(trade['timestamp'])
                date_str = timestamp.strftime("%m/%d %H:%M")

                if trade['resolved']:
                    pnl = trade['pnl']
                    pnl_color = "green" if pnl >= 0 else "red"
                    pnl_str = f"[{pnl_color}]${pnl:.2f}[/{pnl_color}]"
                else:
                    pnl_str = "[dim]pending[/dim]"

                trades_table.add_row(
                    date_str,
                    trade['side'],
                    f"{trade['price']:.1%}",
                    f"${trade['size']:.2f}",
                    pnl_str,
                    trade['question'][:37] + "..." if len(trade['question']) > 40 else trade['question']
                )

            console.print(trades_table)
            console.print()

        # Open positions summary
        if open_trades:
            total_at_risk = sum(t['cost'] for t in open_trades)
            console.print(f"[yellow]Open Positions:[/yellow] {len(open_trades)} trades, ${total_at_risk:.2f} at risk\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def analyze_wallet(
    wallet_address: str = typer.Argument(..., help="Ethereum wallet address (0x...)"),
    limit: int = typer.Option(1000, help="Maximum number of trades to fetch"),
    show_trades: bool = typer.Option(False, help="Show individual trades"),
):
    """
    Analyze a Polymarket wallet to reverse engineer their trading strategy.

    This analyzes entry thresholds, position sizing, market selection, and
    trading frequency to understand how successful traders operate.
    """
    try:
        from bot.analysis import WalletAnalyzer

        console.print(f"[cyan]Analyzing wallet:[/cyan] {wallet_address}\n")

        with console.status("[bold green]Fetching trades from Polymarket..."):
            analyzer = WalletAnalyzer()
            profile = analyzer.analyze_wallet(wallet_address, limit)

        if profile.total_trades == 0:
            console.print("[yellow]No trades found for this wallet.[/yellow]")
            console.print("\n[dim]Possible reasons:")
            console.print("  - Wallet has no trading activity on Polymarket")
            console.print("  - Wallet address is incorrect")
            console.print("  - API rate limits or connectivity issues")
            console.print("  - Polymarket API requires authentication (recent change)[/dim]")
            console.print("\n[cyan]Alternative: Use Polymarket Analytics directly:[/cyan]")
            console.print(f"https://polymarketanalytics.com/traders/{wallet_address}")
            console.print("\nOr try The Graph explorer:")
            console.print(f"https://thegraph.com/explorer/subgraphs/BdXdeG7WR6bjdWwe9wfN2bhJ2VpX3RQP1v1LNdMhQAMw")
            return

        # ====== STRATEGY OVERVIEW ======
        overview_table = Table(title="🎯 Strategy Overview", box=box.ROUNDED)
        overview_table.add_column("Metric", style="cyan")
        overview_table.add_column("Value", style="white")

        overview_table.add_row("Total Trades", f"{profile.total_trades:,}")
        overview_table.add_row("Total Volume", f"${profile.total_volume:,.2f}")

        if profile.total_pnl != 0:
            pnl_color = "green" if profile.total_pnl > 0 else "red"
            overview_table.add_row("Total P&L", f"[{pnl_color}]${profile.total_pnl:,.2f}[/{pnl_color}]")
            overview_table.add_row("Profit per Trade", f"[{pnl_color}]${profile.avg_profit_per_trade:.2f}[/{pnl_color}]")

        if profile.win_rate > 0:
            overview_table.add_row("Win Rate", f"{profile.win_rate:.1%}")

        overview_table.add_row("Trading Period", f"{profile.trading_days} days")
        overview_table.add_row("Trades per Day", f"{profile.trades_per_day:.1f}")

        console.print(overview_table)
        console.print()

        # ====== ENTRY THRESHOLDS ======
        if profile.yes_entry_prices or profile.no_entry_prices:
            threshold_table = Table(title="📊 Entry Thresholds (Extreme Value Strategy)", box=box.ROUNDED)
            threshold_table.add_column("Metric", style="cyan")
            threshold_table.add_column("YES Buys", style="green")
            threshold_table.add_column("NO Buys", style="red")

            yes_count = len(profile.yes_entry_prices)
            no_count = len(profile.no_entry_prices)

            threshold_table.add_row("Trade Count", str(yes_count), str(no_count))

            if yes_count > 0:
                threshold_table.add_row(
                    "Average Entry",
                    f"{profile.avg_yes_entry:.1%}",
                    f"{profile.avg_no_entry:.1%}" if no_count > 0 else "-"
                )
                threshold_table.add_row(
                    "Median Entry",
                    f"{profile.median_yes_entry:.1%}",
                    f"{profile.median_no_entry:.1%}" if no_count > 0 else "-"
                )
                threshold_table.add_row(
                    "10th Percentile",
                    f"{profile.yes_10th_percentile:.1%}",
                    "-"
                )
                threshold_table.add_row(
                    "90th Percentile",
                    f"{profile.yes_90th_percentile:.1%}",
                    "-"
                )

            console.print(threshold_table)
            console.print()

        # ====== POSITION SIZING ======
        sizing_table = Table(title="💰 Position Sizing", box=box.ROUNDED)
        sizing_table.add_column("Metric", style="cyan")
        sizing_table.add_column("Value", style="white")

        sizing_table.add_row("Average Size", f"${profile.avg_position_size:.2f}")
        sizing_table.add_row("Median Size", f"${profile.median_position_size:.2f}")
        sizing_table.add_row("Min Size", f"${profile.min_position_size:.2f}")
        sizing_table.add_row("Max Size", f"${profile.max_position_size:.2f}")
        sizing_table.add_row("Std Deviation", f"${profile.position_size_stddev:.2f}")
        sizing_table.add_row("Max Single Position %", f"{profile.max_single_position_pct:.1f}%")

        console.print(sizing_table)
        console.print()

        # ====== MARKET SELECTION ======
        if profile.market_categories:
            market_table = Table(title="🎲 Market Selection", box=box.ROUNDED)
            market_table.add_column("Category", style="cyan")
            market_table.add_column("Trades", justify="right", style="white")
            market_table.add_column("Percentage", justify="right", style="yellow")

            for category, count in sorted(profile.market_categories.items(), key=lambda x: x[1], reverse=True):
                pct = count / profile.total_trades * 100
                market_table.add_row(
                    category.title(),
                    f"{count:,}",
                    f"{pct:.1f}%"
                )

            console.print(market_table)
            console.print()

            # Weather focus highlight
            if profile.weather_percentage > 0:
                weather_pct = profile.weather_percentage * 100
                if weather_pct >= 80:
                    focus = "🌟 HEAVY"
                    color = "green"
                elif weather_pct >= 50:
                    focus = "🎯 MODERATE"
                    color = "yellow"
                else:
                    focus = "💡 LIGHT"
                    color = "white"

                console.print(f"[{color}]{focus} Weather Focus: {weather_pct:.1f}% of all trades[/{color}]\n")

        # ====== RISK MANAGEMENT ======
        risk_table = Table(title="⚠️ Risk Management", box=box.ROUNDED)
        risk_table.add_column("Metric", style="cyan")
        risk_table.add_column("Value", style="white")

        risk_table.add_row("Max Daily Exposure", f"${profile.max_daily_exposure:.2f}")
        risk_table.add_row("Avg Daily Exposure", f"${profile.avg_daily_exposure:.2f}")
        risk_table.add_row("Max Position as % of Volume", f"{profile.max_single_position_pct:.1f}%")

        console.print(risk_table)
        console.print()

        # ====== PERFORMANCE BY PRICE RANGE ======
        if profile.yes_low_performance.get('count', 0) > 0:
            perf_table = Table(title="📈 Performance by Entry Range", box=box.ROUNDED)
            perf_table.add_column("Range", style="cyan")
            perf_table.add_column("Trades", justify="right", style="white")
            perf_table.add_column("Avg Entry", justify="right", style="yellow")
            perf_table.add_column("Avg Size", justify="right", style="green")
            perf_table.add_column("Total Volume", justify="right", style="magenta")

            ranges = [
                ("YES < 15¢ (Extreme)", profile.yes_low_performance),
                ("YES 15-40¢ (Mid)", profile.yes_mid_performance),
                ("NO (YES > 40¢)", profile.no_performance),
            ]

            for label, perf in ranges:
                if perf.get('count', 0) > 0:
                    perf_table.add_row(
                        label,
                        f"{perf['count']:,}",
                        f"{perf['avg_entry']:.1%}",
                        f"${perf['avg_size']:.2f}",
                        f"${perf['total_volume']:.2f}"
                    )

            console.print(perf_table)
            console.print()

        # ====== STRATEGY RECOMMENDATION ======
        console.print("[bold cyan]🎯 Reverse Engineered Strategy:[/bold cyan]\n")

        strategy_lines = []

        # Entry thresholds
        if profile.yes_entry_prices:
            strategy_lines.append(f"📍 YES Entry: Buy when price ≤ {profile.median_yes_entry:.1%} (median: {profile.median_yes_entry:.1%})")
            strategy_lines.append(f"   Range: {profile.yes_10th_percentile:.1%} to {profile.yes_90th_percentile:.1%}")

        if profile.no_entry_prices:
            # Convert NO entry to YES price for clarity
            yes_price_for_no = 1 - profile.median_no_entry
            strategy_lines.append(f"📍 NO Entry: Buy when YES price ≥ {yes_price_for_no:.1%}")

        # Position sizing
        strategy_lines.append(f"\n💰 Position Sizing: ${profile.median_position_size:.2f} median, ${profile.avg_position_size:.2f} average")
        strategy_lines.append(f"   Range: ${profile.min_position_size:.2f} to ${profile.max_position_size:.2f}")

        # Trading frequency
        strategy_lines.append(f"\n📊 Frequency: {profile.trades_per_day:.1f} trades/day")

        # Market focus
        if profile.weather_percentage > 0.5:
            strategy_lines.append(f"\n🌤️ Focus: {profile.weather_percentage*100:.0f}% weather markets")

        for line in strategy_lines:
            console.print(line)

        console.print()

        # ====== CONFIG TEMPLATE ======
        console.print("[bold cyan]⚙️ Suggested .env Configuration:[/bold cyan]\n")
        console.print("[dim]# Add these to your .env file to replicate this strategy:[/dim]")

        if profile.yes_entry_prices:
            console.print(f"EXTREME_YES_MAX_PRICE={profile.yes_90th_percentile:.2f}")
            console.print(f"EXTREME_YES_IDEAL_PRICE={profile.median_yes_entry:.2f}")

        if profile.no_entry_prices:
            yes_for_no = 1 - profile.median_no_entry
            console.print(f"EXTREME_NO_MIN_YES_PRICE={yes_for_no:.2f}")

        console.print(f"EXTREME_MIN_POSITION={profile.min_position_size:.2f}")
        console.print(f"EXTREME_MAX_POSITION={profile.median_position_size:.2f}")
        console.print(f"EXTREME_AGGRESSIVE_MAX={profile.max_position_size:.2f}")

        console.print()

        # ====== INDIVIDUAL TRADES ======
        if show_trades and profile.trades:
            console.print(f"\n[bold cyan]📝 Individual Trades (showing last {min(20, len(profile.trades))}):[/bold cyan]\n")

            trades_table = Table(box=box.SIMPLE)
            trades_table.add_column("Date", style="dim")
            trades_table.add_column("Side", style="yellow")
            trades_table.add_column("Entry", justify="right")
            trades_table.add_column("Size", justify="right")
            trades_table.add_column("Type", style="cyan")
            trades_table.add_column("Question", max_width=40)

            for trade in profile.trades[-20:]:
                trades_table.add_row(
                    trade.timestamp.strftime("%m/%d"),
                    trade.side,
                    f"{trade.entry_price:.1%}",
                    f"${trade.position_size:.2f}",
                    trade.market_type or "unknown",
                    trade.market_question[:37] + "..." if len(trade.market_question) > 40 else trade.market_question
                )

            console.print(trades_table)

    except Exception as e:
        console.print("[red]Error analyzing wallet:[/red]")
        console.print(str(e), markup=False)
        import traceback
        console.print("[dim]Full traceback:[/dim]")
        console.print(traceback.format_exc(), markup=False)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
