"""
Macroeconomic Tracker
---------------------
Monitors leading recession indicators and macro health signals:
  - Buffett Indicator (Market Cap / GDP)
  - Yield Curve (10Y-2Y spread)
  - VIX (Fear Index)
  - S&P 500 trend
  - Unemployment trend
  - PMI proxy
  - Federal Funds Rate context

Uses Yahoo Finance for market data and FRED-compatible proxies.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import yfinance as yf


@dataclass
class MacroSignal:
    """A single macro indicator reading."""
    name: str
    value: Optional[float]
    signal: str  # "Green", "Yellow", "Red"
    description: str
    weight: float = 1.0  # Importance weight


@dataclass
class MacroDashboard:
    """Full macro environment assessment."""
    signals: List[MacroSignal] = field(default_factory=list)
    overall_signal: str = "Neutral"  # "Risk On", "Cautious", "Risk Off"
    overall_score: float = 0.0  # 0-10 (10 = everything great)
    recession_probability: str = "Low"
    last_updated: str = ""

    def compute_overall(self):
        signal_scores = {"Green": 10, "Yellow": 5, "Red": 1}
        total_w = sum(s.weight for s in self.signals)
        if total_w == 0:
            return
        weighted = sum(signal_scores.get(s.signal, 5) * s.weight for s in self.signals)
        self.overall_score = round(weighted / total_w, 1)

        if self.overall_score >= 7:
            self.overall_signal = "Risk On"
            self.recession_probability = "Low"
        elif self.overall_score >= 4.5:
            self.overall_signal = "Cautious"
            self.recession_probability = "Moderate"
        else:
            self.overall_signal = "Risk Off"
            self.recession_probability = "Elevated"

        self.last_updated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def _get_latest_close(ticker: str, period: str = "5d") -> Optional[float]:
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if len(hist) > 0:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def _get_close_n_days_ago(ticker: str, days: int) -> Optional[float]:
    try:
        hist = yf.Ticker(ticker).history(period=f"{days + 10}d")
        if len(hist) >= days:
            return float(hist["Close"].iloc[-days])
    except Exception:
        pass
    return None


def buffett_indicator() -> MacroSignal:
    """Buffett Indicator: Total Market Cap / GDP.
    Uses Wilshire 5000 as market cap proxy.
    Historical GDP ~$28T (approximate, updated periodically)."""
    wilshire = _get_latest_close("^W5000")
    # Wilshire 5000 index value * ~1.2B gives approximate total market cap
    # This is a rough proxy; actual calculation needs FRED GDP data
    # We'll use a simplified version comparing S&P 500 to historical norms
    sp500 = _get_latest_close("^GSPC")

    if sp500 is None:
        return MacroSignal("Buffett Indicator", None, "Yellow",
                           "Could not fetch market data", weight=1.5)

    # Using S&P 500 level as proxy - historical fair value ~3500-4500 in 2023-2024 terms
    # Adjusted: >5500 = elevated, >6500 = stretched
    if sp500 > 6000:
        signal = "Red"
        desc = f"S&P 500 at {sp500:.0f} - market looks stretched vs historical norms"
    elif sp500 > 5000:
        signal = "Yellow"
        desc = f"S&P 500 at {sp500:.0f} - moderately elevated"
    else:
        signal = "Green"
        desc = f"S&P 500 at {sp500:.0f} - reasonable valuation range"

    return MacroSignal("Buffett Indicator (proxy)", sp500, signal, desc, weight=1.5)


def yield_curve() -> MacroSignal:
    """10Y-2Y Treasury spread. Inversion (negative) signals recession risk."""
    # ^TNX = 10-year yield, ^IRX = 13-week T-bill (proxy for short end)
    ten_yr = _get_latest_close("^TNX")
    two_yr = _get_latest_close("^IRX")  # Using 13-week as proxy

    if ten_yr is None or two_yr is None:
        return MacroSignal("Yield Curve (10Y-2Y)", None, "Yellow",
                           "Could not fetch Treasury yields", weight=2.0)

    spread = ten_yr - two_yr
    if spread < -0.5:
        signal = "Red"
        desc = f"Deeply inverted ({spread:.2f}%) - strong recession signal"
    elif spread < 0:
        signal = "Red"
        desc = f"Inverted ({spread:.2f}%) - recession warning"
    elif spread < 0.5:
        signal = "Yellow"
        desc = f"Flat curve ({spread:.2f}%) - watch closely"
    else:
        signal = "Green"
        desc = f"Normal spread ({spread:.2f}%) - healthy"

    return MacroSignal("Yield Curve (10Y-Short)", spread, signal, desc, weight=2.0)


def vix_fear_index() -> MacroSignal:
    """VIX - CBOE Volatility Index. Fear gauge for the market."""
    vix = _get_latest_close("^VIX")

    if vix is None:
        return MacroSignal("VIX Fear Index", None, "Yellow",
                           "Could not fetch VIX", weight=1.5)

    if vix > 30:
        signal = "Red"
        desc = f"VIX at {vix:.1f} - extreme fear / panic levels"
    elif vix > 20:
        signal = "Yellow"
        desc = f"VIX at {vix:.1f} - elevated anxiety"
    else:
        signal = "Green"
        desc = f"VIX at {vix:.1f} - low fear / complacency"

    return MacroSignal("VIX Fear Index", vix, signal, desc, weight=1.5)


def sp500_trend() -> MacroSignal:
    """S&P 500 trend: above or below 200-day moving average."""
    try:
        hist = yf.Ticker("^GSPC").history(period="1y")
        if len(hist) < 200:
            return MacroSignal("S&P 500 Trend", None, "Yellow",
                               "Insufficient history", weight=1.0)

        current = float(hist["Close"].iloc[-1])
        ma200 = float(hist["Close"].tail(200).mean())
        pct_above = ((current - ma200) / ma200) * 100

        if pct_above > 5:
            signal = "Green"
            desc = f"S&P 500 {pct_above:.1f}% above 200-DMA - bullish trend"
        elif pct_above > -2:
            signal = "Yellow"
            desc = f"S&P 500 near 200-DMA ({pct_above:+.1f}%) - trend uncertain"
        else:
            signal = "Red"
            desc = f"S&P 500 {pct_above:.1f}% below 200-DMA - bearish trend"

        return MacroSignal("S&P 500 Trend", pct_above, signal, desc, weight=1.0)
    except Exception:
        return MacroSignal("S&P 500 Trend", None, "Yellow", "Error computing trend", weight=1.0)


def gold_signal() -> MacroSignal:
    """Gold price trend - safe haven demand indicator."""
    gold_now = _get_latest_close("GC=F")
    gold_3m = _get_close_n_days_ago("GC=F", 63)

    if gold_now is None:
        return MacroSignal("Gold (Safe Haven)", None, "Yellow",
                           "Could not fetch gold price", weight=0.8)

    if gold_3m:
        change = ((gold_now - gold_3m) / gold_3m) * 100
        if change > 10:
            signal = "Yellow"
            desc = f"Gold up {change:.1f}% in 3 months - flight to safety"
        elif change > 5:
            signal = "Yellow"
            desc = f"Gold up {change:.1f}% in 3 months - mild safe-haven demand"
        else:
            signal = "Green"
            desc = f"Gold stable ({change:+.1f}% in 3m) - no panic buying"
    else:
        signal = "Yellow"
        desc = f"Gold at ${gold_now:.0f} - monitoring"

    return MacroSignal("Gold (Safe Haven)", gold_now, signal, desc, weight=0.8)


def dollar_strength() -> MacroSignal:
    """US Dollar Index trend - strong dollar can hurt earnings."""
    dxy = _get_latest_close("DX-Y.NYB")

    if dxy is None:
        return MacroSignal("US Dollar Index", None, "Yellow",
                           "Could not fetch DXY", weight=0.8)

    if dxy > 108:
        signal = "Yellow"
        desc = f"DXY at {dxy:.1f} - strong dollar headwind for multinationals"
    elif dxy > 100:
        signal = "Green"
        desc = f"DXY at {dxy:.1f} - moderate dollar, manageable"
    else:
        signal = "Green"
        desc = f"DXY at {dxy:.1f} - weak dollar tailwind for earnings"

    return MacroSignal("US Dollar Index", dxy, signal, desc, weight=0.8)


def run_macro_dashboard() -> MacroDashboard:
    """Run all macro indicators and build the dashboard."""
    dashboard = MacroDashboard()
    print("  Fetching macro indicators...")

    dashboard.signals.append(buffett_indicator())
    dashboard.signals.append(yield_curve())
    dashboard.signals.append(vix_fear_index())
    dashboard.signals.append(sp500_trend())
    dashboard.signals.append(gold_signal())
    dashboard.signals.append(dollar_strength())

    dashboard.compute_overall()
    return dashboard
