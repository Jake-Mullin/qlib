"""
Scoring Agents
--------------
Each agent evaluates a stock from a different angle and returns a score + verdict.
"""

from typing import List

from .data_fetcher import StockData
from .verdict_system import AgentVerdict


def _safe(val, default=0.0):
    return val if val is not None else default


def valuation_agent(data: StockData) -> AgentVerdict:
    """Score based on valuation metrics (PE, PEG, P/B, P/S)."""
    score = 5.0
    reasons = []

    pe = _safe(data.pe_ratio)
    fpe = _safe(data.forward_pe)
    peg = _safe(data.peg_ratio)
    pb = _safe(data.price_to_book)

    if 0 < pe < 15:
        score += 2.0
        reasons.append("Low trailing P/E")
    elif pe > 35:
        score -= 2.0
        reasons.append("High trailing P/E")

    if 0 < fpe < 15:
        score += 1.5
        reasons.append("Low forward P/E")
    elif fpe > 30:
        score -= 1.5

    if 0 < peg < 1.0:
        score += 1.5
        reasons.append("Attractive PEG ratio")
    elif peg > 2.5:
        score -= 1.0

    if 0 < pb < 2.0:
        score += 1.0
    elif pb > 8.0:
        score -= 1.0

    score = max(0, min(10, score))
    verdict = "Bullish" if score >= 6.5 else "Neutral" if score >= 4.5 else "Bearish"

    return AgentVerdict(
        agent_name="Valuation", score=round(score, 2), verdict=verdict,
        rationale="; ".join(reasons) if reasons else "Fair valuation",
        price_target=data.analyst_target,
    )


def quality_agent(data: StockData) -> AgentVerdict:
    """Score based on profitability, margins, balance sheet strength."""
    score = 5.0
    reasons = []

    margin = _safe(data.profit_margin)
    roe = _safe(data.roe)
    d2e = _safe(data.debt_to_equity)
    cr = _safe(data.current_ratio)
    fcf = _safe(data.free_cash_flow)

    if margin > 0.20:
        score += 2.0
        reasons.append("Strong margins")
    elif margin > 0.10:
        score += 1.0
    elif margin < 0:
        score -= 2.0
        reasons.append("Unprofitable")

    if roe > 0.20:
        score += 1.5
        reasons.append("High ROE")
    elif roe < 0:
        score -= 1.5

    if 0 < d2e < 50:
        score += 1.0
        reasons.append("Low debt")
    elif d2e > 200:
        score -= 1.5
        reasons.append("Heavy debt load")

    if cr and cr > 2.0:
        score += 0.5
    elif cr and cr < 1.0:
        score -= 1.0

    if fcf and fcf > 0:
        score += 1.0

    score = max(0, min(10, score))
    verdict = "Bullish" if score >= 6.5 else "Neutral" if score >= 4.5 else "Bearish"

    return AgentVerdict(
        agent_name="Quality", score=round(score, 2), verdict=verdict,
        rationale="; ".join(reasons) if reasons else "Average quality",
    )


def momentum_agent(data: StockData) -> AgentVerdict:
    """Score based on price momentum and trend strength."""
    score = 5.0
    reasons = []

    price = data.current_price
    ma50 = _safe(data.fifty_day_avg)
    ma200 = _safe(data.two_hundred_day_avg)
    high52 = _safe(data.fifty_two_week_high)
    low52 = _safe(data.fifty_two_week_low)

    # Above/below moving averages
    if ma50 > 0 and price > ma50:
        score += 1.0
        if ma200 > 0 and price > ma200:
            score += 1.0
            reasons.append("Above 50 & 200-day MA")
    elif ma50 > 0 and price < ma50:
        score -= 1.0
        if ma200 > 0 and price < ma200:
            score -= 1.0
            reasons.append("Below both moving averages")

    # Golden/death cross
    if ma50 > 0 and ma200 > 0:
        if ma50 > ma200:
            score += 1.0
            reasons.append("Golden cross setup")
        else:
            score -= 1.0

    # Position in 52-week range
    if high52 > 0 and low52 > 0 and high52 != low52:
        position = (price - low52) / (high52 - low52)
        if position > 0.85:
            score += 1.0
            reasons.append("Near 52-week high")
        elif position < 0.3:
            score -= 1.0
            reasons.append("Near 52-week low")

    # Recent price changes
    if data.price_1m_ago and data.price_1m_ago > 0:
        monthly_ret = ((price - data.price_1m_ago) / data.price_1m_ago) * 100
        if monthly_ret > 5:
            score += 1.0
        elif monthly_ret < -10:
            score -= 1.5

    score = max(0, min(10, score))
    verdict = "Bullish" if score >= 6.5 else "Neutral" if score >= 4.5 else "Bearish"

    return AgentVerdict(
        agent_name="Momentum", score=round(score, 2), verdict=verdict,
        rationale="; ".join(reasons) if reasons else "Neutral momentum",
    )


def growth_agent(data: StockData) -> AgentVerdict:
    """Score based on revenue and earnings growth."""
    score = 5.0
    reasons = []

    rev = _safe(data.revenue_growth)
    earn = _safe(data.earnings_growth)

    if rev > 0.25:
        score += 2.5
        reasons.append(f"Strong revenue growth ({rev:.0%})")
    elif rev > 0.10:
        score += 1.0
    elif rev < 0:
        score -= 2.0
        reasons.append("Revenue declining")

    if earn > 0.25:
        score += 2.0
        reasons.append(f"Strong earnings growth ({earn:.0%})")
    elif earn > 0.10:
        score += 1.0
    elif earn is not None and earn < 0:
        score -= 2.0

    score = max(0, min(10, score))
    verdict = "Bullish" if score >= 6.5 else "Neutral" if score >= 4.5 else "Bearish"

    return AgentVerdict(
        agent_name="Growth", score=round(score, 2), verdict=verdict,
        rationale="; ".join(reasons) if reasons else "Moderate growth",
    )


def analyst_agent(data: StockData) -> AgentVerdict:
    """Score based on Wall Street analyst consensus."""
    score = 5.0
    reasons = []

    rec = data.analyst_recommendation or ""
    target = data.analyst_target
    price = data.current_price
    n = data.num_analysts

    rec_lower = rec.lower()
    if "strong_buy" in rec_lower or "strong buy" in rec_lower:
        score += 2.5
        reasons.append("Strong Buy consensus")
    elif "buy" in rec_lower:
        score += 1.5
        reasons.append("Buy consensus")
    elif "hold" in rec_lower:
        pass
    elif "sell" in rec_lower or "underperform" in rec_lower:
        score -= 2.0
        reasons.append("Sell consensus")

    if target and price and price > 0:
        upside = ((target - price) / price) * 100
        if upside > 25:
            score += 2.0
            reasons.append(f"Target implies {upside:.0f}% upside")
        elif upside > 10:
            score += 1.0
        elif upside < -10:
            score -= 1.5

    if n >= 10:
        score += 0.5
    elif n <= 2:
        score -= 0.5

    score = max(0, min(10, score))
    verdict = "Bullish" if score >= 6.5 else "Neutral" if score >= 4.5 else "Bearish"

    return AgentVerdict(
        agent_name="Analyst", score=round(score, 2), verdict=verdict,
        rationale="; ".join(reasons) if reasons else "Mixed analyst views",
        price_target=target,
    )


def run_all_agents(data: StockData) -> List[AgentVerdict]:
    """Run all scoring agents on a stock."""
    return [
        valuation_agent(data),
        quality_agent(data),
        momentum_agent(data),
        growth_agent(data),
        analyst_agent(data),
    ]
