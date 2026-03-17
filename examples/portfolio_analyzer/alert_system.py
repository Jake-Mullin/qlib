"""
Alert Thresholds System
-----------------------
Configurable alerts that fire when stocks cross thresholds.
Examples: "Alert me if any stock drops below score 4" or "if upside > 30%"
"""

import json
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .verdict_system import StockVerdict
from .historical_tracker import get_score_trend

console = Console()

ALERT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "alert_config.json")


@dataclass
class Alert:
    """A triggered alert."""
    ticker: str
    alert_type: str
    severity: str  # "Critical" / "Warning" / "Info"
    message: str


@dataclass
class AlertRule:
    """A configurable alert rule."""
    name: str
    description: str
    enabled: bool = True
    # Thresholds
    score_below: Optional[float] = None
    score_above: Optional[float] = None
    upside_above: Optional[float] = None
    upside_below: Optional[float] = None
    earnings_within_days: Optional[int] = None
    verdict_change_to: Optional[str] = None  # "Buy", "Avoid", etc.
    momentum_below: Optional[float] = None
    valuation_above: Optional[float] = None


# Default rules
DEFAULT_RULES = [
    AlertRule(
        name="Score Collapse",
        description="Stock score dropped below 4.0",
        score_below=4.0,
    ),
    AlertRule(
        name="Strong Buy Signal",
        description="Stock score above 8.0 - potential strong buy",
        score_above=8.0,
    ),
    AlertRule(
        name="High Upside",
        description="Upside potential exceeds 30%",
        upside_above=30.0,
    ),
    AlertRule(
        name="Negative Upside",
        description="Stock appears overvalued (negative upside)",
        upside_below=0.0,
    ),
    AlertRule(
        name="Earnings Imminent",
        description="Earnings within 3 days - high volatility expected",
        earnings_within_days=3,
    ),
    AlertRule(
        name="Earnings This Week",
        description="Earnings within 7 days",
        earnings_within_days=7,
    ),
    AlertRule(
        name="Momentum Crash",
        description="Momentum score below 3.0 - trend is very weak",
        momentum_below=3.0,
    ),
    AlertRule(
        name="Extreme Value",
        description="Valuation score above 8.0 - deeply undervalued",
        valuation_above=8.0,
    ),
]


def load_alert_rules(config_path: str = ALERT_CONFIG_PATH) -> List[AlertRule]:
    """Load alert rules from config, or use defaults."""
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            rules = []
            for r in data.get("rules", []):
                rules.append(AlertRule(
                    name=r["name"],
                    description=r.get("description", ""),
                    enabled=r.get("enabled", True),
                    score_below=r.get("score_below"),
                    score_above=r.get("score_above"),
                    upside_above=r.get("upside_above"),
                    upside_below=r.get("upside_below"),
                    earnings_within_days=r.get("earnings_within_days"),
                    verdict_change_to=r.get("verdict_change_to"),
                    momentum_below=r.get("momentum_below"),
                    valuation_above=r.get("valuation_above"),
                ))
            return rules
        except (json.JSONDecodeError, KeyError):
            pass
    return DEFAULT_RULES


def save_alert_rules(rules: List[AlertRule], config_path: str = ALERT_CONFIG_PATH):
    """Save alert rules to config file."""
    data = {
        "rules": [
            {
                "name": r.name,
                "description": r.description,
                "enabled": r.enabled,
                "score_below": r.score_below,
                "score_above": r.score_above,
                "upside_above": r.upside_above,
                "upside_below": r.upside_below,
                "earnings_within_days": r.earnings_within_days,
                "verdict_change_to": r.verdict_change_to,
                "momentum_below": r.momentum_below,
                "valuation_above": r.valuation_above,
            }
            for r in rules
        ]
    }
    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)


def evaluate_alerts(verdicts: List[StockVerdict],
                    rules: Optional[List[AlertRule]] = None,
                    db_path: str = None) -> List[Alert]:
    """Evaluate all alert rules against current verdicts."""
    if rules is None:
        rules = load_alert_rules()

    alerts = []
    for v in verdicts:
        for rule in rules:
            if not rule.enabled:
                continue

            triggered = False
            severity = "Info"

            # Score thresholds
            if rule.score_below is not None and v.score < rule.score_below:
                triggered = True
                severity = "Critical" if v.score < 3.0 else "Warning"
            if rule.score_above is not None and v.score > rule.score_above:
                triggered = True
                severity = "Info"

            # Upside thresholds
            if rule.upside_above is not None and v.upside_pct is not None:
                if v.upside_pct > rule.upside_above:
                    triggered = True
                    severity = "Info"
            if rule.upside_below is not None and v.upside_pct is not None:
                if v.upside_pct < rule.upside_below:
                    triggered = True
                    severity = "Warning"

            # Earnings countdown
            if rule.earnings_within_days is not None and v.earnings_countdown is not None:
                if 0 <= v.earnings_countdown <= rule.earnings_within_days:
                    triggered = True
                    severity = "Warning" if v.earnings_countdown <= 3 else "Info"

            # Momentum
            if rule.momentum_below is not None and v.momentum_score < rule.momentum_below:
                triggered = True
                severity = "Warning"

            # Valuation
            if rule.valuation_above is not None and v.valuation_score > rule.valuation_above:
                triggered = True
                severity = "Info"

            if triggered:
                alerts.append(Alert(
                    ticker=v.ticker,
                    alert_type=rule.name,
                    severity=severity,
                    message=f"{rule.description} (Score: {v.score:.1f}, "
                            f"Verdict: {v.verdict}, Price: ${v.current_price:.2f})",
                ))

    # Check for score trend alerts using historical data
    if db_path:
        for v in verdicts:
            trend = get_score_trend(v.ticker, db_path=db_path)
            if trend == "Declining":
                alerts.append(Alert(
                    ticker=v.ticker,
                    alert_type="Score Trend Decline",
                    severity="Warning",
                    message=f"{v.ticker} score is trending downward over recent runs",
                ))
            elif trend == "Improving":
                alerts.append(Alert(
                    ticker=v.ticker,
                    alert_type="Score Trend Improvement",
                    severity="Info",
                    message=f"{v.ticker} score is trending upward over recent runs",
                ))

    return sorted(alerts, key=lambda a: {"Critical": 0, "Warning": 1, "Info": 2}[a.severity])


def render_alerts(verdicts: List[StockVerdict], db_path: str = None):
    """Render the alerts dashboard."""
    rules = load_alert_rules()
    alerts = evaluate_alerts(verdicts, rules, db_path)

    if not alerts:
        console.print(Panel("[green]No alerts triggered - all clear![/green]",
                            title="ALERTS", border_style="green"))
        return

    # Group by severity
    critical = [a for a in alerts if a.severity == "Critical"]
    warnings = [a for a in alerts if a.severity == "Warning"]
    info = [a for a in alerts if a.severity == "Info"]

    # Critical alerts
    if critical:
        console.print(Panel(
            "\n".join(
                f"[bold red]  {a.ticker}: {a.alert_type}[/bold red] - {a.message}"
                for a in critical
            ),
            title=f"CRITICAL ALERTS ({len(critical)})",
            border_style="bold red",
        ))

    # Warning alerts
    if warnings:
        console.print(Panel(
            "\n".join(
                f"[yellow]  {a.ticker}: {a.alert_type}[/yellow] - {a.message}"
                for a in warnings
            ),
            title=f"WARNINGS ({len(warnings)})",
            border_style="yellow",
        ))

    # Info alerts
    if info:
        console.print(Panel(
            "\n".join(
                f"[cyan]  {a.ticker}: {a.alert_type}[/cyan] - {a.message}"
                for a in info
            ),
            title=f"INFO ({len(info)})",
            border_style="cyan",
        ))

    # Summary
    console.print(
        f"[dim]Total alerts: {len(alerts)} "
        f"(Critical: {len(critical)}, Warnings: {len(warnings)}, Info: {len(info)})[/dim]"
    )
    console.print()
