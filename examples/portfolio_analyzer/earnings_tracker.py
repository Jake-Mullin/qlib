"""
Earnings Impact Tracker
-----------------------
Tracks how stocks perform around earnings events.
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
from .historical_tracker import record_earnings_event, get_earnings_history

console = Console()


@dataclass
class EarningsAnalysis:
    ticker: str
    company_name: str
    next_earnings: Optional[dt.date]
    countdown_days: Optional[int]
    total_events: int = 0
    avg_price_change: float = 0.0
    positive_surprises: int = 0
    negative_surprises: int = 0
    avg_positive_move: float = 0.0
    avg_negative_move: float = 0.0
    predictability: str = "Unknown"
    pre_earnings_verdict: str = ""
    pre_earnings_score: float = 0.0
    implied_move: Optional[float] = None


def check_recent_earnings(ticker: str, stock_data: StockData,
                          verdict: StockVerdict, db_path: str = None) -> bool:
    """Check if earnings recently passed and record the event."""
    try:
        stock = yf.Ticker(ticker)
        cal = stock.calendar
        if cal is None:
            return False

        earnings_date = None
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed and len(ed) > 0:
                raw = ed[0]
                earnings_date = raw.date() if isinstance(raw, dt.datetime) else raw if isinstance(raw, dt.date) else None

        if earnings_date is None:
            return False

        days_since = (dt.date.today() - earnings_date).days
        if 0 <= days_since <= 7:
            pre_date = earnings_date - dt.timedelta(days=1)
            post_date = earnings_date + dt.timedelta(days=1)
            hist = stock.history(start=pre_date - dt.timedelta(days=3),
                                end=post_date + dt.timedelta(days=3))
            if len(hist) >= 2:
                kwargs = {"db_path": db_path} if db_path else {}
                record_earnings_event(
                    ticker=ticker, earnings_date=earnings_date.isoformat(),
                    pre_price=float(hist["Close"].iloc[0]),
                    post_price=float(hist["Close"].iloc[-1]),
                    pre_score=verdict.score, pre_verdict=verdict.verdict, **kwargs)
                return True
    except Exception:
        pass
    return False


def analyze_earnings_history(ticker: str, company_name: str,
                             verdict: StockVerdict, db_path: str = None) -> EarningsAnalysis:
    kwargs = {"db_path": db_path} if db_path else {}
    history = get_earnings_history(ticker, **kwargs)

    analysis = EarningsAnalysis(
        ticker=ticker, company_name=company_name,
        next_earnings=verdict.next_earnings, countdown_days=verdict.earnings_countdown,
        pre_earnings_verdict=verdict.verdict, pre_earnings_score=verdict.score)

    if not history:
        return analysis

    analysis.total_events = len(history)
    changes = [h["price_change_pct"] for h in history if h["price_change_pct"] is not None]

    if changes:
        analysis.avg_price_change = sum(changes) / len(changes)
        positives = [c for c in changes if c > 0]
        negatives = [c for c in changes if c < 0]
        analysis.positive_surprises = len(positives)
        analysis.negative_surprises = len(negatives)
        analysis.avg_positive_move = sum(positives) / len(positives) if positives else 0
        analysis.avg_negative_move = sum(negatives) / len(negatives) if negatives else 0

        if len(changes) >= 3:
            consistency = max(len(positives), len(negatives)) / len(changes)
            if consistency >= 0.75: analysis.predictability = "High"
            elif consistency >= 0.5: analysis.predictability = "Medium"
            else: analysis.predictability = "Low"

        analysis.implied_move = round(analysis.avg_price_change, 2)

    return analysis


def render_earnings_tracker(verdicts: List[StockVerdict],
                            stock_data: Dict[str, StockData],
                            db_path: str = None):
    kwargs = {"db_path": db_path} if db_path else {}
    for v in verdicts:
        if v.ticker in stock_data:
            check_recent_earnings(v.ticker, stock_data[v.ticker], v, **kwargs)

    upcoming = sorted(
        [v for v in verdicts if v.earnings_countdown is not None and v.earnings_countdown >= 0],
        key=lambda v: v.earnings_countdown)

    table = Table(title="EARNINGS IMPACT TRACKER", box=box.ROUNDED,
                  border_style="yellow", title_style="bold yellow")
    table.add_column("Ticker", style="bold cyan", width=8)
    table.add_column("Company", width=18)
    table.add_column("Earnings", justify="center", width=12)
    table.add_column("Countdown", justify="center", width=10)
    table.add_column("Verdict", justify="center", width=8)
    table.add_column("Score", justify="center", width=7)
    table.add_column("Hist Events", justify="center", width=10)
    table.add_column("Avg Move", justify="right", width=9)
    table.add_column("Win Rate", justify="center", width=9)
    table.add_column("Predictability", justify="center", width=13)

    for v in upcoming:
        a = analyze_earnings_history(v.ticker, v.company_name, v, **kwargs)

        if v.earnings_countdown <= 2: cd = f"[bold red]{v.earnings_countdown}d !!![/bold red]"
        elif v.earnings_countdown <= 7: cd = f"[red]{v.earnings_countdown}d[/red]"
        elif v.earnings_countdown <= 14: cd = f"[yellow]{v.earnings_countdown}d[/yellow]"
        else: cd = f"{v.earnings_countdown}d"

        if a.total_events > 0:
            avg_c = "green" if a.avg_price_change >= 0 else "red"
            avg_str = f"[{avg_c}]{a.avg_price_change:+.1f}%[/{avg_c}]"
            total = a.positive_surprises + a.negative_surprises
            win = f"{a.positive_surprises}/{total}" if total > 0 else "N/A"
            pc = {"High": "green", "Medium": "yellow", "Low": "red"}.get(a.predictability, "white")
            pred = f"[{pc}]{a.predictability}[/{pc}]"
        else:
            avg_str, win, pred = "N/A", "N/A", "[dim]No data[/dim]"

        vc = {"Buy": "green", "Hold": "yellow", "Pass": "bright_black", "Avoid": "red"}.get(v.verdict, "white")
        table.add_row(v.ticker, v.company_name[:18],
                      v.next_earnings.strftime("%b %d") if v.next_earnings else "TBD",
                      cd, f"[{vc}]{v.verdict}[/{vc}]", f"{v.score:.1f}",
                      str(a.total_events), avg_str, win, pred)

    console.print(table)
    console.print()
