"""
Verdict System
--------------
Combines all analysis into a final Buy/Hold/Pass/Avoid verdict with 1-10 scoring.
Weighs valuation, investor consensus, macro conditions, and momentum.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .data_fetcher import StockData, get_price_change
from .valuation_engine import StockValuation
from .investor_agents import AgentVerdict, consensus_verdict
from .macro_tracker import MacroDashboard


@dataclass
class StockVerdict:
    """Final comprehensive verdict for a stock."""
    ticker: str
    company_name: str
    sector: str
    current_price: float
    # Final verdict
    score: float  # 1-10
    verdict: str  # Buy / Hold / Pass / Avoid
    # Component scores (each 1-10)
    valuation_score: float = 5.0
    momentum_score: float = 5.0
    quality_score: float = 5.0
    agent_consensus_score: float = 5.0
    macro_adjustment: float = 0.0
    # Targets
    one_year_target: Optional[float] = None
    upside_pct: Optional[float] = None
    # Earnings
    next_earnings: Optional[dt.date] = None
    earnings_countdown: Optional[int] = None  # Days until earnings
    # Agent details
    agent_verdicts: List[AgentVerdict] = field(default_factory=list)
    # Valuation details
    valuation: Optional[StockValuation] = None
    # Key reasons
    bull_case: List[str] = field(default_factory=list)
    bear_case: List[str] = field(default_factory=list)


def _score_to_verdict(score: float) -> str:
    if score >= 7.5:
        return "Buy"
    elif score >= 5.5:
        return "Hold"
    elif score >= 3.5:
        return "Pass"
    else:
        return "Avoid"


def compute_valuation_score(valuation: StockValuation) -> float:
    """Convert valuation upside into a 1-10 score."""
    if valuation.composite_upside is None:
        return 5.0
    up = valuation.composite_upside
    if up > 50:
        return 10.0
    elif up > 30:
        return 8.5
    elif up > 15:
        return 7.0
    elif up > 0:
        return 6.0
    elif up > -15:
        return 4.5
    elif up > -30:
        return 3.0
    else:
        return 1.5


def compute_momentum_score(data: StockData) -> float:
    """Score based on multi-timeframe price momentum."""
    score = 5.0
    changes = [
        (get_price_change(data.current_price, data.price_1m_ago), 1.0),
        (get_price_change(data.current_price, data.price_3m_ago), 1.5),
        (get_price_change(data.current_price, data.price_6m_ago), 1.0),
    ]
    for change, weight in changes:
        if change is None:
            continue
        if change > 20:
            score += 1.5 * weight / 1.5
        elif change > 10:
            score += 1.0 * weight / 1.5
        elif change > 0:
            score += 0.5 * weight / 1.5
        elif change > -10:
            score -= 0.5 * weight / 1.5
        elif change > -20:
            score -= 1.0 * weight / 1.5
        else:
            score -= 1.5 * weight / 1.5

    return max(1, min(10, score))


def compute_quality_score(data: StockData) -> float:
    """Score based on business quality metrics."""
    score = 5.0

    # Profitability
    if data.profit_margin and data.profit_margin > 0.20:
        score += 1.5
    elif data.profit_margin and data.profit_margin > 0.10:
        score += 0.5
    elif data.profit_margin and data.profit_margin < 0:
        score -= 2.0

    # ROE
    if data.roe and data.roe > 0.20:
        score += 1.0
    elif data.roe and data.roe > 0.10:
        score += 0.5
    elif data.roe and data.roe < 0:
        score -= 1.0

    # Balance sheet
    if data.debt_to_equity is not None and data.debt_to_equity < 50:
        score += 0.5
    elif data.debt_to_equity is not None and data.debt_to_equity > 200:
        score -= 1.0

    # FCF
    if data.free_cash_flow and data.free_cash_flow > 0:
        score += 0.5
    elif data.free_cash_flow and data.free_cash_flow < 0:
        score -= 1.0

    # Growth
    if data.revenue_growth and data.revenue_growth > 0.15:
        score += 1.0
    elif data.revenue_growth and data.revenue_growth > 0.05:
        score += 0.5

    return max(1, min(10, score))


def macro_adjustment_factor(macro: MacroDashboard) -> float:
    """Returns an adjustment (-1.0 to +1.0) based on macro environment."""
    if macro.overall_score >= 7:
        return 0.5  # Macro tailwind
    elif macro.overall_score >= 5:
        return 0.0  # Neutral
    elif macro.overall_score >= 3:
        return -0.5  # Headwind
    else:
        return -1.0  # Strong headwind


def build_verdict(data: StockData, valuation: StockValuation,
                  agent_verdicts: List[AgentVerdict],
                  macro: MacroDashboard) -> StockVerdict:
    """Build the final comprehensive verdict for a stock."""
    sv = StockVerdict(
        ticker=data.ticker,
        company_name=data.company_name,
        sector=data.sector,
        current_price=data.current_price,
        score=0,
        verdict="",
    )

    # Component scores
    sv.valuation_score = compute_valuation_score(valuation)
    sv.momentum_score = compute_momentum_score(data)
    sv.quality_score = compute_quality_score(data)

    # Agent consensus
    consensus = consensus_verdict(agent_verdicts)
    sv.agent_consensus_score = consensus["avg_score"]
    sv.agent_verdicts = agent_verdicts
    sv.valuation = valuation

    # Macro adjustment
    sv.macro_adjustment = macro_adjustment_factor(macro)

    # Weighted final score
    weights = {
        "valuation": 0.25,
        "quality": 0.25,
        "agents": 0.25,
        "momentum": 0.15,
    }
    raw_score = (
        sv.valuation_score * weights["valuation"]
        + sv.quality_score * weights["quality"]
        + sv.agent_consensus_score * weights["agents"]
        + sv.momentum_score * weights["momentum"]
    )
    # Remaining 10% is macro
    sv.score = round(max(1, min(10, raw_score + sv.macro_adjustment)), 1)
    sv.verdict = _score_to_verdict(sv.score)

    # Price target: blend of agent targets and valuation
    targets = []
    if consensus["price_target"]:
        targets.append(consensus["price_target"])
    if valuation.composite_fair_value:
        targets.append(valuation.composite_fair_value)
    if data.analyst_target_mean:
        targets.append(data.analyst_target_mean)
    if targets:
        sv.one_year_target = round(sum(targets) / len(targets), 2)
        if data.current_price > 0:
            sv.upside_pct = round(((sv.one_year_target - data.current_price) / data.current_price) * 100, 1)

    # Earnings countdown
    sv.next_earnings = data.next_earnings_date
    if data.next_earnings_date:
        delta = data.next_earnings_date - dt.date.today()
        sv.earnings_countdown = delta.days if delta.days >= 0 else None

    # Bull/Bear case extraction
    for av in agent_verdicts:
        if av.score >= 7:
            sv.bull_case.extend(av.reasoning[:2])
        elif av.score <= 3.5:
            sv.bear_case.extend(av.reasoning[:2])

    # Deduplicate
    sv.bull_case = list(dict.fromkeys(sv.bull_case))[:5]
    sv.bear_case = list(dict.fromkeys(sv.bear_case))[:5]

    return sv
