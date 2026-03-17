"""
Watchlist vs Portfolio Mode
---------------------------
Two modes:
  - Watchlist: stocks you're tracking but don't own (focus on entry points)
  - Portfolio: stocks you own (focus on hold/sell decisions, P&L tracking)
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .verdict_system import StockVerdict

console = Console()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "watchlist_config.json")


@dataclass
class PortfolioPosition:
    """A stock position with cost basis tracking."""
    ticker: str
    shares: float
    cost_basis: float  # Average cost per share
    purchase_date: str = ""

    @property
    def total_cost(self) -> float:
        return self.shares * self.cost_basis


@dataclass
class WatchlistConfig:
    """Configuration for watchlist/portfolio modes."""
    portfolio_positions: List[PortfolioPosition] = field(default_factory=list)
    watchlist_tickers: List[str] = field(default_factory=list)


def load_config(config_path: str = CONFIG_PATH) -> WatchlistConfig:
    """Load watchlist/portfolio config from JSON file."""
    config = WatchlistConfig()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            for p in data.get("portfolio", []):
                config.portfolio_positions.append(PortfolioPosition(
                    ticker=p["ticker"],
                    shares=p.get("shares", 0),
                    cost_basis=p.get("cost_basis", 0),
                    purchase_date=p.get("purchase_date", ""),
                ))
            config.watchlist_tickers = data.get("watchlist", [])
        except (json.JSONDecodeError, KeyError):
            pass
    return config


def save_config(config: WatchlistConfig, config_path: str = CONFIG_PATH):
    """Save watchlist/portfolio config to JSON file."""
    data = {
        "portfolio": [
            {
                "ticker": p.ticker,
                "shares": p.shares,
                "cost_basis": p.cost_basis,
                "purchase_date": p.purchase_date,
            }
            for p in config.portfolio_positions
        ],
        "watchlist": config.watchlist_tickers,
    }
    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)


def create_default_config(tickers: List[str], config_path: str = CONFIG_PATH) -> WatchlistConfig:
    """Create a default config treating all tickers as watchlist items."""
    config = WatchlistConfig(watchlist_tickers=tickers)
    save_config(config, config_path)
    return config


def render_portfolio_mode(verdicts: List[StockVerdict], config: WatchlistConfig):
    """Render portfolio view with P&L tracking."""
    positions = {p.ticker: p for p in config.portfolio_positions}
    portfolio_verdicts = [v for v in verdicts if v.ticker in positions]

    if not portfolio_verdicts:
        console.print("[yellow]No portfolio positions configured.[/yellow]")
        return

    total_invested = 0.0
    total_current = 0.0

    table = Table(title="PORTFOLIO MODE - Your Holdings", box=box.ROUNDED,
                  border_style="green", title_style="bold green")
    table.add_column("Ticker", style="bold cyan", width=8)
    table.add_column("Company", width=16)
    table.add_column("Shares", justify="right", width=8)
    table.add_column("Cost Basis", justify="right", width=10)
    table.add_column("Current", justify="right", width=10)
    table.add_column("P&L", justify="right", width=12)
    table.add_column("P&L %", justify="right", width=8)
    table.add_column("Verdict", justify="center", width=8)
    table.add_column("Score", justify="center", width=7)
    table.add_column("Action Signal", justify="center", width=14)

    for v in sorted(portfolio_verdicts, key=lambda x: x.score, reverse=True):
        pos = positions[v.ticker]
        current_val = pos.shares * v.current_price
        invested = pos.total_cost
        pnl = current_val - invested
        pnl_pct = ((v.current_price - pos.cost_basis) / pos.cost_basis * 100) if pos.cost_basis > 0 else 0

        total_invested += invested
        total_current += current_val

        pnl_c = "green" if pnl >= 0 else "red"
        vc = {"Buy": "green", "Hold": "yellow", "Pass": "bright_black", "Avoid": "red"}.get(v.verdict, "white")

        # Action signal based on verdict + P&L
        if v.verdict == "Avoid" or (v.verdict == "Pass" and pnl_pct > 20):
            action = "[bold red]CONSIDER SELLING[/bold red]"
        elif v.verdict == "Buy" and pnl_pct < -10:
            action = "[bold green]ADD TO POSITION[/bold green]"
        elif v.verdict == "Buy":
            action = "[green]HOLD / ADD[/green]"
        elif v.verdict == "Hold":
            action = "[yellow]HOLD[/yellow]"
        else:
            action = "[bright_black]REVIEW[/bright_black]"

        table.add_row(
            v.ticker,
            v.company_name[:16],
            f"{pos.shares:.1f}",
            f"${pos.cost_basis:.2f}",
            f"${v.current_price:.2f}",
            f"[{pnl_c}]${pnl:+,.2f}[/{pnl_c}]",
            f"[{pnl_c}]{pnl_pct:+.1f}%[/{pnl_c}]",
            f"[{vc}]{v.verdict}[/{vc}]",
            f"{v.score:.1f}",
            action,
        )

    console.print(table)

    # Portfolio summary
    total_pnl = total_current - total_invested
    total_pnl_pct = ((total_current - total_invested) / total_invested * 100) if total_invested > 0 else 0
    pnl_c = "green" if total_pnl >= 0 else "red"

    console.print(Panel(
        f"Total Invested: ${total_invested:,.2f}  |  "
        f"Current Value: ${total_current:,.2f}  |  "
        f"P&L: [{pnl_c}]${total_pnl:+,.2f} ({total_pnl_pct:+.1f}%)[/{pnl_c}]",
        border_style="green",
    ))


def render_watchlist_mode(verdicts: List[StockVerdict], config: WatchlistConfig):
    """Render watchlist view focused on entry points."""
    watchlist_verdicts = [v for v in verdicts if v.ticker in config.watchlist_tickers]

    if not watchlist_verdicts:
        # If no config, show all as watchlist
        watchlist_verdicts = verdicts

    table = Table(title="WATCHLIST MODE - Stocks You're Watching", box=box.ROUNDED,
                  border_style="cyan", title_style="bold cyan")
    table.add_column("Ticker", style="bold cyan", width=8)
    table.add_column("Company", width=16)
    table.add_column("Price", justify="right", width=10)
    table.add_column("Target", justify="right", width=10)
    table.add_column("Upside", justify="right", width=8)
    table.add_column("Verdict", justify="center", width=8)
    table.add_column("Score", justify="center", width=7)
    table.add_column("Entry Signal", justify="center", width=16)
    table.add_column("Risk", justify="center", width=10)

    for v in sorted(watchlist_verdicts, key=lambda x: x.score, reverse=True):
        vc = {"Buy": "green", "Hold": "yellow", "Pass": "bright_black", "Avoid": "red"}.get(v.verdict, "white")
        up_c = "green" if (v.upside_pct or 0) >= 0 else "red"

        # Entry signal
        if v.verdict == "Buy" and v.score >= 8.0:
            entry = "[bold green]STRONG BUY[/bold green]"
        elif v.verdict == "Buy":
            entry = "[green]BUY ZONE[/green]"
        elif v.verdict == "Hold" and (v.upside_pct or 0) > 20:
            entry = "[yellow]WAIT FOR DIP[/yellow]"
        elif v.verdict == "Pass":
            entry = "[bright_black]NOT YET[/bright_black]"
        else:
            entry = "[red]AVOID[/red]"

        # Risk assessment
        if v.earnings_countdown and v.earnings_countdown <= 7:
            risk = "[red]Earnings![/red]"
        elif v.momentum_score < 3:
            risk = "[red]Falling[/red]"
        elif v.momentum_score > 7:
            risk = "[green]Momentum[/green]"
        else:
            risk = "[yellow]Normal[/yellow]"

        table.add_row(
            v.ticker,
            v.company_name[:16],
            f"${v.current_price:.2f}",
            f"${v.one_year_target:.2f}" if v.one_year_target else "N/A",
            f"[{up_c}]{v.upside_pct:+.1f}%[/{up_c}]" if v.upside_pct else "N/A",
            f"[{vc}]{v.verdict}[/{vc}]",
            f"{v.score:.1f}",
            entry,
            risk,
        )

    console.print(table)


def render_watchlist_portfolio(verdicts: List[StockVerdict]):
    """Render both modes, auto-detecting from config."""
    config = load_config()

    # If no config exists, create default with all tickers as watchlist
    if not config.portfolio_positions and not config.watchlist_tickers:
        tickers = [v.ticker for v in verdicts]
        config = create_default_config(tickers)
        console.print(
            f"[dim]Created default watchlist config at {CONFIG_PATH}[/dim]"
        )
        console.print(
            "[dim]Edit it to add portfolio positions with cost basis for P&L tracking[/dim]\n"
        )

    if config.portfolio_positions:
        render_portfolio_mode(verdicts, config)
        console.print()

    render_watchlist_mode(verdicts, config)
    console.print()
