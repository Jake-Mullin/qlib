"""
Valuation Engine
----------------
Multiple valuation methodologies applied to each stock:
  - DCF (Discounted Cash Flow)
  - Graham Number
  - PEG Valuation
  - EV/EBITDA relative
  - P/E relative to sector
  - Price-to-Book value assessment
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import math

from .data_fetcher import StockData


@dataclass
class ValuationResult:
    """Result of a single valuation method."""
    method: str
    fair_value: Optional[float]  # Estimated fair value per share
    upside_pct: Optional[float]  # % upside from current price
    confidence: str  # "High", "Medium", "Low"
    notes: str = ""


@dataclass
class StockValuation:
    """Full valuation output for a stock."""
    ticker: str
    current_price: float
    valuations: List[ValuationResult] = field(default_factory=list)
    composite_fair_value: Optional[float] = None
    composite_upside: Optional[float] = None

    def compute_composite(self):
        """Weighted average of valid valuations."""
        weights = {"High": 3.0, "Medium": 2.0, "Low": 1.0}
        total_w = 0.0
        total_v = 0.0
        for v in self.valuations:
            if v.fair_value is not None and v.fair_value > 0:
                w = weights.get(v.confidence, 1.0)
                total_v += v.fair_value * w
                total_w += w
        if total_w > 0:
            self.composite_fair_value = total_v / total_w
            if self.current_price > 0:
                self.composite_upside = ((self.composite_fair_value - self.current_price) / self.current_price) * 100


def dcf_valuation(data: StockData, discount_rate: float = 0.10, growth_years: int = 5, terminal_growth: float = 0.03) -> ValuationResult:
    """Simplified DCF based on free cash flow."""
    if not data.free_cash_flow or data.free_cash_flow <= 0 or not data.shares_outstanding or data.shares_outstanding <= 0:
        return ValuationResult("DCF", None, None, "Low", "Insufficient FCF data")

    fcf = data.free_cash_flow
    growth_rate = data.revenue_growth if data.revenue_growth and data.revenue_growth > 0 else 0.05

    # Cap growth rate to reasonable bounds
    growth_rate = min(growth_rate, 0.30)

    projected_fcf = []
    for yr in range(1, growth_years + 1):
        fcf *= (1 + growth_rate)
        projected_fcf.append(fcf / ((1 + discount_rate) ** yr))

    # Terminal value
    terminal_fcf = fcf * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    terminal_pv = terminal_value / ((1 + discount_rate) ** growth_years)

    intrinsic = (sum(projected_fcf) + terminal_pv) / data.shares_outstanding
    upside = ((intrinsic - data.current_price) / data.current_price) * 100 if data.current_price > 0 else None

    confidence = "Medium"
    if data.free_cash_flow > 0 and data.revenue_growth:
        confidence = "High"

    return ValuationResult("DCF", round(intrinsic, 2), round(upside, 1) if upside else None, confidence,
                           f"Growth={growth_rate:.1%}, Discount={discount_rate:.0%}")


def graham_number(data: StockData) -> ValuationResult:
    """Benjamin Graham's intrinsic value formula: sqrt(22.5 * EPS * Book Value)."""
    eps = data.eps_trailing
    bv = data.book_value
    if not eps or eps <= 0 or not bv or bv <= 0:
        return ValuationResult("Graham Number", None, None, "Low", "Needs positive EPS & Book Value")

    fair = math.sqrt(22.5 * eps * bv)
    upside = ((fair - data.current_price) / data.current_price) * 100 if data.current_price > 0 else None
    return ValuationResult("Graham Number", round(fair, 2), round(upside, 1) if upside else None, "Medium",
                           f"EPS={eps:.2f}, BV={bv:.2f}")


def peg_valuation(data: StockData) -> ValuationResult:
    """PEG-based fair PE estimation. Fair PEG = 1.0 implies fair PE = growth rate * 100."""
    if not data.peg_ratio or not data.eps_trailing or data.eps_trailing <= 0:
        return ValuationResult("PEG Fair Value", None, None, "Low", "Needs PEG ratio and EPS")

    if not data.earnings_growth or data.earnings_growth <= 0:
        return ValuationResult("PEG Fair Value", None, None, "Low", "Needs positive earnings growth")

    # Fair PE if PEG were 1.0
    fair_pe = data.earnings_growth * 100
    fair_price = fair_pe * data.eps_trailing
    upside = ((fair_price - data.current_price) / data.current_price) * 100 if data.current_price > 0 else None
    confidence = "Medium" if data.peg_ratio else "Low"
    return ValuationResult("PEG Fair Value", round(fair_price, 2), round(upside, 1) if upside else None, confidence,
                           f"PEG={data.peg_ratio:.2f}, Fair PE={fair_pe:.1f}")


def ev_ebitda_valuation(data: StockData, sector_avg_multiple: float = 15.0) -> ValuationResult:
    """EV/EBITDA relative valuation against sector average."""
    if not data.ebitda or data.ebitda <= 0 or not data.shares_outstanding or data.shares_outstanding <= 0:
        return ValuationResult("EV/EBITDA", None, None, "Low", "Needs EBITDA data")

    total_debt = data.total_debt or 0
    total_cash = data.total_cash or 0

    fair_ev = data.ebitda * sector_avg_multiple
    fair_equity = fair_ev - total_debt + total_cash
    fair_price = fair_equity / data.shares_outstanding

    if fair_price <= 0:
        return ValuationResult("EV/EBITDA", None, None, "Low", "Negative equity value")

    upside = ((fair_price - data.current_price) / data.current_price) * 100 if data.current_price > 0 else None
    current_mult = data.ev_to_ebitda if data.ev_to_ebitda else "N/A"
    return ValuationResult("EV/EBITDA", round(fair_price, 2), round(upside, 1) if upside else None, "Medium",
                           f"Current={current_mult}, Sector avg={sector_avg_multiple}")


def pb_valuation(data: StockData) -> ValuationResult:
    """Price-to-Book assessment. Fair P/B depends on ROE."""
    if not data.book_value or data.book_value <= 0 or not data.roe:
        return ValuationResult("P/B Value", None, None, "Low", "Needs Book Value and ROE")

    # Justified P/B = ROE / (cost of equity - growth)
    # Simplified: if ROE > 15%, stock deserves P/B of ~3x; if ROE ~10%, ~1.5x; etc.
    roe_pct = data.roe * 100 if data.roe < 1 else data.roe
    if roe_pct > 25:
        fair_pb = 4.0
    elif roe_pct > 20:
        fair_pb = 3.0
    elif roe_pct > 15:
        fair_pb = 2.5
    elif roe_pct > 10:
        fair_pb = 1.5
    else:
        fair_pb = 1.0

    fair_price = data.book_value * fair_pb
    upside = ((fair_price - data.current_price) / data.current_price) * 100 if data.current_price > 0 else None
    return ValuationResult("P/B Value", round(fair_price, 2), round(upside, 1) if upside else None, "Low",
                           f"ROE={roe_pct:.1f}%, Fair P/B={fair_pb}x")


# Sector average EV/EBITDA multiples (approximate)
SECTOR_EV_EBITDA = {
    "Technology": 20.0,
    "Communication Services": 14.0,
    "Consumer Cyclical": 14.0,
    "Consumer Defensive": 14.0,
    "Financial Services": 10.0,
    "Healthcare": 16.0,
    "Industrials": 13.0,
    "Energy": 7.0,
    "Utilities": 12.0,
    "Real Estate": 18.0,
    "Basic Materials": 9.0,
}


def run_all_valuations(data: StockData) -> StockValuation:
    """Run every valuation method on a stock and produce composite."""
    sv = StockValuation(ticker=data.ticker, current_price=data.current_price)

    sv.valuations.append(dcf_valuation(data))
    sv.valuations.append(graham_number(data))
    sv.valuations.append(peg_valuation(data))

    sector_mult = SECTOR_EV_EBITDA.get(data.sector, 15.0)
    sv.valuations.append(ev_ebitda_valuation(data, sector_avg_multiple=sector_mult))
    sv.valuations.append(pb_valuation(data))

    sv.compute_composite()
    return sv
