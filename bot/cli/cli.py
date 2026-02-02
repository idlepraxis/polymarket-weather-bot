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

from bot.application.extreme_value_strategy import ExtremeValueStrategy
from bot.application.bot_runner import BotRunner
from bot.connectors.weather import WeatherConnector
from bot.database.trade_history import TradeHistoryDB
from bot.utils.config import Config, get_config
from bot.utils.logger import setup_logger, get_logger
from bot.utils.models import Trade, TradeSide

# Optional Polymarket support
try:
    from bot.connectors.polymarket import PolymarketClient
    POLYMARKET_AVAILABLE = True
except ImportError:
    POLYMARKET_AVAILABLE = False
    PolymarketClient = None

app = typer.Typer(
    name="polymarket-weather-bot",
    help="Automated trading bot for Polymarket weather prediction markets",
    add_completion=False,
)

console = Console()


@app.command()
def status(
    simulation: bool = typer.Option(True, help="Show simulation or live trades"),
):
    """Show bot status and portfolio summary."""
    try:
        platform = "polymarket"

        # Get data directly from database without initializing connectors
        trade_db = TradeHistoryDB()

        # Get P&L summary
        pnl = trade_db.get_pnl_summary(simulation=simulation, platform=platform)

        # Get open trades count
        open_trades = trade_db.get_open_trades(simulation=simulation, platform=platform)

        # Get recent trades (fetch up to 100, show all)
        recent_trades = trade_db.get_trades(simulation=simulation, platform=platform, limit=100)

        # Create status panel
        status_table = Table(show_header=False, box=box.SIMPLE)
        status_table.add_column("Metric", style="cyan")
        status_table.add_column("Value", style="green")

        mode = "SIMULATION" if simulation else "LIVE"
        mode_color = "yellow" if simulation else "red"

        status_table.add_row("Trading Mode", f"[{mode_color}]{mode}[/{mode_color}]")
        status_table.add_row("Platform", "POLYMARKET")
        status_table.add_row("Total Trades", str(pnl['total_trades']))
        status_table.add_row("Open Positions", str(len(open_trades)))
        status_table.add_row("Resolved Trades", str(pnl['winning_trades'] + pnl['losing_trades']))
        status_table.add_row("Win Rate", f"{pnl['win_rate']:.1f}%")
        status_table.add_row("Total P&L", f"${pnl['realized_pnl']:.2f}")
        status_table.add_row("Total Invested", f"${pnl['total_invested']:.2f}")
        status_table.add_row("ROI", f"{pnl['roi']:.1f}%")

        console.print(Panel(status_table, title="Portfolio Status", border_style="blue"))

        # Recent trades
        if recent_trades:
            trades_table = Table(title="Recent Trades", box=box.ROUNDED)
            trades_table.add_column("Date", style="dim")
            trades_table.add_column("Side", style="cyan")
            trades_table.add_column("Market", style="white", max_width=60)
            trades_table.add_column("Price", justify="right")
            trades_table.add_column("Size", justify="right", style="yellow")
            trades_table.add_column("Status", style="green")

            for trade in recent_trades:  # Show all trades (up to 100)
                # Parse timestamp
                try:
                    trade_time = datetime.fromisoformat(trade['timestamp'])
                    time_str = trade_time.strftime("%m/%d %H:%M")
                except:
                    time_str = "Unknown"

                # Determine status
                if trade['resolved']:
                    status = "🎉 WON" if trade['won'] else "❌ LOST"
                    status += f" (${trade['pnl']:+.2f})"
                else:
                    status = "⏳ Pending"

                market_str = trade['question'][:57] + "..." if len(trade['question']) > 60 else trade['question']

                # Extract YES/NO from token_id
                token_side = "YES" if "YES" in trade['token_id'].upper() else "NO"

                trades_table.add_row(
                    time_str,
                    token_side,
                    market_str,
                    f"{trade['price']:.2f}",
                    f"${trade['cost']:.2f}",
                    status
                )

            console.print(trades_table)
        else:
            console.print("\n[yellow]No trades found[/yellow]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}", markup=False)
        import traceback
        console.print(traceback.format_exc(), markup=False)
        raise typer.Exit(1)


@app.command()
def balance():
    """Check Polymarket USDC balance."""
    try:
        config = get_config()
        client = PolymarketClient(config)
        bal = client.get_usdc_balance()
        console.print(f"\n[green]Polymarket USDC Balance:[/green] ${bal:.2f}\n")

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
    simulation: bool = typer.Option(True, "--simulation/--live", help="Run in simulation mode"),
):
    """Start the automated trading bot.

    The bot will:
    - Scan for opportunities based on configured interval (default: 6 hours)
    - Execute trades automatically based on strategy parameters
    - Check for market resolutions periodically (default: every hour)
    - Update P&L automatically
    - Apply risk management (default: max 5% daily exposure)
    """
    try:
        mode = "SIMULATION" if simulation else "LIVE"
        mode_color = "yellow" if simulation else "red"

        console.print(f"\n[{mode_color} bold]Starting {mode} Bot on POLYMARKET[/{mode_color} bold]\n")

        if not simulation:
            confirm = typer.confirm("⚠️  Start LIVE trading with real funds?")
            if not confirm:
                raise typer.Exit(0)

        # Initialize and start bot
        bot = BotRunner(simulation=simulation)

        console.print("[green]Bot started successfully![/green]")
        console.print("\nConfiguration:")
        console.print("  Platform: POLYMARKET")
        console.print(f"  Mode: {mode}")
        console.print(f"  Scan interval: {bot.config.scan_interval_hours} hours")
        console.print(f"  Max trades/scan: {bot.config.max_trades_per_scan}")
        console.print(f"  Max trades/day: {bot.config.max_trades_per_day}")
        console.print(f"  Max exposure/day: {bot.config.max_daily_exposure_pct}% of bankroll")
        console.print(f"  Resolution checks: Every {bot.config.resolution_check_hours} hour")
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
        platform = "polymarket"
        trade_db = TradeHistoryDB()

        # Get P&L summary
        pnl_stats = trade_db.get_pnl_summary(simulation=simulation, platform=platform)

        # Get open trades
        open_trades = trade_db.get_open_trades(simulation=simulation, platform=platform)

        # Get recent trades (show more for better visibility)
        recent_trades = trade_db.get_trades(simulation=simulation, platform=platform, limit=20)

        mode = "SIMULATION" if simulation else "LIVE"
        mode_color = "yellow" if simulation else "green"

        # Header
        console.print(f"\n[{mode_color} bold]Bot Status - {mode} Mode (POLYMARKET)[/{mode_color} bold]\n")

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
            trades_table.add_column("Question", max_width=60)

            for trade in recent_trades[:5]:
                timestamp = datetime.fromisoformat(trade['timestamp'])
                date_str = timestamp.strftime("%m/%d %H:%M")

                if trade['resolved']:
                    pnl = trade['pnl']
                    pnl_color = "green" if pnl >= 0 else "red"
                    pnl_str = f"[{pnl_color}]${pnl:.2f}[/{pnl_color}]"
                else:
                    pnl_str = "[dim]pending[/dim]"

                # Extract YES/NO from token_id
                token_side = "YES" if "YES" in trade['token_id'].upper() else "NO"

                trades_table.add_row(
                    date_str,
                    token_side,
                    f"{trade['price']:.1%}",
                    f"${trade['size']:.2f}",
                    pnl_str,
                    trade['question'][:57] + "..." if len(trade['question']) > 60 else trade['question']
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
    limit: int = typer.Option(10000, help="Maximum number of trades to fetch"),
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
            console.print("  - Polymarket API requires authentication (recent change)")
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


# ============================================================================
# BACKTESTING COMMANDS
# ============================================================================

@app.command()
def backtest(
    min_price: float = typer.Option(0.03, help="Minimum YES price (skip below)"),
    max_price: float = typer.Option(0.12, help="Maximum YES price (skip above)"),
    min_edge: float = typer.Option(0.10, help="Minimum edge required"),
    skip_yes_threshold: bool = typer.Option(False, "--skip-yes-threshold", help="Skip YES bets on threshold markets"),
    compare: bool = typer.Option(False, "--compare", help="Compare multiple strategies"),
):
    """Run backtest against historical trades.

    Examples:
        python bot.py backtest
        python bot.py backtest --min-price 0.05 --skip-yes-threshold
        python bot.py backtest --compare
    """
    from bot.backtesting.engine import BacktestEngine, BacktestParams

    try:
        engine = BacktestEngine()

        if compare:
            # Compare multiple strategy configurations
            param_sets = [
                BacktestParams(),  # Current defaults
                BacktestParams(yes_min_price=0.0),  # No min price filter
                BacktestParams(skip_yes_on_threshold=True),  # Skip YES threshold
                BacktestParams(yes_min_price=0.05),  # Higher min price
                BacktestParams(skip_yes_on_threshold=True, yes_min_price=0.03),  # Combined
            ]
            names = [
                "v2.5.0 Defaults",
                "No Min Price",
                "Skip YES Threshold",
                "Min Price 5¢",
                "Strict Mode",
            ]

            results = engine.compare_strategies(param_sets, names)
            engine.print_comparison(results)
        else:
            # Single backtest with specified parameters
            params = BacktestParams(
                yes_min_price=min_price,
                yes_max_price=max_price,
                min_edge=min_edge,
                skip_yes_on_threshold=skip_yes_threshold,
            )

            result = engine.run_backtest(params)

            # Display results
            console.print("\n" + "=" * 70)
            console.print("[bold cyan]BACKTEST RESULTS[/bold cyan]")
            console.print("=" * 70)

            # Parameters used
            console.print("\n[yellow]Parameters:[/yellow]")
            console.print(f"  Min Price: {params.yes_min_price:.0%}")
            console.print(f"  Max Price: {params.yes_max_price:.0%}")
            console.print(f"  Min Edge: {params.min_edge:.0%}")
            console.print(f"  Skip YES Threshold: {params.skip_yes_on_threshold}")

            # Summary
            console.print("\n[yellow]Results:[/yellow]")
            console.print(f"  Trades: {result.total_trades}")
            console.print(f"  Wins: {result.wins} ({result.win_rate*100:.1f}%)")
            console.print(f"  Losses: {result.losses}")
            console.print(f"  P&L: ${result.total_pnl:+.2f}")
            console.print(f"  Invested: ${result.total_invested:.2f}")
            console.print(f"  ROI: {result.roi*100:+.1f}%")

            # Breakdown by category
            if result.breakdown:
                console.print("\n[yellow]Breakdown by Trade Type:[/yellow]")
                breakdown_table = Table(box=box.SIMPLE)
                breakdown_table.add_column("Type", style="cyan")
                breakdown_table.add_column("Trades", justify="right")
                breakdown_table.add_column("Wins", justify="right")
                breakdown_table.add_column("Win Rate", justify="right")
                breakdown_table.add_column("P&L", justify="right")
                breakdown_table.add_column("ROI", justify="right")

                for cat, data in result.breakdown.items():
                    breakdown_table.add_row(
                        cat,
                        str(data["trades"]),
                        str(data["wins"]),
                        f"{data['win_rate']*100:.1f}%",
                        f"${data['pnl']:+.2f}",
                        f"{data['roi']*100:+.1f}%",
                    )

                console.print(breakdown_table)

            # Skipped trades
            if result.skipped:
                console.print("\n[yellow]Skipped Trades:[/yellow]")
                for reason, trades in result.skipped.items():
                    skipped_pnl = sum(t["pnl"] or 0 for t in trades)
                    console.print(f"  {reason}: {len(trades)} trades (${skipped_pnl:+.2f} avoided P&L)")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback
        console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command("backtest-compare")
def backtest_compare(
    save: bool = typer.Option(False, "--save", help="Save results to backtest database"),
):
    """Compare all common strategy configurations.

    This runs multiple backtests and shows a comparison table.

    Examples:
        python bot.py backtest-compare
        python bot.py backtest-compare --save
    """
    from bot.backtesting.engine import BacktestEngine, BacktestParams
    from bot.backtesting.database import BacktestDatabase

    try:
        engine = BacktestEngine()

        # Define strategies to compare
        strategies = [
            ("Actual v2.4.0", BacktestParams(yes_min_price=0.0, skip_yes_on_threshold=False)),
            ("Min 3¢ Only", BacktestParams(yes_min_price=0.03, skip_yes_on_threshold=False)),
            ("Skip YES Thresh", BacktestParams(yes_min_price=0.0, skip_yes_on_threshold=True)),
            ("v2.5.0 Default", BacktestParams(yes_min_price=0.03, skip_yes_on_threshold=False)),
            ("Strict Mode", BacktestParams(yes_min_price=0.03, skip_yes_on_threshold=True)),
            ("Conservative", BacktestParams(yes_min_price=0.05, skip_yes_on_threshold=True, min_edge=0.15)),
        ]

        names = [s[0] for s in strategies]
        param_sets = [s[1] for s in strategies]

        results = engine.compare_strategies(param_sets, names)
        engine.print_comparison(results)

        if save:
            db = BacktestDatabase()
            for r in results:
                db.save_backtest_run(
                    run_name=r["name"],
                    params=r["params"],
                    results=r,
                )
            console.print(f"\n[green]✓ Saved {len(results)} backtest results to database[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback
        console.print(traceback.format_exc())
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
