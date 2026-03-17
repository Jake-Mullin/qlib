"""
Risk Correlation Matrix
-----------------------
Shows how correlated portfolio stocks are to each other.
Helps identify concentration risk: "Am I just betting on tech 5 different ways?"
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from .verdict_system import StockVerdict

console = Console()


@dataclass
class CorrelationPair:
    """A pair of stocks with their correlation."""
    ticker_a: str
    ticker_b: str
    correlation: float
    risk_level: str  # "Low" / "Medium" / "High"


@dataclass
class RiskProfile:
    """Overall portfolio risk assessment."""
    avg_correlation: float
    max_correlation: float
    max_corr_pair: Tuple[str, str]
    min_correlation: float
    min_corr_pair: Tuple[str, str]
    diversification_score: float  # 0-10, higher is better
    risk_level: str  # "Well Diversified" / "Moderately Concentrated" / "Highly Concentrated"
    sector_concentration: Dict[str, int] = field(default_factory=dict)
    cluster_warnings: List[str] = field(default_factory=list)


def _fetch_returns(tickers: List[str], period: str = "6mo") -> Optional[Dict[str, List[float]]]:
    """Fetch daily returns for a list of tickers."""
    try:
        data = yf.download(tickers, period=period, progress=False)
        if data.empty:
            return None

        if "Close" in data.columns:
            close = data["Close"]
        elif "Adj Close" in data.columns:
            close = data["Adj Close"]
        else:
            close = data

        # Handle single ticker case
        if isinstance(close, (list,)):
            return None

        returns = close.pct_change().dropna()
        if returns.empty:
            return None

        result = {}
        if len(tickers) == 1:
            result[tickers[0]] = returns.tolist()
        else:
            for t in tickers:
                if t in returns.columns:
                    vals = returns[t].dropna().tolist()
                    if vals:
                        result[t] = vals
        return result if result else None
    except Exception:
        return None


def _compute_correlation(returns_a: List[float], returns_b: List[float]) -> float:
    """Compute Pearson correlation between two return series."""
    n = min(len(returns_a), len(returns_b))
    if n < 10:
        return 0.0

    a = returns_a[:n]
    b = returns_b[:n]

    mean_a = sum(a) / n
    mean_b = sum(b) / n

    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / n
    std_a = (sum((x - mean_a) ** 2 for x in a) / n) ** 0.5
    std_b = (sum((x - mean_b) ** 2 for x in b) / n) ** 0.5

    if std_a == 0 or std_b == 0:
        return 0.0
    return cov / (std_a * std_b)


def build_correlation_matrix(verdicts: List[StockVerdict]) -> Tuple[Dict[Tuple[str, str], float], List[str]]:
    """Build full NxN correlation matrix for portfolio stocks."""
    tickers = [v.ticker for v in verdicts]

    if len(tickers) < 2:
        return {}, tickers

    returns_data = _fetch_returns(tickers)
    if not returns_data:
        return {}, tickers

    matrix = {}
    available = [t for t in tickers if t in returns_data]

    for i, t1 in enumerate(available):
        for j, t2 in enumerate(available):
            if i <= j:
                if i == j:
                    matrix[(t1, t2)] = 1.0
                else:
                    corr = _compute_correlation(returns_data[t1], returns_data[t2])
                    matrix[(t1, t2)] = round(corr, 3)
                    matrix[(t2, t1)] = round(corr, 3)

    return matrix, available


def assess_portfolio_risk(verdicts: List[StockVerdict],
                          matrix: Dict[Tuple[str, str], float],
                          tickers: List[str]) -> RiskProfile:
    """Assess overall portfolio risk from correlation data."""
    # Sector concentration
    sectors: Dict[str, int] = {}
    for v in verdicts:
        s = v.sector or "Unknown"
        sectors[s] = sectors.get(s, 0) + 1

    # Correlation stats
    pairs = []
    for i, t1 in enumerate(tickers):
        for j, t2 in enumerate(tickers):
            if i < j and (t1, t2) in matrix:
                pairs.append(CorrelationPair(
                    ticker_a=t1, ticker_b=t2,
                    correlation=matrix[(t1, t2)],
                    risk_level="High" if abs(matrix[(t1, t2)]) > 0.7
                    else "Medium" if abs(matrix[(t1, t2)]) > 0.4
                    else "Low",
                ))

    if not pairs:
        return RiskProfile(
            avg_correlation=0.0, max_correlation=0.0,
            max_corr_pair=("N/A", "N/A"), min_correlation=0.0,
            min_corr_pair=("N/A", "N/A"), diversification_score=5.0,
            risk_level="Insufficient Data", sector_concentration=sectors,
        )

    avg_corr = sum(p.correlation for p in pairs) / len(pairs)
    max_pair = max(pairs, key=lambda p: p.correlation)
    min_pair = min(pairs, key=lambda p: p.correlation)

    # Diversification score: lower avg correlation = better diversification
    div_score = max(0, min(10, 10 * (1 - avg_corr)))

    # Risk level
    if avg_corr > 0.6:
        risk = "Highly Concentrated"
    elif avg_corr > 0.35:
        risk = "Moderately Concentrated"
    else:
        risk = "Well Diversified"

    # Cluster warnings
    warnings = []
    high_corr = [p for p in pairs if p.correlation > 0.7]
    if high_corr:
        for p in high_corr:
            warnings.append(
                f"{p.ticker_a} & {p.ticker_b} are highly correlated ({p.correlation:.2f}) - "
                "consider reducing to one"
            )

    max_sector = max(sectors.values()) if sectors else 0
    if max_sector >= 3:
        heavy_sector = [s for s, c in sectors.items() if c == max_sector][0]
        warnings.append(
            f"Heavy sector concentration: {max_sector} stocks in {heavy_sector}"
        )

    return RiskProfile(
        avg_correlation=round(avg_corr, 3),
        max_correlation=max_pair.correlation,
        max_corr_pair=(max_pair.ticker_a, max_pair.ticker_b),
        min_correlation=min_pair.correlation,
        min_corr_pair=(min_pair.ticker_a, min_pair.ticker_b),
        diversification_score=round(div_score, 1),
        risk_level=risk,
        sector_concentration=sectors,
        cluster_warnings=warnings,
    )


def _corr_color(corr: float) -> str:
    """Color based on correlation value."""
    if corr >= 0.7:
        return "bold red"
    elif corr >= 0.4:
        return "yellow"
    elif corr >= 0.0:
        return "green"
    elif corr >= -0.3:
        return "cyan"
    else:
        return "bold cyan"


def render_correlation_matrix(verdicts: List[StockVerdict]):
    """Render full correlation matrix and risk assessment."""
    console.print(Panel("[bold]Computing correlation matrix...[/bold]", border_style="red"))

    matrix, tickers = build_correlation_matrix(verdicts)
    if not matrix or len(tickers) < 2:
        console.print("[yellow]Not enough data for correlation matrix[/yellow]")
        return

    # NxN matrix display
    table = Table(title="RISK CORRELATION MATRIX", box=box.ROUNDED,
                  border_style="red", title_style="bold red")
    table.add_column("", style="bold cyan", width=8)  # Row header

    for t in tickers:
        table.add_column(t, justify="center", width=8)

    for t1 in tickers:
        row = [t1]
        for t2 in tickers:
            corr = matrix.get((t1, t2), 0.0)
            color = _corr_color(corr)
            if t1 == t2:
                row.append("[dim]1.00[/dim]")
            else:
                row.append(f"[{color}]{corr:+.2f}[/{color}]")
        table.add_row(*row)

    console.print(table)

    # Risk assessment
    risk = assess_portfolio_risk(verdicts, matrix, tickers)

    div_color = "green" if risk.diversification_score >= 6 else "yellow" if risk.diversification_score >= 4 else "red"
    risk_color = {"Well Diversified": "green", "Moderately Concentrated": "yellow",
                  "Highly Concentrated": "red"}.get(risk.risk_level, "white")

    summary = Table(title="RISK ASSESSMENT", box=box.ROUNDED, border_style="red")
    summary.add_column("Metric", width=28)
    summary.add_column("Value", width=40)

    summary.add_row("Average Correlation", f"{risk.avg_correlation:+.3f}")
    summary.add_row("Diversification Score", f"[{div_color}]{risk.diversification_score}/10[/{div_color}]")
    summary.add_row("Risk Level", f"[{risk_color}]{risk.risk_level}[/{risk_color}]")
    summary.add_row("Most Correlated",
                     f"{risk.max_corr_pair[0]} & {risk.max_corr_pair[1]} ({risk.max_correlation:+.2f})")
    summary.add_row("Least Correlated",
                     f"{risk.min_corr_pair[0]} & {risk.min_corr_pair[1]} ({risk.min_correlation:+.2f})")

    # Sector breakdown
    sector_str = "  ".join(f"{s}: {c}" for s, c in sorted(risk.sector_concentration.items(),
                                                           key=lambda x: -x[1]))
    summary.add_row("Sector Breakdown", sector_str)

    console.print(summary)

    # Warnings
    if risk.cluster_warnings:
        console.print(Panel(
            "\n".join(f"[yellow]  {w}[/yellow]" for w in risk.cluster_warnings),
            title="CONCENTRATION WARNINGS",
            border_style="yellow",
        ))

    # Legend
    console.print(
        "[dim]Legend: [bold red]>0.7 High risk[/bold red]  "
        "[yellow]0.4-0.7 Medium[/yellow]  "
        "[green]0.0-0.4 Low[/green]  "
        "[cyan]<0.0 Hedged[/cyan][/dim]"
    )
    console.print()
