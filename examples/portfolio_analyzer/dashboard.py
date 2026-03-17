"""
Dashboard
---------
Main dashboard rendering that ties all modules together.
"""

from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .verdict_system import StockVerdict
from .data_fetcher import StockData
from .macro_tracker import MacroDashboard, render_macro_dashboard

console = Console()


def render_verdicts_table(verdicts: List[StockVerdict]):
    """Render the main stock verdicts summary table."""
    table = Table(title="STOCK ANALYSIS DASHBOARD", box=box.ROUNDED,
                  border_style="bold cyan", title_style="bold cyan")
    table.add_column("#", width=3, style="dim")
    table.add_column("Ticker", style="bold cyan", width=8)
    table.add_column("Company", width=18)
    table.add_column("Sector", width=16)
    table.add_column("Price", justify="right", width=10)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Verdict", justify="center", width=8)
    table.add_column("Val", justify="center", width=5)
    table.add_column("Qual", justify="center", width=5)
    table.add_column("Mom", justify="center", width=5)
    table.add_column("Target", justify="right", width=10)
    table.add_column("Upside", justify="right", width=8)
    table.add_column("Earnings", justify="center", width=10)

    for i, v in enumerate(sorted(verdicts, key=lambda x: x.score, reverse=True), 1):
        vc = {"Buy": "bold green", "Hold": "yellow", "Pass": "bright_black",
              "Avoid": "bold red"}.get(v.verdict, "white")
        sc = "green" if v.score >= 7 else "yellow" if v.score >= 5 else "red"
        up_c = "green" if (v.upside_pct or 0) >= 0 else "red"

        earn_str = ""
        if v.earnings_countdown is not None:
            if v.earnings_countdown <= 3:
                earn_str = f"[bold red]{v.earnings_countdown}d !!![/bold red]"
            elif v.earnings_countdown <= 7:
                earn_str = f"[red]{v.earnings_countdown}d[/red]"
            elif v.earnings_countdown <= 14:
                earn_str = f"[yellow]{v.earnings_countdown}d[/yellow]"
            else:
                earn_str = f"{v.earnings_countdown}d"

        table.add_row(
            str(i),
            v.ticker,
            v.company_name[:18],
            v.sector[:16],
            f"${v.current_price:.2f}",
            f"[{sc}]{v.score:.1f}/10[/{sc}]",
            f"[{vc}]{v.verdict}[/{vc}]",
            f"{v.valuation_score:.1f}",
            f"{v.quality_score:.1f}",
            f"{v.momentum_score:.1f}",
            f"${v.one_year_target:.2f}" if v.one_year_target else "N/A",
            f"[{up_c}]{v.upside_pct:+.1f}%[/{up_c}]" if v.upside_pct is not None else "N/A",
            earn_str,
        )

    console.print(table)
    console.print()


def render_agent_details(verdicts: List[StockVerdict]):
    """Render per-stock agent breakdown."""
    for v in sorted(verdicts, key=lambda x: x.score, reverse=True):
        vc = {"Buy": "green", "Hold": "yellow", "Pass": "bright_black",
              "Avoid": "red"}.get(v.verdict, "white")

        header = (
            f"[bold cyan]{v.ticker}[/bold cyan] - {v.company_name}  |  "
            f"[{vc}]{v.verdict}[/{vc}] ({v.score:.1f}/10)  |  "
            f"${v.current_price:.2f}"
        )
        console.print(Panel(header, border_style=vc))

        agent_table = Table(box=box.SIMPLE, show_header=True)
        agent_table.add_column("Agent", width=12)
        agent_table.add_column("Score", justify="center", width=8)
        agent_table.add_column("Verdict", justify="center", width=10)
        agent_table.add_column("Rationale", width=50)

        for av in v.agent_verdicts:
            avc = {"Bullish": "green", "Neutral": "yellow", "Bearish": "red"}.get(av.verdict, "white")
            asc = "green" if av.score >= 6.5 else "yellow" if av.score >= 4.5 else "red"
            agent_table.add_row(
                av.agent_name,
                f"[{asc}]{av.score:.1f}[/{asc}]",
                f"[{avc}]{av.verdict}[/{avc}]",
                av.rationale,
            )

        console.print(agent_table)

        # Bull/bear cases
        if v.bull_case:
            console.print(f"  [green]Bull case:[/green] {'; '.join(v.bull_case)}")
        if v.bear_case:
            console.print(f"  [red]Bear case:[/red] {'; '.join(v.bear_case)}")
        console.print()


def render_full_dashboard(verdicts: List[StockVerdict],
                          macro: MacroDashboard,
                          stock_data: Dict[str, StockData]):
    """Render the complete dashboard with all sections."""
    console.print()
    console.print(Panel(
        "[bold]PORTFOLIO ANALYZER - Multi-Agent Stock Analysis System[/bold]\n"
        "[dim]Powered by 5 scoring agents + macro overlay[/dim]",
        border_style="bold cyan",
    ))
    console.print()

    # 1. Macro environment
    render_macro_dashboard(macro)

    # 2. Main verdicts table
    render_verdicts_table(verdicts)

    # 3. Agent details
    render_agent_details(verdicts)
