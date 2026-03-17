"""
Investor Persona Agents
-----------------------
Each legendary investor evaluates stocks through their unique lens.

Agents:
  1. Michael Burry   - Deep value contrarian, balance sheet obsessed
  2. Cathie Wood     - Disruptive innovation, exponential growth
  3. Ray Dalio       - Macro risk parity, all-weather thinking
  4. Warren Buffett  - Quality moats, margin of safety, long-term compounding
  5. Peter Lynch     - Growth at a reasonable price, invest in what you know
  6. George Soros    - Reflexivity, macro momentum, narrative-driven
  7. Bill Ackman     - Activist value, catalysts, business quality
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from .data_fetcher import StockData, get_price_change
from .valuation_engine import StockValuation


@dataclass
class AgentVerdict:
    """An individual investor agent's take on a stock."""
    agent_name: str
    agent_style: str  # Short description of their approach
    score: float  # 1-10
    verdict: str  # Buy / Hold / Pass / Avoid
    reasoning: List[str]  # Bullet points of key reasoning
    price_target: Optional[float] = None
    conviction: str = "Medium"  # High / Medium / Low


def _score_to_verdict(score: float) -> str:
    if score >= 7.5:
        return "Buy"
    elif score >= 5.5:
        return "Hold"
    elif score >= 3.5:
        return "Pass"
    else:
        return "Avoid"


# ---------------------------------------------------------------------------
# 1. MICHAEL BURRY - The Big Short
# ---------------------------------------------------------------------------
def michael_burry(data: StockData, valuation: StockValuation) -> AgentVerdict:
    """Deep value contrarian. Loves beaten-down assets with hidden value.
    Hates overvalued hype. Focuses on balance sheet, FCF, and margin of safety."""
    score = 5.0
    reasons = []

    # Value: low P/E is good
    if data.pe_ratio and data.pe_ratio > 0:
        if data.pe_ratio < 10:
            score += 2.0
            reasons.append(f"Deep value P/E of {data.pe_ratio:.1f} - Burry loves this")
        elif data.pe_ratio < 15:
            score += 1.0
            reasons.append(f"Reasonable P/E of {data.pe_ratio:.1f}")
        elif data.pe_ratio > 40:
            score -= 2.0
            reasons.append(f"P/E of {data.pe_ratio:.1f} screams overvaluation")
        elif data.pe_ratio > 25:
            score -= 1.0
            reasons.append(f"P/E of {data.pe_ratio:.1f} is elevated")

    # Price to book
    if data.price_to_book and data.price_to_book < 1.5:
        score += 1.0
        reasons.append(f"P/B of {data.price_to_book:.1f} - trading near asset value")
    elif data.price_to_book and data.price_to_book > 10:
        score -= 1.5
        reasons.append(f"P/B of {data.price_to_book:.1f} - way too rich for Burry")

    # Balance sheet strength
    if data.debt_to_equity is not None:
        if data.debt_to_equity < 30:
            score += 1.0
            reasons.append("Low leverage - fortress balance sheet")
        elif data.debt_to_equity > 150:
            score -= 1.0
            reasons.append("Heavy debt load is a red flag")

    # Free cash flow
    if data.free_cash_flow and data.free_cash_flow > 0:
        score += 0.5
        reasons.append("Positive FCF generation")
    elif data.free_cash_flow and data.free_cash_flow < 0:
        score -= 1.0
        reasons.append("Negative FCF - cash burn is dangerous")

    # Contrarian: stock beaten down from 52-week high
    if data.current_price > 0 and data.fifty_two_week_high > 0:
        drawdown = (data.fifty_two_week_high - data.current_price) / data.fifty_two_week_high
        if drawdown > 0.30:
            score += 1.0
            reasons.append(f"Down {drawdown:.0%} from 52wk high - contrarian opportunity")

    # Composite valuation upside
    if valuation.composite_upside and valuation.composite_upside > 30:
        score += 1.0
        reasons.append(f"Valuation models show {valuation.composite_upside:.0f}% upside")

    score = max(1, min(10, score))
    price_target = valuation.composite_fair_value if valuation.composite_fair_value else None

    return AgentVerdict("Michael Burry", "Deep Value Contrarian", round(score, 1),
                        _score_to_verdict(score), reasons, price_target,
                        "High" if score >= 7 else "Medium" if score >= 5 else "Low")


# ---------------------------------------------------------------------------
# 2. CATHIE WOOD - ARK Invest
# ---------------------------------------------------------------------------
def cathie_wood(data: StockData, valuation: StockValuation) -> AgentVerdict:
    """Disruptive innovation seeker. Loves high growth, visionary tech,
    exponential adoption curves. Willing to pay premium for growth."""
    score = 5.0
    reasons = []

    # Revenue growth is king
    if data.revenue_growth:
        if data.revenue_growth > 0.30:
            score += 2.5
            reasons.append(f"Revenue growth of {data.revenue_growth:.0%} - exponential trajectory")
        elif data.revenue_growth > 0.15:
            score += 1.5
            reasons.append(f"Solid revenue growth of {data.revenue_growth:.0%}")
        elif data.revenue_growth < 0.05:
            score -= 1.0
            reasons.append(f"Revenue growth of {data.revenue_growth:.0%} - not disruptive enough")

    # Earnings growth
    if data.earnings_growth and data.earnings_growth > 0.25:
        score += 1.0
        reasons.append(f"Strong earnings growth of {data.earnings_growth:.0%}")

    # Sector preference - she loves tech
    innovation_sectors = ["Technology", "Communication Services", "Healthcare"]
    if data.sector in innovation_sectors:
        score += 1.0
        reasons.append(f"{data.sector} sector aligns with innovation thesis")
    else:
        score -= 0.5
        reasons.append(f"{data.sector} isn't in Cathie's innovation sweet spot")

    # Market cap - she likes growth stage companies
    if data.market_cap:
        if data.market_cap < 50e9:
            score += 0.5
            reasons.append("Mid-cap with room for massive upside")
        elif data.market_cap > 1e12:
            score -= 0.5
            reasons.append("Mega-cap - harder to deliver 10x returns")

    # She accepts high valuations for growth
    if data.pe_ratio and data.pe_ratio > 50 and data.revenue_growth and data.revenue_growth > 0.20:
        reasons.append("High P/E acceptable given growth trajectory")
    elif data.pe_ratio and data.pe_ratio > 60 and (not data.revenue_growth or data.revenue_growth < 0.20):
        score -= 1.0
        reasons.append("High P/E without the growth to back it up")

    # Momentum - she rides winners
    change_6m = get_price_change(data.current_price, data.price_6m_ago)
    if change_6m and change_6m > 30:
        score += 0.5
        reasons.append(f"Strong 6-month momentum: +{change_6m:.0f}%")

    score = max(1, min(10, score))
    # Cathie's price targets are typically aggressive
    pt = data.current_price * 1.5 if data.revenue_growth and data.revenue_growth > 0.20 else None

    return AgentVerdict("Cathie Wood", "Disruptive Innovation", round(score, 1),
                        _score_to_verdict(score), reasons, pt,
                        "High" if score >= 7 else "Medium" if score >= 5 else "Low")


# ---------------------------------------------------------------------------
# 3. RAY DALIO - Bridgewater
# ---------------------------------------------------------------------------
def ray_dalio(data: StockData, valuation: StockValuation) -> AgentVerdict:
    """All-weather macro thinker. Focuses on risk-adjusted returns, diversification,
    balance sheet resilience, and how the stock fits macro cycles."""
    score = 5.0
    reasons = []

    # Beta - he wants balanced risk
    if data.beta is not None:
        if 0.8 <= data.beta <= 1.2:
            score += 1.0
            reasons.append(f"Beta of {data.beta:.2f} - well-balanced risk profile")
        elif data.beta > 1.8:
            score -= 1.0
            reasons.append(f"Beta of {data.beta:.2f} - too volatile for all-weather")
        elif data.beta < 0.5:
            score += 0.5
            reasons.append(f"Low beta of {data.beta:.2f} - defensive characteristics")

    # Dividend - consistent returns
    if data.dividend_yield and data.dividend_yield > 0.02:
        score += 1.0
        reasons.append(f"Dividend yield of {data.dividend_yield:.1%} adds steady return")
    elif data.dividend_yield and data.dividend_yield > 0.01:
        score += 0.5
        reasons.append(f"Modest dividend of {data.dividend_yield:.1%}")

    # Debt management
    if data.current_ratio and data.current_ratio > 1.5:
        score += 0.5
        reasons.append(f"Current ratio of {data.current_ratio:.1f} - good liquidity")
    elif data.current_ratio and data.current_ratio < 1.0:
        score -= 1.0
        reasons.append(f"Current ratio of {data.current_ratio:.1f} - liquidity risk")

    # Profit margins - quality
    if data.profit_margin and data.profit_margin > 0.20:
        score += 1.0
        reasons.append(f"Strong margins at {data.profit_margin:.0%} - pricing power")
    elif data.profit_margin and data.profit_margin < 0.05:
        score -= 0.5
        reasons.append(f"Thin margins of {data.profit_margin:.0%} - vulnerable to downturns")

    # Consistent returns (ROE)
    if data.roe and data.roe > 0.15:
        score += 1.0
        reasons.append(f"ROE of {data.roe:.0%} - efficient capital allocation")

    # Debt to equity
    if data.debt_to_equity is not None and data.debt_to_equity < 50:
        score += 0.5
        reasons.append("Conservative leverage works in all environments")
    elif data.debt_to_equity is not None and data.debt_to_equity > 200:
        score -= 1.0
        reasons.append("Excessive leverage fails in risk-off environments")

    score = max(1, min(10, score))
    pt = valuation.composite_fair_value

    return AgentVerdict("Ray Dalio", "All-Weather Macro", round(score, 1),
                        _score_to_verdict(score), reasons, pt,
                        "High" if score >= 7 else "Medium" if score >= 5 else "Low")


# ---------------------------------------------------------------------------
# 4. WARREN BUFFETT - Berkshire Hathaway
# ---------------------------------------------------------------------------
def warren_buffett(data: StockData, valuation: StockValuation) -> AgentVerdict:
    """Quality compounder. Wants durable competitive moats, high ROE,
    consistent earnings, reasonable price. Never overpays."""
    score = 5.0
    reasons = []

    # Moat indicators: high margins + high ROE
    if data.profit_margin and data.profit_margin > 0.20 and data.roe and data.roe > 0.15:
        score += 2.0
        reasons.append(f"Moat signal: {data.profit_margin:.0%} margins + {data.roe:.0%} ROE")
    elif data.profit_margin and data.profit_margin > 0.15:
        score += 1.0
        reasons.append(f"Decent margins at {data.profit_margin:.0%}")

    # Valuation discipline - Buffett NEVER overpays
    if data.pe_ratio:
        if data.pe_ratio < 20:
            score += 1.5
            reasons.append(f"P/E of {data.pe_ratio:.1f} - price Buffett would consider")
        elif data.pe_ratio > 35:
            score -= 1.5
            reasons.append(f"P/E of {data.pe_ratio:.1f} - too expensive for the Oracle")

    # Consistent earnings (use positive EPS as proxy)
    if data.eps_trailing and data.eps_trailing > 0:
        score += 0.5
        reasons.append("Positive earnings - Buffett requires profitability")
    else:
        score -= 2.0
        reasons.append("Unprofitable - Buffett would never touch this")

    # Low debt
    if data.debt_to_equity is not None and data.debt_to_equity < 50:
        score += 1.0
        reasons.append("Conservative balance sheet - Buffett approved")
    elif data.debt_to_equity is not None and data.debt_to_equity > 150:
        score -= 1.0
        reasons.append("Too much debt for Buffett's taste")

    # Free cash flow
    if data.free_cash_flow and data.free_cash_flow > 1e9:
        score += 1.0
        reasons.append(f"FCF of ${data.free_cash_flow/1e9:.1f}B - cash machine")

    # Margin of safety from valuation
    if valuation.composite_upside and valuation.composite_upside > 20:
        score += 0.5
        reasons.append(f"Margin of safety: {valuation.composite_upside:.0f}% upside")

    score = max(1, min(10, score))
    pt = valuation.composite_fair_value

    return AgentVerdict("Warren Buffett", "Quality Compounder", round(score, 1),
                        _score_to_verdict(score), reasons, pt,
                        "High" if score >= 7 else "Medium" if score >= 5 else "Low")


# ---------------------------------------------------------------------------
# 5. PETER LYNCH - Fidelity Magellan
# ---------------------------------------------------------------------------
def peter_lynch(data: StockData, valuation: StockValuation) -> AgentVerdict:
    """GARP investor. PEG ratio is king. Classifies stocks into categories.
    Loves growth at a reasonable price."""
    score = 5.0
    reasons = []

    # PEG ratio is Lynch's signature metric
    if data.peg_ratio:
        if data.peg_ratio < 1.0:
            score += 2.5
            reasons.append(f"PEG of {data.peg_ratio:.2f} - Lynch's sweet spot (under 1.0)")
        elif data.peg_ratio < 1.5:
            score += 1.5
            reasons.append(f"PEG of {data.peg_ratio:.2f} - reasonable growth-to-price")
        elif data.peg_ratio > 2.5:
            score -= 1.5
            reasons.append(f"PEG of {data.peg_ratio:.2f} - overpaying for growth")
        else:
            reasons.append(f"PEG of {data.peg_ratio:.2f} - moderately priced")

    # Lynch classification
    if data.revenue_growth and data.revenue_growth > 0.20:
        reasons.append("Fast grower - Lynch's favorite category")
        score += 1.0
    elif data.revenue_growth and data.revenue_growth > 0.08:
        reasons.append("Stalwart - steady reliable grower")
        score += 0.5
    elif data.dividend_yield and data.dividend_yield > 0.03:
        reasons.append("Slow grower / Asset play - dividend story")

    # Earnings growth vs PE (his 2:1 rule)
    if data.earnings_growth and data.pe_ratio:
        eg_pct = data.earnings_growth * 100
        if eg_pct > data.pe_ratio:
            score += 1.0
            reasons.append(f"Earnings growth ({eg_pct:.0f}%) > P/E ({data.pe_ratio:.0f}) - Lynch rule")

    # Debt check
    if data.debt_to_equity is not None and data.debt_to_equity < 80:
        score += 0.5
        reasons.append("Manageable debt levels")
    elif data.debt_to_equity is not None and data.debt_to_equity > 200:
        score -= 1.0
        reasons.append("Lynch avoids overleveraged companies")

    # Institutional ownership proxy (large cap = more institutional)
    if data.market_cap and data.market_cap < 20e9:
        score += 0.5
        reasons.append("Under-followed mid-cap - Lynch loved finding these")

    score = max(1, min(10, score))
    # Lynch's target: fair PEG of 1.0
    if data.peg_ratio and data.eps_trailing and data.earnings_growth:
        pt = data.eps_trailing * (data.earnings_growth * 100)
    else:
        pt = valuation.composite_fair_value

    return AgentVerdict("Peter Lynch", "Growth at Reasonable Price", round(score, 1),
                        _score_to_verdict(score), reasons, pt,
                        "High" if score >= 7 else "Medium" if score >= 5 else "Low")


# ---------------------------------------------------------------------------
# 6. GEORGE SOROS - Quantum Fund
# ---------------------------------------------------------------------------
def george_soros(data: StockData, valuation: StockValuation) -> AgentVerdict:
    """Reflexivity trader. Momentum + narrative driven. Looks for self-reinforcing
    trends and market inefficiencies. Willing to bet big on momentum."""
    score = 5.0
    reasons = []

    # Momentum is everything for Soros
    change_1m = get_price_change(data.current_price, data.price_1m_ago)
    change_3m = get_price_change(data.current_price, data.price_3m_ago)
    change_6m = get_price_change(data.current_price, data.price_6m_ago)

    momentum_score = 0
    if change_1m and change_1m > 5:
        momentum_score += 1
        reasons.append(f"1-month momentum: +{change_1m:.1f}%")
    if change_3m and change_3m > 15:
        momentum_score += 1
        reasons.append(f"3-month momentum: +{change_3m:.1f}%")
    if change_6m and change_6m > 25:
        momentum_score += 1
        reasons.append(f"6-month momentum: +{change_6m:.1f}%")

    if momentum_score >= 2:
        score += 2.0
        reasons.append("Strong reflexive feedback loop forming")
    elif momentum_score == 1:
        score += 1.0
    elif change_3m and change_3m < -15:
        score -= 1.0
        reasons.append(f"Negative momentum ({change_3m:.1f}% over 3m) - reflexivity working against")

    # Volume - Soros watches for surges
    # (we'd need volume trend data for this, so simplified)

    # Market cap - Soros can move in and out of large liquid names
    if data.market_cap and data.market_cap > 100e9:
        score += 0.5
        reasons.append("Liquid mega-cap - easy to build large position")

    # Narrative strength - high analyst attention
    if data.num_analyst_opinions and data.num_analyst_opinions > 30:
        score += 0.5
        reasons.append(f"{data.num_analyst_opinions} analysts covering - strong narrative flow")

    # Soros will exploit overvaluation too (short side)
    if data.pe_ratio and data.pe_ratio > 60 and change_3m and change_3m < 0:
        score -= 1.5
        reasons.append("Overvalued + losing momentum - potential short candidate")

    # Sector rotation potential
    if data.sector == "Technology" and change_3m and change_3m > 10:
        score += 0.5
        reasons.append("Tech momentum in Soros's wheelhouse")

    score = max(1, min(10, score))
    # Soros targets based on momentum extension
    if change_3m and change_3m > 0:
        pt = data.current_price * (1 + change_3m / 100)  # Momentum extension
    else:
        pt = data.analyst_target_mean

    return AgentVerdict("George Soros", "Reflexivity & Macro Momentum", round(score, 1),
                        _score_to_verdict(score), reasons, pt,
                        "High" if score >= 7 else "Medium" if score >= 5 else "Low")


# ---------------------------------------------------------------------------
# 7. BILL ACKMAN - Pershing Square
# ---------------------------------------------------------------------------
def bill_ackman(data: StockData, valuation: StockValuation) -> AgentVerdict:
    """Activist value investor. Looks for great businesses trading below intrinsic
    value, with clear catalysts for re-rating. Concentrated portfolio."""
    score = 5.0
    reasons = []

    # Business quality - Ackman wants quality
    if data.operating_margin and data.operating_margin > 0.20:
        score += 1.5
        reasons.append(f"Operating margin of {data.operating_margin:.0%} - high-quality business")
    elif data.operating_margin and data.operating_margin > 0.10:
        score += 0.5
        reasons.append(f"Operating margin of {data.operating_margin:.0%} - decent quality")
    elif data.operating_margin and data.operating_margin < 0.05:
        score -= 1.0
        reasons.append(f"Low operating margin of {data.operating_margin:.0%}")

    # ROE - capital efficiency
    if data.roe and data.roe > 0.20:
        score += 1.0
        reasons.append(f"ROE of {data.roe:.0%} - excellent capital efficiency")

    # Valuation gap = catalyst opportunity
    if valuation.composite_upside:
        if valuation.composite_upside > 30:
            score += 2.0
            reasons.append(f"{valuation.composite_upside:.0f}% upside - activist catalyst potential")
        elif valuation.composite_upside > 15:
            score += 1.0
            reasons.append(f"{valuation.composite_upside:.0f}% upside gap to exploit")
        elif valuation.composite_upside < -20:
            score -= 1.0
            reasons.append("Overvalued - no margin of safety for activist play")

    # FCF generation
    if data.free_cash_flow and data.free_cash_flow > 0:
        score += 0.5
        reasons.append("Positive FCF supports capital return thesis")

    # Ackman likes businesses he can understand (brand-name companies)
    if data.market_cap and 10e9 < data.market_cap < 200e9:
        score += 0.5
        reasons.append("Mid-to-large cap - perfect size for activist position")

    # Price below 52-week high = re-rating opportunity
    if data.current_price > 0 and data.fifty_two_week_high > 0:
        gap = (data.fifty_two_week_high - data.current_price) / data.fifty_two_week_high
        if gap > 0.20:
            score += 1.0
            reasons.append(f"Trading {gap:.0%} below 52-week high - re-rating opportunity")

    score = max(1, min(10, score))
    pt = valuation.composite_fair_value if valuation.composite_fair_value else data.analyst_target_mean

    return AgentVerdict("Bill Ackman", "Activist Value", round(score, 1),
                        _score_to_verdict(score), reasons, pt,
                        "High" if score >= 7 else "Medium" if score >= 5 else "Low")


# ---------------------------------------------------------------------------
# Run all agents
# ---------------------------------------------------------------------------
ALL_AGENTS = [michael_burry, cathie_wood, ray_dalio, warren_buffett, peter_lynch, george_soros, bill_ackman]


def run_all_agents(data: StockData, valuation: StockValuation) -> List[AgentVerdict]:
    """Run every investor persona on a single stock."""
    return [agent(data, valuation) for agent in ALL_AGENTS]


def consensus_verdict(verdicts: List[AgentVerdict]) -> Dict:
    """Compute consensus across all agents."""
    if not verdicts:
        return {"avg_score": 0, "verdict": "N/A", "agreement": "N/A"}

    avg = sum(v.score for v in verdicts) / len(verdicts)
    verdict = _score_to_verdict(avg)

    # Agreement: how many agents share the consensus verdict
    matching = sum(1 for v in verdicts if v.verdict == verdict)
    pct = matching / len(verdicts)
    if pct >= 0.7:
        agreement = "Strong"
    elif pct >= 0.5:
        agreement = "Moderate"
    else:
        agreement = "Split"

    # Compute consensus price target
    targets = [v.price_target for v in verdicts if v.price_target and v.price_target > 0]
    avg_target = sum(targets) / len(targets) if targets else None

    return {
        "avg_score": round(avg, 1),
        "verdict": verdict,
        "agreement": agreement,
        "price_target": round(avg_target, 2) if avg_target else None,
        "bull_case": max(verdicts, key=lambda v: v.score).agent_name,
        "bear_case": min(verdicts, key=lambda v: v.score).agent_name,
    }
