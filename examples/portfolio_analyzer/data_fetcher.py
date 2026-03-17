"""
Data Fetcher
------------
Pulls stock fundamentals, price data, and analyst estimates from yfinance.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import yfinance as yf


@dataclass
class StockData:
    """All raw data for a single stock."""
    ticker: str
    company_name: str = ""
    sector: str = ""
    industry: str = ""
    current_price: float = 0.0

    # Historical prices (for backtesting)
    price_1w_ago: Optional[float] = None
    price_1m_ago: Optional[float] = None
    price_3m_ago: Optional[float] = None
    price_6m_ago: Optional[float] = None
    price_1y_ago: Optional[float] = None

    # Fundamentals
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    dividend_yield: Optional[float] = None

    # Profitability
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None

    # Balance sheet
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    free_cash_flow: Optional[float] = None

    # Analyst data
    analyst_target: Optional[float] = None
    analyst_recommendation: Optional[str] = None
    num_analysts: int = 0

    # Earnings
    next_earnings: Optional[dt.date] = None

    # Momentum
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    fifty_day_avg: Optional[float] = None
    two_hundred_day_avg: Optional[float] = None

    # Error tracking
    fetch_error: Optional[str] = None


def fetch_stock_data(ticker: str) -> StockData:
    """Fetch comprehensive data for a single stock."""
    data = StockData(ticker=ticker)

    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # Basic info
        data.company_name = info.get("longName", info.get("shortName", ticker))
        data.sector = info.get("sector", "Unknown")
        data.industry = info.get("industry", "Unknown")
        data.current_price = info.get("currentPrice",
                             info.get("regularMarketPrice",
                             info.get("previousClose", 0.0))) or 0.0

        # Fundamentals
        data.market_cap = info.get("marketCap")
        data.pe_ratio = info.get("trailingPE")
        data.forward_pe = info.get("forwardPE")
        data.peg_ratio = info.get("pegRatio")
        data.price_to_book = info.get("priceToBook")
        data.price_to_sales = info.get("priceToSalesTrailing12Months")
        data.dividend_yield = info.get("dividendYield")

        # Profitability
        data.profit_margin = info.get("profitMargins")
        data.operating_margin = info.get("operatingMargins")
        data.roe = info.get("returnOnEquity")
        data.roa = info.get("returnOnAssets")
        data.revenue_growth = info.get("revenueGrowth")
        data.earnings_growth = info.get("earningsGrowth")

        # Balance sheet
        data.debt_to_equity = info.get("debtToEquity")
        data.current_ratio = info.get("currentRatio")
        data.free_cash_flow = info.get("freeCashflow")

        # Analyst
        data.analyst_target = info.get("targetMeanPrice")
        data.analyst_recommendation = info.get("recommendationKey")
        data.num_analysts = info.get("numberOfAnalystOpinions", 0)

        # Momentum
        data.beta = info.get("beta")
        data.fifty_two_week_high = info.get("fiftyTwoWeekHigh")
        data.fifty_two_week_low = info.get("fiftyTwoWeekLow")
        data.fifty_day_avg = info.get("fiftyDayAverage")
        data.two_hundred_day_avg = info.get("twoHundredDayAverage")

        # Historical prices
        try:
            hist = stock.history(period="1y")
            if len(hist) > 0:
                if len(hist) >= 5:
                    data.price_1w_ago = float(hist["Close"].iloc[-5])
                if len(hist) >= 21:
                    data.price_1m_ago = float(hist["Close"].iloc[-21])
                if len(hist) >= 63:
                    data.price_3m_ago = float(hist["Close"].iloc[-63])
                if len(hist) >= 126:
                    data.price_6m_ago = float(hist["Close"].iloc[-126])
                if len(hist) >= 252:
                    data.price_1y_ago = float(hist["Close"].iloc[0])
        except Exception:
            pass

        # Earnings date
        try:
            cal = stock.calendar
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed and len(ed) > 0:
                    raw = ed[0]
                    if isinstance(raw, dt.datetime):
                        data.next_earnings = raw.date()
                    elif isinstance(raw, dt.date):
                        data.next_earnings = raw
            elif hasattr(cal, "iloc") and "Earnings Date" in getattr(cal, 'columns', []):
                raw = cal["Earnings Date"].iloc[0]
                if hasattr(raw, "date"):
                    data.next_earnings = raw.date()
        except Exception:
            pass

    except Exception as e:
        data.fetch_error = str(e)

    return data


def fetch_all_stocks(tickers: List[str]) -> Dict[str, StockData]:
    """Fetch data for all tickers."""
    results = {}
    for ticker in tickers:
        results[ticker] = fetch_stock_data(ticker)
    return results
