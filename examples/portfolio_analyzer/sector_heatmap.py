"""
Sector Heatmap
--------------
Visual sector-level summary showing which sectors are bullish/bearish.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

from rich.console import Console
from rich.table import Table
from rich import box

from .verdict_system import StockVerdict

console = Console()


@dataclass
class SectorSummary:
    sector: str
    stocks: List[str] = field(default_factory=list)
    avg_score: float = 0.0
    signal: str = "Neutral"
    buy_count: int = 0
    hold_count: int = 0
    pass_count: int = 0
    avoid_count: int = 0
    avg_upside: float = 0.0
    top_pick: str = ""
    top_pick_score: float = 0.0


def build_sector_heatmap(verdicts: List[StockVerdict]) -> List[SectorSummary]:
    sectors: Dict[str, List[StockVerdict]] = defaultdict(list)
    for v in verdicts:
        sectors[v.sector if v.sector else "Unknown"].append(v)

    summaries = []
    for sector, stocks in sorted(sectors.items()):
        s = SectorSummary(sector=sector)
        s.stocks = [v.ticker for v in stocks]
        s.avg_score = sum(v.score for v in stocks) / len(stocks)

        for v in stocks:
            if v.verdict == "Buy": s.buy_count += 1
            elif v.verdict == "Hold": s.hold_count += 1
            elif v.verdict == "Pass": s.pass_count += 1
            else: s.avoid_count += 1

        upsides = [v.upside_pct for v in stocks if v.upside_pct is not None]
        s.avg_upside = sum(upsides) / len(upsides) if upsides else 0.0

        top = max(stocks, key=lambda v: v.score)
        s.top_pick = top.ticker
        s.top_pick_score = top.score

        if s.avg_score >= 7.0: s.signal = "Bullish"
        elif s.avg_score >= 5.5: s.signal = "Neutral"
        elif s.avg_score >= 3.5: s.signal = "Cautious"
        else: s.signal = "Bearish"

        summaries.append(s)

    return sorted(summaries, key=lambda s: s.avg_score, reverse=True)


def _heat_color(score: float) -> str:
    if score >= 8.0: return "bold green"
    elif score >= 7.0: return "green"
    elif score >= 6.0: return "yellow"
    elif score >= 5.0: return "bright_black"
    elif score >= 4.0: return "red"
    return "bold red"


def _heat_bar(score: float, width: int = 20) -> str:
    filled = int((score / 10) * width)
    empty = width - filled
    color = _heat_color(score)
    return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"


def render_sector_heatmap(verdicts: List[StockVerdict]):
    summaries = build_sector_heatmap(verdicts)

    table = Table(title="SECTOR HEATMAP", box=box.ROUNDED, border_style="green",
                  title_style="bold green")
    table.add_column("Sector", style="bold", width=22)
    table.add_column("Signal", justify="center", width=10)
    table.add_column("Avg Score", justify="center", width=10)
    table.add_column("Heat", width=22)
    table.add_column("B/H/P/A", justify="center", width=10)
    table.add_column("Avg Upside", justify="right", width=10)
    table.add_column("Top Pick", justify="center", width=12)
    table.add_column("Stocks", width=20)

    for s in summaries:
        sc = _heat_color(s.avg_score)
        sig_c = {"Bullish": "bold green", "Neutral": "yellow", "Cautious": "bright_black",
                 "Bearish": "bold red"}.get(s.signal, "white")
        up_c = "green" if s.avg_upside >= 0 else "red"

        table.add_row(
            s.sector,
            f"[{sig_c}]{s.signal}[/{sig_c}]",
            f"[{sc}]{s.avg_score:.1f}/10[/{sc}]",
            _heat_bar(s.avg_score),
            f"[green]{s.buy_count}[/green]/[yellow]{s.hold_count}[/yellow]/[bright_black]{s.pass_count}[/bright_black]/[red]{s.avoid_count}[/red]",
            f"[{up_c}]{s.avg_upside:+.1f}%[/{up_c}]",
            f"[bold cyan]{s.top_pick}[/bold cyan] ({s.top_pick_score:.1f})",
            ", ".join(s.stocks),
        )

    console.print(table)
    console.print()
