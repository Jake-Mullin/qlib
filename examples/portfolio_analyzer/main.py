#!/usr/bin/env python3
"""
Portfolio Analyzer - Main Entry Point
=====================================

Usage:
  python -m examples.portfolio_analyzer.main AAPL MSFT GOOGL NVDA AMZN
  python -m examples.portfolio_analyzer.main --tickers AAPL,MSFT,GOOGL
  python -m examples.portfolio_analyzer.main --preset tech
  python -m examples.portfolio_analyzer.main --preset diversified --full

Presets:
  tech       - Big tech stocks
  diversified - Mix across sectors
  dividend   - Dividend aristocrats
  growth     - High-growth companies

Flags:
  --full         Run all analysis modules (default: summary only)
  --no-news      Skip news sentiment (faster)
  --no-insider   Skip insider trading data (faster)
  --no-corr      Skip correlation matrix (faster)
  --no-sim       Skip portfolio simulation (faster)
  --sim-only     Only run portfolio simulation
  --alerts-only  Only check alerts
"""

import argparse
import sys
import time

from rich.console import Console
from rich.panel import Panel

from .data_fetcher import fetch_all_stocks, StockData
from .scoring_agents import run_all_agents
from .verdict_system import synthesize_verdict, StockVerdict, AgentVerdict
from .valuation_engine import run_all_valuations
from .macro_tracker import fetch_macro_dashboard, get_macro_adjustment, MacroDashboard
from .dashboard import render_full_dashboard
from .sector_heatmap import render_sector_heatmap
from .portfolio_simulator import run_all_simulations
from .earnings_tracker import render_earnings_tracker
from .risk_matrix import render_correlation_matrix
from .news_sentiment import render_news_sentiment
from .insider_tracker import render_insider_tracker
from .watchlist import render_watchlist_portfolio
from .alert_system import render_alerts
from .historical_tracker import save_snapshot, init_db

console = Console()

PRESETS = {
    "tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSM", "AVGO", "MU"],
    "diversified": ["AAPL", "JPM", "JNJ", "XOM", "PG", "HD", "LLY", "V"],
    "dividend": ["KO", "PEP", "JNJ", "PG", "MMM", "ABT", "T", "XOM"],
    "growth": ["NVDA", "TSLA", "AMD", "SHOP", "SQ", "CRWD", "SNOW", "DDOG"],
}


def build_bull_bear(data: StockData, agents: list) -> tuple:
    """Generate bull and bear case bullet points."""
    bull = []
    bear = []

    for av in agents:
        if av.score >= 7.0:
            bull.append(f"{av.agent_name}: {av.rationale}")
        elif av.score <= 3.5:
            bear.append(f"{av.agent_name}: {av.rationale}")

    if data.revenue_growth and data.revenue_growth > 0.15:
        bull.append(f"Revenue growing {data.revenue_growth:.0%}")
    if data.profit_margin and data.profit_margin > 0.2:
        bull.append(f"Healthy {data.profit_margin:.0%} profit margin")
    if data.debt_to_equity and data.debt_to_equity < 30:
        bull.append("Conservative balance sheet")

    if data.pe_ratio and data.pe_ratio > 40:
        bear.append(f"Expensive at {data.pe_ratio:.0f}x earnings")
    if data.revenue_growth and data.revenue_growth < 0:
        bear.append("Revenue is declining")
    if data.debt_to_equity and data.debt_to_equity > 200:
        bear.append(f"Heavy debt load ({data.debt_to_equity:.0f}% D/E)")

    return bull[:4], bear[:4]


def analyze_stocks(tickers: list) -> tuple:
    """Run the full analysis pipeline. Returns (verdicts, macro, stock_data)."""
    # Fetch macro environment
    console.print(Panel("[bold]Fetching macro environment...[/bold]", border_style="cyan"))
    macro = fetch_macro_dashboard()
    macro_adj = get_macro_adjustment(macro)

    # Fetch stock data
    console.print(Panel(f"[bold]Fetching data for {len(tickers)} stocks...[/bold]",
                        border_style="cyan"))
    stock_data = fetch_all_stocks(tickers)

    # Score each stock with multi-method valuation
    verdicts = []
    for ticker, data in stock_data.items():
        if data.fetch_error:
            console.print(f"[red]Error fetching {ticker}: {data.fetch_error}[/red]")
            continue
        if data.current_price <= 0:
            console.print(f"[yellow]Skipping {ticker}: no price data[/yellow]")
            continue

        agents = run_all_agents(data)
        bull, bear = build_bull_bear(data, agents)

        # Run multi-method intrinsic valuation (DCF, Graham, PEG, EV/EBITDA, P/B)
        stock_val = run_all_valuations(data)
        fair_value = stock_val.composite_fair_value  # Confidence-weighted average

        verdict = synthesize_verdict(
            ticker=ticker,
            company_name=data.company_name,
            sector=data.sector,
            current_price=data.current_price,
            agent_verdicts=agents,
            valuation_score=next((a.score for a in agents if a.agent_name == "Valuation"), 5.0),
            quality_score=next((a.score for a in agents if a.agent_name == "Quality"), 5.0),
            momentum_score=next((a.score for a in agents if a.agent_name == "Momentum"), 5.0),
            macro_adjustment=macro_adj,
            one_year_target=data.analyst_target,
            fair_value=fair_value,
            next_earnings=data.next_earnings,
            bull_case=bull,
            bear_case=bear,
        )
        verdicts.append(verdict)

    return verdicts, macro, stock_data


def main():
    parser = argparse.ArgumentParser(description="Portfolio Analyzer")
    parser.add_argument("tickers", nargs="*", help="Stock tickers to analyze")
    parser.add_argument("--tickers", dest="ticker_str", help="Comma-separated tickers")
    parser.add_argument("--preset", choices=PRESETS.keys(), help="Use a preset portfolio")
    parser.add_argument("--full", action="store_true", help="Run all analysis modules")
    parser.add_argument("--no-news", action="store_true", help="Skip news sentiment")
    parser.add_argument("--no-insider", action="store_true", help="Skip insider data")
    parser.add_argument("--no-corr", action="store_true", help="Skip correlation matrix")
    parser.add_argument("--no-sim", action="store_true", help="Skip simulation")
    parser.add_argument("--sim-only", action="store_true", help="Only run simulation")
    parser.add_argument("--alerts-only", action="store_true", help="Only check alerts")

    args = parser.parse_args()

    # Resolve tickers
    tickers = []
    if args.preset:
        tickers = PRESETS[args.preset]
    elif args.ticker_str:
        tickers = [t.strip().upper() for t in args.ticker_str.split(",")]
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        console.print("[yellow]No tickers specified. Using tech preset.[/yellow]")
        tickers = PRESETS["tech"]

    start = time.time()

    # Run analysis
    verdicts, macro, stock_data = analyze_stocks(tickers)

    if not verdicts:
        console.print("[bold red]No stocks could be analyzed.[/bold red]")
        sys.exit(1)

    # Save to history
    try:
        save_snapshot(verdicts, macro)
        console.print("[dim]Snapshot saved to history database.[/dim]")
    except Exception as e:
        console.print(f"[dim]Could not save snapshot: {e}[/dim]")

    # Alerts first (always shown)
    render_alerts(verdicts)

    if args.alerts_only:
        return

    if args.sim_only:
        run_all_simulations(verdicts, stock_data)
        return

    # Core dashboard
    render_full_dashboard(verdicts, macro, stock_data)

    # Sector heatmap
    render_sector_heatmap(verdicts)

    # Watchlist / portfolio mode
    render_watchlist_portfolio(verdicts)

    # Earnings tracker
    render_earnings_tracker(verdicts, stock_data)

    if args.full or not (args.no_corr and args.no_news and args.no_insider and args.no_sim):
        # Correlation matrix
        if not args.no_corr:
            render_correlation_matrix(verdicts)

        # News sentiment
        if not args.no_news:
            render_news_sentiment(verdicts)

        # Insider trading
        if not args.no_insider:
            render_insider_tracker(verdicts)

        # Portfolio simulation
        if not args.no_sim:
            run_all_simulations(verdicts, stock_data)

    elapsed = time.time() - start
    console.print(f"\n[dim]Analysis complete in {elapsed:.1f}s[/dim]")


if __name__ == "__main__":
    main()
