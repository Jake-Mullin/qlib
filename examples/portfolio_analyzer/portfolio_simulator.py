"""
Portfolio Simulator / Backtester
--------------------------------
"If I put $10K into all Buy-rated stocks equally 6 months ago, how would I have done?"
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .data_fetcher import StockData
from .verdict_system import StockVerdict

console = Console()


@dataclass
class SimulatedPosition:
    ticker: str
    entry_price: float
    current_price: float
    shares: float
    invested: float
    current_value: float
    return_pct: float
    verdict_at_entry: str
    score_at_entry: float


@dataclass
class SimulationResult:
    strategy: str
    initial_investment: float
    current_value: float
    total_return_pct: float
    start_date: str
    end_date: str
    positions: List[SimulatedPosition] = field(default_factory=list)
    best_performer: Optional[SimulatedPosition] = None
    worst_performer: Optional[SimulatedPosition] = None
    sp500_return_pct: Optional[float] = None
    beat_market: Optional[bool] = None


def simulate_portfolio(verdicts: List[StockVerdict], stock_data: Dict[str, StockData],
                       investment: float = 10000.0, lookback_days: int = 180,
                       strategy: str = "buy_only") -> SimulationResult:
    start_date = dt.date.today() - dt.timedelta(days=lookback_days)
    end_date = dt.date.today()

    sorted_v = sorted(verdicts, key=lambda v: v.score, reverse=True)
    strategy_names = {
        "buy_only": ("Buy-Rated Only", lambda v: v.verdict == "Buy"),
        "buy_hold": ("Buy + Hold Rated", lambda v: v.verdict in ("Buy", "Hold")),
        "top_3": ("Top 3 by Score", None),
        "top_5": ("Top 5 by Score", None),
        "all": ("Equal Weight All", lambda v: True),
    }

    name, filt = strategy_names.get(strategy, ("Custom", lambda v: True))
    if strategy == "top_3":
        selected = sorted_v[:3]
    elif strategy == "top_5":
        selected = sorted_v[:5]
    else:
        selected = [v for v in sorted_v if filt(v)]

    if not selected:
        return SimulationResult(strategy=name, initial_investment=investment,
                                current_value=investment, total_return_pct=0.0,
                                start_date=start_date.isoformat(), end_date=end_date.isoformat())

    per_stock = investment / len(selected)
    positions = []
    total_value = 0.0

    for v in selected:
        entry_price = None
        if v.ticker in stock_data:
            d = stock_data[v.ticker]
            if lookback_days >= 252 and d.price_1y_ago: entry_price = d.price_1y_ago
            elif lookback_days >= 126 and d.price_6m_ago: entry_price = d.price_6m_ago
            elif lookback_days >= 63 and d.price_3m_ago: entry_price = d.price_3m_ago
            elif lookback_days >= 21 and d.price_1m_ago: entry_price = d.price_1m_ago
            elif d.price_1w_ago: entry_price = d.price_1w_ago

        if entry_price and entry_price > 0 and v.current_price > 0:
            shares = per_stock / entry_price
            current_val = shares * v.current_price
            ret_pct = ((v.current_price - entry_price) / entry_price) * 100
            positions.append(SimulatedPosition(
                ticker=v.ticker, entry_price=entry_price, current_price=v.current_price,
                shares=round(shares, 4), invested=per_stock, current_value=round(current_val, 2),
                return_pct=round(ret_pct, 2), verdict_at_entry=v.verdict, score_at_entry=v.score))
            total_value += current_val
        else:
            total_value += per_stock

    total_return = ((total_value - investment) / investment) * 100 if investment > 0 else 0
    result = SimulationResult(
        strategy=name, initial_investment=investment, current_value=round(total_value, 2),
        total_return_pct=round(total_return, 2), start_date=start_date.isoformat(),
        end_date=end_date.isoformat(), positions=positions)

    if positions:
        result.best_performer = max(positions, key=lambda p: p.return_pct)
        result.worst_performer = min(positions, key=lambda p: p.return_pct)

    try:
        sp_hist = yf.Ticker("^GSPC").history(start=start_date, end=end_date)
        if len(sp_hist) >= 2:
            sp_s = float(sp_hist["Close"].iloc[0])
            sp_e = float(sp_hist["Close"].iloc[-1])
            if sp_s > 0:
                result.sp500_return_pct = round(((sp_e - sp_s) / sp_s) * 100, 2)
                result.beat_market = result.total_return_pct > result.sp500_return_pct
    except Exception:
        pass

    return result


def render_simulation(result: SimulationResult):
    ret_color = "green" if result.total_return_pct >= 0 else "red"
    beat_str = ""
    if result.beat_market is not None:
        beat_str = ("  [bold green]BEAT MARKET[/bold green]" if result.beat_market
                    else "  [bold red]UNDERPERFORMED[/bold red]")

    header = (f"[bold]{result.strategy}[/bold]  |  "
              f"${result.initial_investment:,.0f} invested  |  "
              f"[{ret_color}]{result.total_return_pct:+.1f}%[/{ret_color}]  |  "
              f"${result.current_value:,.2f}{beat_str}")
    console.print(Panel(header, title="PORTFOLIO SIMULATOR", border_style="yellow"))

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("Ticker", style="bold cyan", width=8)
    table.add_column("Entry", justify="right", width=10)
    table.add_column("Current", justify="right", width=10)
    table.add_column("Shares", justify="right", width=8)
    table.add_column("Invested", justify="right", width=10)
    table.add_column("Value", justify="right", width=10)
    table.add_column("Return", justify="right", width=10)
    table.add_column("Verdict", justify="center", width=8)

    for p in sorted(result.positions, key=lambda x: x.return_pct, reverse=True):
        rc = "green" if p.return_pct >= 0 else "red"
        table.add_row(p.ticker, f"${p.entry_price:.2f}", f"${p.current_price:.2f}",
                      f"{p.shares:.2f}", f"${p.invested:,.2f}", f"${p.current_value:,.2f}",
                      f"[{rc}]{p.return_pct:+.1f}%[/{rc}]", p.verdict_at_entry)
    console.print(table)

    parts = [f"Period: {result.start_date} to {result.end_date}"]
    if result.best_performer:
        parts.append(f"[green]Best: {result.best_performer.ticker} ({result.best_performer.return_pct:+.1f}%)[/green]")
    if result.worst_performer:
        parts.append(f"[red]Worst: {result.worst_performer.ticker} ({result.worst_performer.return_pct:+.1f}%)[/red]")
    if result.sp500_return_pct is not None:
        parts.append(f"S&P 500: {result.sp500_return_pct:+.1f}%")
    console.print("  " + "  |  ".join(parts))
    console.print()


def run_all_simulations(verdicts: List[StockVerdict], stock_data: Dict[str, StockData],
                        investment: float = 10000.0):
    console.print(Panel("[bold]PORTFOLIO SIMULATIONS[/bold]", border_style="yellow"))

    results = []
    for strategy in ["buy_only", "top_3", "top_5", "buy_hold", "all"]:
        r = simulate_portfolio(verdicts, stock_data, investment, 180, strategy)
        results.append(r)
        render_simulation(r)

    comp = Table(title="STRATEGY COMPARISON (6-month)", box=box.ROUNDED, border_style="yellow")
    comp.add_column("Strategy", width=22)
    comp.add_column("Return", justify="right", width=10)
    comp.add_column("Final Value", justify="right", width=14)
    comp.add_column("vs S&P 500", justify="right", width=12)

    for r in sorted(results, key=lambda x: x.total_return_pct, reverse=True):
        rc = "green" if r.total_return_pct >= 0 else "red"
        vs = ""
        if r.sp500_return_pct is not None:
            d = r.total_return_pct - r.sp500_return_pct
            vs = f"[{'green' if d >= 0 else 'red'}]{d:+.1f}%[/]"
        comp.add_row(r.strategy, f"[{rc}]{r.total_return_pct:+.1f}%[/{rc}]",
                     f"${r.current_value:,.2f}", vs)
    console.print(comp)
    console.print()
