"""
Verdict System
--------------
Core data structures for the multi-agent stock scoring system.
Each "agent" scores a stock from a different angle (valuation, quality, momentum, etc.)
and the system synthesizes them into a final verdict.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AgentVerdict:
    """A single agent's assessment of a stock."""
    agent_name: str
    score: float  # 0-10
    verdict: str  # "Bullish" / "Neutral" / "Bearish"
    rationale: str = ""
    price_target: Optional[float] = None


@dataclass
class StockVerdict:
    """Final synthesized verdict for a stock."""
    ticker: str
    company_name: str
    sector: str
    current_price: float
    score: float  # 0-10 composite score
    verdict: str  # "Buy" / "Hold" / "Pass" / "Avoid"

    # Component scores (0-10 each)
    valuation_score: float = 0.0
    quality_score: float = 0.0
    momentum_score: float = 0.0
    agent_consensus_score: float = 0.0
    macro_adjustment: float = 0.0

    # Price targets
    one_year_target: Optional[float] = None  # Analyst consensus target
    upside_pct: Optional[float] = None       # Analyst consensus upside
    fair_value: Optional[float] = None       # Intrinsic fair value (multi-method composite)
    fair_value_upside: Optional[float] = None  # % upside to fair value

    # Earnings
    next_earnings: Optional[dt.date] = None
    earnings_countdown: Optional[int] = None

    # Narratives
    bull_case: List[str] = field(default_factory=list)
    bear_case: List[str] = field(default_factory=list)

    # Individual agent results
    agent_verdicts: List[AgentVerdict] = field(default_factory=list)


def compute_verdict(score: float) -> str:
    """Convert a numeric score to a verdict string."""
    if score >= 7.5:
        return "Buy"
    elif score >= 5.5:
        return "Hold"
    elif score >= 3.5:
        return "Pass"
    else:
        return "Avoid"


def synthesize_verdict(
    ticker: str,
    company_name: str,
    sector: str,
    current_price: float,
    agent_verdicts: List[AgentVerdict],
    valuation_score: float = 0.0,
    quality_score: float = 0.0,
    momentum_score: float = 0.0,
    macro_adjustment: float = 0.0,
    one_year_target: Optional[float] = None,
    fair_value: Optional[float] = None,
    next_earnings: Optional[dt.date] = None,
    bull_case: Optional[List[str]] = None,
    bear_case: Optional[List[str]] = None,
) -> StockVerdict:
    """Synthesize individual agent scores into a final verdict.

    Uses multi-method intrinsic valuation (fair_value) alongside analyst
    consensus (one_year_target) to produce a blended price target.
    Applies an upside-consistency guard: a stock with negative intrinsic
    upside cannot receive a Buy verdict regardless of agent scores.
    """
    # Agent consensus
    if agent_verdicts:
        agent_avg = sum(av.score for av in agent_verdicts) / len(agent_verdicts)
    else:
        agent_avg = 5.0

    # Composite score: weighted blend
    raw_score = (
        valuation_score * 0.30
        + quality_score * 0.25
        + momentum_score * 0.20
        + agent_avg * 0.25
    )

    # Apply macro adjustment (slight nudge)
    adjusted = max(0, min(10, raw_score + macro_adjustment))

    # Analyst consensus upside
    analyst_upside = None
    if one_year_target and current_price and current_price > 0:
        analyst_upside = ((one_year_target - current_price) / current_price) * 100

    # Intrinsic fair value upside
    fv_upside = None
    if fair_value and current_price and current_price > 0:
        fv_upside = ((fair_value - current_price) / current_price) * 100

    # Blended upside: weight intrinsic fair value + analyst target
    # If both available, 60% intrinsic / 40% analyst (intrinsic is independent)
    # If only one available, use that one
    upside = None
    if fv_upside is not None and analyst_upside is not None:
        upside = fv_upside * 0.6 + analyst_upside * 0.4
    elif fv_upside is not None:
        upside = fv_upside
    elif analyst_upside is not None:
        upside = analyst_upside

    # Upside-consistency guard (from briefing: negative upside + BUY = contradictory)
    # If blended upside is negative, cap the score so verdict cannot be Buy
    if upside is not None and upside < 0 and adjusted >= 7.5:
        adjusted = min(adjusted, 7.4)  # Cap at high Hold

    # If upside is significantly negative (<-15%), further penalize
    if upside is not None and upside < -15 and adjusted >= 5.5:
        adjusted = min(adjusted, 5.4)  # Drop to Pass

    # Earnings countdown
    countdown = None
    if next_earnings:
        delta = (next_earnings - dt.date.today()).days
        countdown = delta if delta >= 0 else None

    return StockVerdict(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        current_price=current_price,
        score=round(adjusted, 2),
        verdict=compute_verdict(adjusted),
        valuation_score=valuation_score,
        quality_score=quality_score,
        momentum_score=momentum_score,
        agent_consensus_score=round(agent_avg, 2),
        macro_adjustment=macro_adjustment,
        one_year_target=one_year_target,
        upside_pct=round(upside, 2) if upside is not None else None,
        fair_value=fair_value,
        fair_value_upside=round(fv_upside, 2) if fv_upside is not None else None,
        next_earnings=next_earnings,
        earnings_countdown=countdown,
        bull_case=bull_case or [],
        bear_case=bear_case or [],
        agent_verdicts=agent_verdicts,
    )
