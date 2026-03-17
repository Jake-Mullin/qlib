"""
Insider Trading Tracker
-----------------------
Monitors insider buying/selling activity from SEC filings.
Uses yfinance's insider transaction data.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .verdict_system import StockVerdict

console = Console()


@dataclass
class InsiderTransaction:
    """A single insider transaction."""
    insider_name: str
    title: str
    transaction_type: str  # "Buy" / "Sell" / "Option Exercise"
    shares: int
    value: Optional[float]
    date: str


@dataclass
class InsiderSummary:
    """Aggregated insider activity for a stock."""
    ticker: str
    company_name: str
    transactions: List[InsiderTransaction] = field(default_factory=list)
    total_buys: int = 0
    total_sells: int = 0
    net_shares: int = 0  # Positive = net buying
    buy_value: float = 0.0
    sell_value: float = 0.0
    insider_signal: str = "Neutral"  # "Bullish" / "Neutral" / "Bearish"
    signal_vs_verdict: str = "N/A"
    notable_transactions: List[str] = field(default_factory=list)


def fetch_insider_data(ticker: str, company_name: str) -> InsiderSummary:
    """Fetch insider transaction data for a stock."""
    summary = InsiderSummary(ticker=ticker, company_name=company_name)

    try:
        stock = yf.Ticker(ticker)

        # Try insider_transactions (newer yfinance)
        transactions = None
        if hasattr(stock, 'insider_transactions') and stock.insider_transactions is not None:
            transactions = stock.insider_transactions
        elif hasattr(stock, 'insider_purchases') and stock.insider_purchases is not None:
            transactions = stock.insider_purchases

        if transactions is not None and not transactions.empty:
            for _, row in transactions.head(20).iterrows():
                # Parse transaction type
                text = str(row.get("Text", row.get("Transaction", ""))).lower()
                if "purchase" in text or "buy" in text:
                    tx_type = "Buy"
                elif "sale" in text or "sell" in text:
                    tx_type = "Sell"
                elif "option" in text or "exercise" in text:
                    tx_type = "Option Exercise"
                else:
                    tx_type = "Other"

                shares = abs(int(row.get("Shares", row.get("shares", 0)) or 0))
                value = None
                if "Value" in row.index:
                    try:
                        value = abs(float(row["Value"]))
                    except (ValueError, TypeError):
                        pass

                name = str(row.get("Insider", row.get("insider", "Unknown")))
                title = str(row.get("Title", row.get("Relationship", "")))
                date_val = row.get("Start Date", row.get("Date", ""))
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)[:10]

                tx = InsiderTransaction(
                    insider_name=name[:30],
                    title=title[:20],
                    transaction_type=tx_type,
                    shares=shares,
                    value=value,
                    date=date_str,
                )
                summary.transactions.append(tx)

                if tx_type == "Buy":
                    summary.total_buys += 1
                    summary.net_shares += shares
                    if value:
                        summary.buy_value += value
                elif tx_type == "Sell":
                    summary.total_sells += 1
                    summary.net_shares -= shares
                    if value:
                        summary.sell_value += value

            # Determine signal
            if summary.total_buys > 0 and summary.total_buys > summary.total_sells:
                summary.insider_signal = "Bullish"
            elif summary.total_sells > summary.total_buys * 2:
                summary.insider_signal = "Bearish"
            else:
                summary.insider_signal = "Neutral"

            # Notable transactions (large buys)
            for tx in summary.transactions:
                if tx.transaction_type == "Buy" and tx.value and tx.value > 100000:
                    summary.notable_transactions.append(
                        f"{tx.insider_name} ({tx.title}) bought ${tx.value:,.0f} worth on {tx.date}"
                    )
                elif tx.transaction_type == "Sell" and tx.value and tx.value > 1000000:
                    summary.notable_transactions.append(
                        f"{tx.insider_name} ({tx.title}) sold ${tx.value:,.0f} worth on {tx.date}"
                    )

    except Exception:
        pass

    return summary


def render_insider_tracker(verdicts: List[StockVerdict]):
    """Render insider trading dashboard."""
    console.print(Panel("[bold]Fetching insider trading data...[/bold]", border_style="magenta"))

    summaries = []
    for v in verdicts:
        s = fetch_insider_data(v.ticker, v.company_name)

        # Compare insider signal with verdict
        verdict_bull = v.verdict in ("Buy", "Hold")
        insider_bull = s.insider_signal == "Bullish"
        insider_bear = s.insider_signal == "Bearish"

        if s.insider_signal == "Neutral":
            s.signal_vs_verdict = "N/A"
        elif (verdict_bull and insider_bull) or (not verdict_bull and insider_bear):
            s.signal_vs_verdict = "Aligned"
        else:
            s.signal_vs_verdict = "Divergent"

        summaries.append((v, s))

    # Summary table
    table = Table(title="INSIDER TRADING TRACKER", box=box.ROUNDED,
                  border_style="magenta", title_style="bold magenta")
    table.add_column("Ticker", style="bold cyan", width=8)
    table.add_column("Company", width=18)
    table.add_column("Buys", justify="center", width=6)
    table.add_column("Sells", justify="center", width=6)
    table.add_column("Net Shares", justify="right", width=12)
    table.add_column("Buy Value", justify="right", width=12)
    table.add_column("Sell Value", justify="right", width=12)
    table.add_column("Signal", justify="center", width=10)
    table.add_column("vs Verdict", justify="center", width=12)

    for v, s in summaries:
        signal_c = {"Bullish": "green", "Neutral": "yellow", "Bearish": "red"}.get(s.insider_signal, "white")
        vs_c = {"Aligned": "green", "Divergent": "bold red", "N/A": "dim"}.get(s.signal_vs_verdict, "white")
        net_c = "green" if s.net_shares > 0 else "red" if s.net_shares < 0 else "dim"

        table.add_row(
            s.ticker,
            s.company_name[:18],
            f"[green]{s.total_buys}[/green]" if s.total_buys > 0 else "[dim]0[/dim]",
            f"[red]{s.total_sells}[/red]" if s.total_sells > 0 else "[dim]0[/dim]",
            f"[{net_c}]{s.net_shares:+,}[/{net_c}]" if s.net_shares != 0 else "[dim]0[/dim]",
            f"${s.buy_value:,.0f}" if s.buy_value > 0 else "[dim]$0[/dim]",
            f"${s.sell_value:,.0f}" if s.sell_value > 0 else "[dim]$0[/dim]",
            f"[{signal_c}]{s.insider_signal}[/{signal_c}]",
            f"[{vs_c}]{s.signal_vs_verdict}[/{vs_c}]",
        )

    console.print(table)

    # Notable transactions
    all_notable = []
    for v, s in summaries:
        for note in s.notable_transactions:
            all_notable.append(f"[bold cyan]{s.ticker}[/bold cyan]: {note}")

    if all_notable:
        console.print(Panel(
            "\n".join(all_notable[:10]),
            title="NOTABLE INSIDER TRANSACTIONS",
            border_style="magenta",
        ))

    # Divergence alerts
    divergent = [(v, s) for v, s in summaries if s.signal_vs_verdict == "Divergent"]
    if divergent:
        console.print(Panel(
            "\n".join(
                f"[bold yellow]  {s.ticker}[/bold yellow]: Insiders are "
                f"[{{'Bullish': 'green', 'Bearish': 'red'}}.get(s.insider_signal, 'white')]{s.insider_signal}[/] "
                f"but verdict is {v.verdict}"
                for v, s in divergent
            ),
            title="INSIDER / VERDICT DIVERGENCES",
            border_style="yellow",
        ))

    console.print()
