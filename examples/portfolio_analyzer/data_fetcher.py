"""
Core Stock Data Fetcher
-----------------------
Pulls price data, fundamentals, and earnings dates from Yahoo Finance.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yfinance as yf


@dataclass
class StockData:
    """Container for all data we pull on a single ticker."""
    ticker: str
    current_price: float = 0.0
    market_cap: float = 0.0
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    roe: Optional[float] = None  # Return on equity
    roa: Optional[float] = None  # Return on assets
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    free_cash_flow: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    fifty_two_week_high: float = 0.0
    fifty_two_week_low: float = 0.0
    avg_volume: float = 0.0
    shares_outstanding: float = 0.0
    eps_trailing: Optional[float] = None
    eps_forward: Optional[float] = None
    book_value: Optional[float] = None
    total_revenue: Optional[float] = None
    total_debt: Optional[float] = None
    total_cash: Optional[float] = None
    ebitda: Optional[float] = None
    enterprise_value: Optional[float] = None
    next_earnings_date: Optional[dt.date] = None
    sector: str = ""
    industry: str = ""
    company_name: str = ""
    # Price history for trend analysis
    price_1d_ago: Optional[float] = None
    price_1w_ago: Optional[float] = None
    price_1m_ago: Optional[float] = None
    price_3m_ago: Optional[float] = None
    price_6m_ago: Optional[float] = None
    price_1y_ago: Optional[float] = None
    # Analyst targets
    analyst_target_mean: Optional[float] = None
    analyst_target_median: Optional[float] = None
    analyst_target_low: Optional[float] = None
    analyst_target_high: Optional[float] = None
    analyst_recommendation: str = ""
    num_analyst_opinions: int = 0


def _safe_get(info: dict, key: str, default=None):
    """Safely get a value from Yahoo Finance info dict."""
    val = info.get(key, default)
    if val is None or val == "Infinity" or val == float("inf"):
        return default
    return val


def fetch_stock_data(ticker: str) -> StockData:
    """Fetch comprehensive data for a single stock ticker."""
    stock = yf.Ticker(ticker)
    info = stock.info or {}

    data = StockData(ticker=ticker)
    data.company_name = _safe_get(info, "shortName", ticker)
    data.sector = _safe_get(info, "sector", "Unknown")
    data.industry = _safe_get(info, "industry", "Unknown")
    data.current_price = _safe_get(info, "currentPrice", 0.0) or _safe_get(info, "regularMarketPrice", 0.0)
    data.market_cap = _safe_get(info, "marketCap", 0.0)
    data.pe_ratio = _safe_get(info, "trailingPE")
    data.forward_pe = _safe_get(info, "forwardPE")
    data.peg_ratio = _safe_get(info, "pegRatio")
    data.price_to_book = _safe_get(info, "priceToBook")
    data.price_to_sales = _safe_get(info, "priceToSalesTrailing12Months")
    data.ev_to_ebitda = _safe_get(info, "enterpriseToEbitda")
    data.debt_to_equity = _safe_get(info, "debtToEquity")
    data.current_ratio = _safe_get(info, "currentRatio")
    data.roe = _safe_get(info, "returnOnEquity")
    data.roa = _safe_get(info, "returnOnAssets")
    data.profit_margin = _safe_get(info, "profitMargins")
    data.operating_margin = _safe_get(info, "operatingMargins")
    data.revenue_growth = _safe_get(info, "revenueGrowth")
    data.earnings_growth = _safe_get(info, "earningsGrowth")
    data.free_cash_flow = _safe_get(info, "freeCashflow")
    data.dividend_yield = _safe_get(info, "dividendYield")
    data.beta = _safe_get(info, "beta")
    data.fifty_two_week_high = _safe_get(info, "fiftyTwoWeekHigh", 0.0)
    data.fifty_two_week_low = _safe_get(info, "fiftyTwoWeekLow", 0.0)
    data.avg_volume = _safe_get(info, "averageVolume", 0.0)
    data.shares_outstanding = _safe_get(info, "sharesOutstanding", 0.0)
    data.eps_trailing = _safe_get(info, "trailingEps")
    data.eps_forward = _safe_get(info, "forwardEps")
    data.book_value = _safe_get(info, "bookValue")
    data.total_revenue = _safe_get(info, "totalRevenue")
    data.total_debt = _safe_get(info, "totalDebt")
    data.total_cash = _safe_get(info, "totalCash")
    data.ebitda = _safe_get(info, "ebitda")
    data.enterprise_value = _safe_get(info, "enterpriseValue")

    # Analyst targets
    data.analyst_target_mean = _safe_get(info, "targetMeanPrice")
    data.analyst_target_median = _safe_get(info, "targetMedianPrice")
    data.analyst_target_low = _safe_get(info, "targetLowPrice")
    data.analyst_target_high = _safe_get(info, "targetHighPrice")
    data.analyst_recommendation = _safe_get(info, "recommendationKey", "N/A")
    data.num_analyst_opinions = _safe_get(info, "numberOfAnalystOpinions", 0)

    # Earnings date
    try:
        cal = stock.calendar
        if cal is not None:
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed and len(ed) > 0:
                    raw = ed[0]
                    if isinstance(raw, dt.datetime):
                        data.next_earnings_date = raw.date()
                    elif isinstance(raw, dt.date):
                        data.next_earnings_date = raw
            elif hasattr(cal, "iloc"):
                # DataFrame format
                if "Earnings Date" in cal.columns:
                    raw = cal["Earnings Date"].iloc[0]
                    if hasattr(raw, "date"):
                        data.next_earnings_date = raw.date()
    except Exception:
        pass

    # Historical prices for trend calculation
    try:
        hist = stock.history(period="1y")
        if len(hist) > 0:
            closes = hist["Close"]
            if len(closes) >= 2:
                data.price_1d_ago = closes.iloc[-2]
            if len(closes) >= 5:
                data.price_1w_ago = closes.iloc[-5]
            if len(closes) >= 21:
                data.price_1m_ago = closes.iloc[-21]
            if len(closes) >= 63:
                data.price_3m_ago = closes.iloc[-63]
            if len(closes) >= 126:
                data.price_6m_ago = closes.iloc[-126]
            if len(closes) >= 252:
                data.price_1y_ago = closes.iloc[0]
    except Exception:
        pass

    return data


def fetch_portfolio(tickers: List[str]) -> Dict[str, StockData]:
    """Fetch data for a list of tickers. Returns dict keyed by ticker."""
    portfolio = {}
    for t in tickers:
        try:
            portfolio[t] = fetch_stock_data(t)
        except Exception as e:
            print(f"  [!] Error fetching {t}: {e}")
    return portfolio


def get_price_change(current: float, previous: Optional[float]) -> Optional[float]:
    """Calculate percentage price change."""
    if previous is None or previous == 0:
        return None
    return ((current - previous) / previous) * 100
