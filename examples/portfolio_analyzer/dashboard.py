"""
Rich CLI Dashboard
------------------
Beautiful terminal output with colored tables, panels, and verdict tabs.
Uses the Rich library for formatting.
"""

from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.layout import Layout
from rich import box

from .data_fetcher import StockData, get_price_change
from .valuation_engine import StockValuation
from .investor_agents import AgentVerdict
from .macro_tracker import MacroDashboard
from .verdict_system import StockVerdict

console = Console()


def _verdict_color(verdict: str) -> str:
    return {"Buy": "bold green", "Hold": "bold yellow", "Pass": "bold bright_black", "Avoid": "bold red"}.get(verdict, "white")


def _score_color(score: float) -> str:
    if score >= 7.5:
        return "green"
    elif score >= 5.5:
        return "yellow"
    elif score >= 3.5:
        return "bright_black"
    else:
        return "red"


def _signal_color(signal: str) -> str:
    return {"Green": "green", "Yellow": "yellow", "Red": "red"}.get(signal, "white")


def _pct_str(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    color = "green" if val >= 0 else "red"
    return f"[{color}]{val:+.1f}%[/{color}]"


def _price_str(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    return f"${val:,.2f}"


def _fmt_large_num(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.2f}T"
    elif abs(val) >= 1e9:
        return f"${val/1e9:.2f}B"
    elif abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    else:
        return f"${val:,.0f}"


# =========================================================================
# HEADER
# =========================================================================
def render_header():
    header_text = Text()
    header_text.append("  ULTIMATE STOCK PORTFOLIO ANALYZER  ", style="bold white on blue")
    header_text.append("\n  Powered by 7 Legendary Investor Agents  ", style="dim")
    console.print(Panel(header_text, border_style="blue", padding=(1, 2)))


# =========================================================================
# MACRO DASHBOARD
# =========================================================================
def render_macro(macro: MacroDashboard):
    table = Table(title="MACROECONOMIC DASHBOARD", box=box.ROUNDED, border_style="cyan",
                  title_style="bold cyan")
    table.add_column("Indicator", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Signal", justify="center")
    table.add_column("Details")

    for s in macro.signals:
        val_str = f"{s.value:.2f}" if s.value is not None else "N/A"
        sig_style = _signal_color(s.signal)
        signal_display = f"[{sig_style}]● {s.signal}[/{sig_style}]"
        table.add_row(s.name, val_str, signal_display, s.description)

    # Overall row
    table.add_section()
    overall_color = "green" if macro.overall_signal == "Risk On" else "yellow" if macro.overall_signal == "Cautious" else "red"
    table.add_row(
        "[bold]OVERALL[/bold]",
        f"[bold]{macro.overall_score:.1f}/10[/bold]",
        f"[bold {overall_color}]{macro.overall_signal}[/bold {overall_color}]",
        f"Recession Risk: [{overall_color}]{macro.recession_probability}[/{overall_color}]"
    )

    console.print(table)
    console.print()


# =========================================================================
# PORTFOLIO SUMMARY TABLE
# =========================================================================
def render_portfolio_summary(verdicts: List[StockVerdict]):
    table = Table(title="PORTFOLIO CORE TRACKER", box=box.HEAVY_HEAD, border_style="magenta",
                  title_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Ticker", style="bold cyan", width=6)
    table.add_column("Company", width=20)
    table.add_column("Price", justify="right", width=10)
    table.add_column("Score", justify="center", width=7)
    table.add_column("Verdict", justify="center", width=8)
    table.add_column("1Y Target", justify="right", width=10)
    table.add_column("Upside", justify="right", width=8)
    table.add_column("Earnings", justify="center", width=12)
    table.add_column("Bull", justify="center", width=8)
    table.add_column("Bear", justify="center", width=8)

    # Sort by score descending
    sorted_v = sorted(verdicts, key=lambda v: v.score, reverse=True)
    for i, v in enumerate(sorted_v, 1):
        sc = _score_color(v.score)
        vc = _verdict_color(v.verdict)

        # Earnings countdown
        if v.earnings_countdown is not None:
            if v.earnings_countdown <= 7:
                earn_str = f"[bold red]{v.earnings_countdown}d[/bold red] ⏰"
            elif v.earnings_countdown <= 30:
                earn_str = f"[yellow]{v.earnings_countdown}d[/yellow]"
            else:
                earn_str = f"{v.earnings_countdown}d"
        else:
            earn_str = "TBD"

        # Find bull/bear agents
        bull_agent = max(v.agent_verdicts, key=lambda a: a.score).agent_name.split()[-1] if v.agent_verdicts else "N/A"
        bear_agent = min(v.agent_verdicts, key=lambda a: a.score).agent_name.split()[-1] if v.agent_verdicts else "N/A"

        table.add_row(
            str(i),
            v.ticker,
            v.company_name[:20],
            _price_str(v.current_price),
            f"[{sc}]{v.score:.1f}[/{sc}]",
            f"[{vc[5:] if vc.startswith('bold ') else vc}]{v.verdict}[/{vc[5:] if vc.startswith('bold ') else vc}]",
            _price_str(v.one_year_target),
            _pct_str(v.upside_pct),
            earn_str,
            f"[green]{bull_agent}[/green]",
            f"[red]{bear_agent}[/red]",
        )

    console.print(table)
    console.print()


# =========================================================================
# VERDICT TABS (Buy / Hold / Pass / Avoid)
# =========================================================================
def render_verdict_tabs(verdicts: List[StockVerdict]):
    categories = {"Buy": [], "Hold": [], "Pass": [], "Avoid": []}
    for v in verdicts:
        categories[v.verdict].append(v)

    panels = []
    for cat, color in [("Buy", "green"), ("Hold", "yellow"), ("Pass", "bright_black"), ("Avoid", "red")]:
        stocks = categories[cat]
        if stocks:
            lines = []
            for s in sorted(stocks, key=lambda x: x.score, reverse=True):
                lines.append(f"  {s.ticker:6s} {s.score:.1f}/10  {_price_str(s.one_year_target):>10s}")
            content = "\n".join(lines)
        else:
            content = "  (none)"
        panels.append(Panel(content, title=f"[bold {color}]{cat}[/bold {color}] ({len(stocks)})",
                            border_style=color, width=35, padding=(0, 1)))

    console.print(Columns(panels, equal=True, expand=True))
    console.print()


# =========================================================================
# INDIVIDUAL STOCK DEEP DIVE
# =========================================================================
def render_stock_detail(v: StockVerdict, data: StockData):
    vc = _verdict_color(v.verdict)

    # Header
    header = f"[bold]{v.ticker}[/bold] - {v.company_name}  |  {v.sector}  |  [{vc[5:] if vc.startswith('bold ') else vc}]{v.verdict} ({v.score:.1f}/10)[/{vc[5:] if vc.startswith('bold ') else vc}]"
    console.print(Panel(header, border_style="cyan"))

    # Price & Momentum table
    price_table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    price_table.add_column("Metric", width=18)
    price_table.add_column("Value", justify="right", width=12)
    price_table.add_column("Metric", width=18)
    price_table.add_column("Value", justify="right", width=12)

    price_table.add_row(
        "Current Price", _price_str(v.current_price),
        "1Y Target", _price_str(v.one_year_target),
    )
    price_table.add_row(
        "52-Week High", _price_str(data.fifty_two_week_high),
        "52-Week Low", _price_str(data.fifty_two_week_low),
    )
    price_table.add_row(
        "1M Change", _pct_str(get_price_change(data.current_price, data.price_1m_ago)),
        "3M Change", _pct_str(get_price_change(data.current_price, data.price_3m_ago)),
    )
    price_table.add_row(
        "6M Change", _pct_str(get_price_change(data.current_price, data.price_6m_ago)),
        "1Y Change", _pct_str(get_price_change(data.current_price, data.price_1y_ago)),
    )
    console.print(price_table)

    # Fundamentals
    fund_table = Table(title="Fundamentals", box=box.SIMPLE, show_header=True, header_style="bold")
    fund_table.add_column("Metric", width=18)
    fund_table.add_column("Value", justify="right", width=12)
    fund_table.add_column("Metric", width=18)
    fund_table.add_column("Value", justify="right", width=12)

    fund_table.add_row(
        "Market Cap", _fmt_large_num(data.market_cap),
        "P/E Ratio", f"{data.pe_ratio:.1f}" if data.pe_ratio else "N/A",
    )
    fund_table.add_row(
        "Forward P/E", f"{data.forward_pe:.1f}" if data.forward_pe else "N/A",
        "PEG Ratio", f"{data.peg_ratio:.2f}" if data.peg_ratio else "N/A",
    )
    fund_table.add_row(
        "P/B Ratio", f"{data.price_to_book:.1f}" if data.price_to_book else "N/A",
        "EV/EBITDA", f"{data.ev_to_ebitda:.1f}" if data.ev_to_ebitda else "N/A",
    )
    fund_table.add_row(
        "Profit Margin", f"{data.profit_margin:.1%}" if data.profit_margin else "N/A",
        "ROE", f"{data.roe:.1%}" if data.roe else "N/A",
    )
    fund_table.add_row(
        "Revenue Growth", f"{data.revenue_growth:.1%}" if data.revenue_growth else "N/A",
        "Debt/Equity", f"{data.debt_to_equity:.0f}" if data.debt_to_equity is not None else "N/A",
    )
    fund_table.add_row(
        "Free Cash Flow", _fmt_large_num(data.free_cash_flow),
        "Dividend Yield", f"{data.dividend_yield:.2%}" if data.dividend_yield else "N/A",
    )
    console.print(fund_table)

    # Valuation Methods
    if v.valuation and v.valuation.valuations:
        val_table = Table(title="Valuation Analysis", box=box.ROUNDED, border_style="blue")
        val_table.add_column("Method", width=18)
        val_table.add_column("Fair Value", justify="right", width=12)
        val_table.add_column("Upside", justify="right", width=10)
        val_table.add_column("Confidence", justify="center", width=10)
        val_table.add_column("Notes", width=35)

        for vr in v.valuation.valuations:
            val_table.add_row(
                vr.method,
                _price_str(vr.fair_value),
                _pct_str(vr.upside_pct),
                vr.confidence,
                vr.notes,
            )

        if v.valuation.composite_fair_value:
            val_table.add_section()
            val_table.add_row(
                "[bold]COMPOSITE[/bold]",
                f"[bold]{_price_str(v.valuation.composite_fair_value)}[/bold]",
                f"[bold]{_pct_str(v.valuation.composite_upside)}[/bold]",
                "[bold]Weighted[/bold]",
                "",
            )
        console.print(val_table)

    # Investor Agent Verdicts
    agent_table = Table(title="Legendary Investor Agents", box=box.ROUNDED, border_style="magenta")
    agent_table.add_column("Investor", width=16)
    agent_table.add_column("Style", width=24)
    agent_table.add_column("Score", justify="center", width=7)
    agent_table.add_column("Verdict", justify="center", width=8)
    agent_table.add_column("Target", justify="right", width=10)
    agent_table.add_column("Key Reasoning", width=45)

    for av in sorted(v.agent_verdicts, key=lambda a: a.score, reverse=True):
        sc = _score_color(av.score)
        vc_inner = _verdict_color(av.verdict)
        reasoning = av.reasoning[0] if av.reasoning else ""
        agent_table.add_row(
            av.agent_name,
            av.agent_style,
            f"[{sc}]{av.score:.1f}[/{sc}]",
            f"[{vc_inner[5:] if vc_inner.startswith('bold ') else vc_inner}]{av.verdict}[/{vc_inner[5:] if vc_inner.startswith('bold ') else vc_inner}]",
            _price_str(av.price_target),
            reasoning[:45],
        )
    console.print(agent_table)

    # Score Breakdown
    breakdown = Table(title="Score Breakdown", box=box.SIMPLE)
    breakdown.add_column("Component", width=20)
    breakdown.add_column("Score", justify="center", width=8)
    breakdown.add_column("Weight", justify="center", width=8)

    breakdown.add_row("Valuation", f"{v.valuation_score:.1f}", "25%")
    breakdown.add_row("Quality", f"{v.quality_score:.1f}", "25%")
    breakdown.add_row("Agent Consensus", f"{v.agent_consensus_score:.1f}", "25%")
    breakdown.add_row("Momentum", f"{v.momentum_score:.1f}", "15%")
    breakdown.add_row("Macro Adjustment", f"{v.macro_adjustment:+.1f}", "10%")
    breakdown.add_section()
    sc = _score_color(v.score)
    breakdown.add_row("[bold]FINAL SCORE[/bold]", f"[bold {sc}]{v.score:.1f}/10[/bold {sc}]", "")

    console.print(breakdown)

    # Bull / Bear Case
    if v.bull_case or v.bear_case:
        cases = ""
        if v.bull_case:
            cases += "[green]BULL CASE:[/green]\n"
            for b in v.bull_case:
                cases += f"  + {b}\n"
        if v.bear_case:
            cases += "[red]BEAR CASE:[/red]\n"
            for b in v.bear_case:
                cases += f"  - {b}\n"
        console.print(Panel(cases.strip(), title="Investment Thesis", border_style="white"))

    console.print("─" * 80)
    console.print()


# =========================================================================
# EARNINGS CALENDAR
# =========================================================================
def render_earnings_calendar(verdicts: List[StockVerdict]):
    table = Table(title="EARNINGS CALENDAR & COUNTDOWN", box=box.ROUNDED, border_style="yellow",
                  title_style="bold yellow")
    table.add_column("Ticker", style="bold cyan", width=8)
    table.add_column("Company", width=22)
    table.add_column("Earnings Date", justify="center", width=14)
    table.add_column("Countdown", justify="center", width=12)
    table.add_column("Verdict", justify="center", width=8)

    # Sort by earnings date
    with_dates = [v for v in verdicts if v.next_earnings is not None]
    without_dates = [v for v in verdicts if v.next_earnings is None]
    sorted_v = sorted(with_dates, key=lambda v: v.next_earnings) + without_dates

    for v in sorted_v:
        if v.next_earnings:
            date_str = v.next_earnings.strftime("%b %d, %Y")
            if v.earnings_countdown is not None:
                if v.earnings_countdown <= 7:
                    cd_str = f"[bold red]{v.earnings_countdown} days ⏰[/bold red]"
                elif v.earnings_countdown <= 14:
                    cd_str = f"[yellow]{v.earnings_countdown} days[/yellow]"
                elif v.earnings_countdown <= 30:
                    cd_str = f"[yellow]{v.earnings_countdown} days[/yellow]"
                else:
                    cd_str = f"{v.earnings_countdown} days"
            else:
                cd_str = "Passed"
        else:
            date_str = "TBD"
            cd_str = "—"

        vc = _verdict_color(v.verdict)
        table.add_row(
            v.ticker,
            v.company_name[:22],
            date_str,
            cd_str,
            f"[{vc[5:] if vc.startswith('bold ') else vc}]{v.verdict}[/{vc[5:] if vc.startswith('bold ') else vc}]",
        )

    console.print(table)
    console.print()


# =========================================================================
# FULL DASHBOARD RENDER
# =========================================================================
def render_full_dashboard(verdicts: List[StockVerdict], stock_data: Dict[str, StockData],
                          macro: MacroDashboard, show_details: bool = True):
    """Render the complete portfolio analysis dashboard."""
    console.clear()
    render_header()
    console.print()

    # Macro overview
    render_macro(macro)

    # Portfolio summary
    render_portfolio_summary(verdicts)

    # Verdict tabs
    render_verdict_tabs(verdicts)

    # Earnings calendar
    render_earnings_calendar(verdicts)

    # Individual deep dives
    if show_details:
        console.print(Panel("[bold]INDIVIDUAL STOCK DEEP DIVES[/bold]", border_style="cyan"))
        console.print()
        for v in sorted(verdicts, key=lambda x: x.score, reverse=True):
            render_stock_detail(v, stock_data[v.ticker])

    # Footer
    console.print(Panel(
        "[dim]Analysis is for informational purposes only. Not financial advice. "
        "Do your own research before making investment decisions.[/dim]",
        border_style="dim"
    ))
