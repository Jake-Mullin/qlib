"""
Macro Tracker
-------------
Tracks macro-economic signals that affect the overall market.
Uses market indices and yield data as proxies.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import List, Optional

import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


@dataclass
class MacroSignal:
    """A single macro-economic indicator."""
    name: str
    value: float
    signal: str  # "Bullish" / "Neutral" / "Bearish"
    description: str = ""


@dataclass
class MacroDashboard:
    """Overall macro environment summary."""
    signals: List[MacroSignal] = field(default_factory=list)
    overall_signal: str = "Neutral"
    overall_score: float = 0.0  # -1 to +1
    recession_probability: str = "Low"


def _fetch_index_momentum(ticker: str, name: str) -> Optional[MacroSignal]:
    """Check if a market index is above/below its 200-day moving average."""
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if len(hist) < 200:
            return None
        current = float(hist["Close"].iloc[-1])
        ma200 = float(hist["Close"].tail(200).mean())
        pct_above = ((current - ma200) / ma200) * 100

        if pct_above > 5:
            signal = "Bullish"
        elif pct_above > -5:
            signal = "Neutral"
        else:
            signal = "Bearish"

        return MacroSignal(
            name=name,
            value=round(pct_above, 2),
            signal=signal,
            description=f"{pct_above:+.1f}% vs 200-day MA",
        )
    except Exception:
        return None


def _fetch_vix() -> Optional[MacroSignal]:
    """Check VIX (fear gauge)."""
    try:
        hist = yf.Ticker("^VIX").history(period="5d")
        if len(hist) == 0:
            return None
        vix = float(hist["Close"].iloc[-1])

        if vix < 15:
            signal = "Bullish"
            desc = "Low volatility - complacency"
        elif vix < 25:
            signal = "Neutral"
            desc = "Normal volatility"
        elif vix < 35:
            signal = "Bearish"
            desc = "Elevated fear"
        else:
            signal = "Bearish"
            desc = "Extreme fear"

        return MacroSignal(name="VIX", value=round(vix, 2), signal=signal,
                           description=desc)
    except Exception:
        return None


def _fetch_yield_curve() -> Optional[MacroSignal]:
    """Check 10Y-2Y Treasury spread as recession indicator."""
    try:
        t10 = yf.Ticker("^TNX").history(period="5d")
        t2 = yf.Ticker("^IRX").history(period="5d")  # 3-month as proxy

        if len(t10) == 0 or len(t2) == 0:
            return None

        ten_yr = float(t10["Close"].iloc[-1])
        short_rate = float(t2["Close"].iloc[-1])
        spread = ten_yr - short_rate

        if spread > 1.0:
            signal = "Bullish"
            desc = "Normal yield curve"
        elif spread > 0:
            signal = "Neutral"
            desc = "Flattening yield curve"
        else:
            signal = "Bearish"
            desc = "Inverted yield curve - recession signal"

        return MacroSignal(name="Yield Curve", value=round(spread, 2),
                           signal=signal, description=desc)
    except Exception:
        return None


def fetch_macro_dashboard() -> MacroDashboard:
    """Build the complete macro dashboard."""
    dashboard = MacroDashboard()

    # Fetch all signals
    indicators = [
        _fetch_index_momentum("^GSPC", "S&P 500 Trend"),
        _fetch_index_momentum("^IXIC", "Nasdaq Trend"),
        _fetch_index_momentum("^DJI", "Dow Jones Trend"),
        _fetch_vix(),
        _fetch_yield_curve(),
    ]

    dashboard.signals = [s for s in indicators if s is not None]

    # Compute overall score
    if dashboard.signals:
        score_map = {"Bullish": 1.0, "Neutral": 0.0, "Bearish": -1.0}
        scores = [score_map.get(s.signal, 0) for s in dashboard.signals]
        dashboard.overall_score = round(sum(scores) / len(scores), 2)

        if dashboard.overall_score > 0.3:
            dashboard.overall_signal = "Bullish"
        elif dashboard.overall_score > -0.3:
            dashboard.overall_signal = "Neutral"
        else:
            dashboard.overall_signal = "Bearish"

        # Recession check
        bearish_count = sum(1 for s in dashboard.signals if s.signal == "Bearish")
        if bearish_count >= 3:
            dashboard.recession_probability = "High"
        elif bearish_count >= 2:
            dashboard.recession_probability = "Moderate"
        else:
            dashboard.recession_probability = "Low"

    return dashboard


def get_macro_adjustment(dashboard: MacroDashboard) -> float:
    """Convert macro signals to a score adjustment for stock verdicts."""
    # Range: -0.5 to +0.5
    return round(dashboard.overall_score * 0.5, 2)


def render_macro_dashboard(dashboard: MacroDashboard):
    """Render macro environment to terminal."""
    signal_c = {"Bullish": "green", "Neutral": "yellow", "Bearish": "red"}.get(
        dashboard.overall_signal, "white")
    recession_c = {"Low": "green", "Moderate": "yellow", "High": "red"}.get(
        dashboard.recession_probability, "white")

    header = (
        f"[{signal_c}]{dashboard.overall_signal}[/{signal_c}]  |  "
        f"Score: {dashboard.overall_score:+.2f}  |  "
        f"Recession Risk: [{recession_c}]{dashboard.recession_probability}[/{recession_c}]"
    )
    console.print(Panel(header, title="MACRO ENVIRONMENT", border_style=signal_c,
                        title_align="left"))

    table = Table(box=box.SIMPLE)
    table.add_column("Indicator", width=20)
    table.add_column("Signal", justify="center", width=10)
    table.add_column("Value", justify="right", width=10)
    table.add_column("Description", width=35)

    for s in dashboard.signals:
        sc = {"Bullish": "green", "Neutral": "yellow", "Bearish": "red"}.get(s.signal, "white")
        table.add_row(
            s.name,
            f"[{sc}]{s.signal}[/{sc}]",
            f"{s.value:.2f}",
            s.description,
        )

    console.print(table)
    console.print()
