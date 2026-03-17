#!/usr/bin/env python3
"""
Ultimate Stock Portfolio Analyzer
==================================
Run this script to analyze your portfolio with 7 legendary investor agents,
multiple valuation methodologies, macro tracking, and a Rich CLI dashboard.

Usage:
    python -m examples.portfolio_analyzer.run_analyzer
    python -m examples.portfolio_analyzer.run_analyzer --tickers AAPL MSFT NVDA
    python -m examples.portfolio_analyzer.run_analyzer --no-details
    python -m examples.portfolio_analyzer.run_analyzer --export results.json

Requirements:
    pip install yfinance rich
"""

import argparse
import json
import sys
import datetime as dt
from typing import Dict, List

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .data_fetcher import fetch_stock_data, StockData
from .valuation_engine import run_all_valuations, StockValuation
from .investor_agents import run_all_agents, consensus_verdict, AgentVerdict
from .macro_tracker import run_macro_dashboard, MacroDashboard
from .verdict_system import build_verdict, StockVerdict
from .dashboard import render_full_dashboard

console = Console()

# Default portfolio
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "MU", "AMD", "CRM"]


def analyze_portfolio(tickers: List[str], show_details: bool = True,
                      export_path: str = None, notion_api_key: str = None,
                      notion_db_id: str = None) -> List[StockVerdict]:
    """Run the full analysis pipeline."""
    console.print("\n[bold blue]ULTIMATE STOCK PORTFOLIO ANALYZER[/bold blue]")
    console.print(f"[dim]Analyzing {len(tickers)} stocks: {', '.join(tickers)}[/dim]\n")

    # Step 1: Macro environment
    console.print("[bold cyan]Step 1/4:[/bold cyan] Scanning macroeconomic environment...")
    macro = run_macro_dashboard()
    console.print(f"  Macro signal: [bold]{macro.overall_signal}[/bold] ({macro.overall_score:.1f}/10)\n")

    # Step 2: Fetch stock data
    console.print("[bold cyan]Step 2/4:[/bold cyan] Fetching stock data from Yahoo Finance...")
    stock_data: Dict[str, StockData] = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching stocks...", total=len(tickers))
        for ticker in tickers:
            progress.update(task, description=f"Fetching {ticker}...")
            try:
                stock_data[ticker] = fetch_stock_data(ticker)
            except Exception as e:
                console.print(f"  [red]Error fetching {ticker}: {e}[/red]")
            progress.advance(task)

    console.print(f"  Successfully fetched {len(stock_data)}/{len(tickers)} stocks\n")

    # Step 3: Run valuations + investor agents
    console.print("[bold cyan]Step 3/4:[/bold cyan] Running valuations & investor agents...")
    valuations: Dict[str, StockValuation] = {}
    agent_results: Dict[str, List[AgentVerdict]] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing...", total=len(stock_data))
        for ticker, data in stock_data.items():
            progress.update(task, description=f"Analyzing {ticker}...")
            valuations[ticker] = run_all_valuations(data)
            agent_results[ticker] = run_all_agents(data, valuations[ticker])
            progress.advance(task)

    console.print("  All 7 investor agents have evaluated every stock\n")

    # Step 4: Build verdicts
    console.print("[bold cyan]Step 4/4:[/bold cyan] Computing final verdicts...")
    verdicts: List[StockVerdict] = []
    for ticker, data in stock_data.items():
        verdict = build_verdict(data, valuations[ticker], agent_results[ticker], macro)
        verdicts.append(verdict)

    # Sort by score
    verdicts.sort(key=lambda v: v.score, reverse=True)

    # Summary stats
    buys = sum(1 for v in verdicts if v.verdict == "Buy")
    holds = sum(1 for v in verdicts if v.verdict == "Hold")
    passes = sum(1 for v in verdicts if v.verdict == "Pass")
    avoids = sum(1 for v in verdicts if v.verdict == "Avoid")
    console.print(f"  Results: [green]{buys} Buy[/green] | [yellow]{holds} Hold[/yellow] | "
                  f"[bright_black]{passes} Pass[/bright_black] | [red]{avoids} Avoid[/red]\n")

    # Render the dashboard
    render_full_dashboard(verdicts, stock_data, macro, show_details=show_details)

    # Export if requested
    if export_path:
        export_results(verdicts, macro, export_path)

    # Push to Notion if configured
    if notion_api_key and notion_db_id:
        try:
            from .notion_integration import push_to_notion
            console.print("\n[bold cyan]Pushing to Notion...[/bold cyan]")
            push_to_notion(notion_api_key, notion_db_id, verdicts, macro)
            console.print("[green]Notion database updated![/green]")
        except Exception as e:
            console.print(f"[red]Notion update failed: {e}[/red]")

    return verdicts


def export_results(verdicts: List[StockVerdict], macro: MacroDashboard, path: str):
    """Export results to JSON for n8n or other automation."""
    output = {
        "generated_at": dt.datetime.now().isoformat(),
        "macro": {
            "overall_signal": macro.overall_signal,
            "overall_score": macro.overall_score,
            "recession_probability": macro.recession_probability,
            "indicators": [
                {"name": s.name, "value": s.value, "signal": s.signal, "description": s.description}
                for s in macro.signals
            ],
        },
        "portfolio": [],
    }

    for v in verdicts:
        stock = {
            "ticker": v.ticker,
            "company": v.company_name,
            "sector": v.sector,
            "price": v.current_price,
            "score": v.score,
            "verdict": v.verdict,
            "one_year_target": v.one_year_target,
            "upside_pct": v.upside_pct,
            "next_earnings": v.next_earnings.isoformat() if v.next_earnings else None,
            "earnings_countdown_days": v.earnings_countdown,
            "component_scores": {
                "valuation": v.valuation_score,
                "quality": v.quality_score,
                "agent_consensus": v.agent_consensus_score,
                "momentum": v.momentum_score,
                "macro_adjustment": v.macro_adjustment,
            },
            "agent_verdicts": [
                {
                    "agent": av.agent_name,
                    "style": av.agent_style,
                    "score": av.score,
                    "verdict": av.verdict,
                    "price_target": av.price_target,
                    "conviction": av.conviction,
                    "reasoning": av.reasoning,
                }
                for av in v.agent_verdicts
            ],
            "valuations": [
                {
                    "method": vr.method,
                    "fair_value": vr.fair_value,
                    "upside_pct": vr.upside_pct,
                    "confidence": vr.confidence,
                    "notes": vr.notes,
                }
                for vr in (v.valuation.valuations if v.valuation else [])
            ],
            "bull_case": v.bull_case,
            "bear_case": v.bear_case,
        }
        output["portfolio"].append(stock)

    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    console.print(f"\n[green]Results exported to {path}[/green]")


def main():
    parser = argparse.ArgumentParser(description="Ultimate Stock Portfolio Analyzer")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS,
                        help="Stock tickers to analyze (default: tech-heavy portfolio)")
    parser.add_argument("--no-details", action="store_true",
                        help="Skip individual stock deep dives")
    parser.add_argument("--export", type=str, default=None,
                        help="Export results to JSON file (for n8n automation)")
    parser.add_argument("--notion-key", type=str, default=None,
                        help="Notion API key (or set NOTION_API_KEY env var)")
    parser.add_argument("--notion-db", type=str, default=None,
                        help="Notion database ID (or set NOTION_DATABASE_ID env var)")
    args = parser.parse_args()

    import os
    notion_key = args.notion_key or os.environ.get("NOTION_API_KEY")
    notion_db = args.notion_db or os.environ.get("NOTION_DATABASE_ID")

    analyze_portfolio(
        tickers=args.tickers,
        show_details=not args.no_details,
        export_path=args.export,
        notion_api_key=notion_key,
        notion_db_id=notion_db,
    )


if __name__ == "__main__":
    main()
