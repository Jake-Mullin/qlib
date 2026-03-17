"""
News Sentiment Layer
--------------------
Pulls recent news for each stock and does basic sentiment scoring.
Uses yfinance news feed + keyword-based sentiment as a lightweight approach.
"""

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .verdict_system import StockVerdict

console = Console()

# Sentiment keyword dictionaries
POSITIVE_WORDS = {
    "beat", "beats", "exceeded", "upgrade", "upgraded", "bullish", "growth",
    "record", "profit", "surge", "surged", "outperform", "strong", "strength",
    "positive", "gain", "gains", "rally", "rallied", "buy", "boost", "boosted",
    "optimistic", "breakthrough", "innovation", "raised", "raises", "dividend",
    "expansion", "momentum", "recovery", "recovered", "improved", "top",
    "exceeded expectations", "revenue growth", "margin expansion", "upbeat",
    "success", "award", "partnership", "launch", "launched", "approval",
}

NEGATIVE_WORDS = {
    "miss", "missed", "downgrade", "downgraded", "bearish", "decline",
    "declined", "loss", "losses", "crash", "crashed", "fall", "falls",
    "underperform", "weak", "weakness", "negative", "sell", "selloff",
    "plunge", "plunged", "cut", "cuts", "layoff", "layoffs", "lawsuit",
    "investigation", "fraud", "recall", "bankruptcy", "debt", "warning",
    "disappointing", "concern", "concerns", "risk", "risks", "delay",
    "delayed", "fine", "fined", "penalty", "violation", "trouble",
    "recession", "inflation", "slump", "slumped", "shutdown", "closure",
}


@dataclass
class NewsItem:
    """A single news item with sentiment."""
    title: str
    publisher: str
    published: Optional[str]
    link: str
    sentiment_score: float  # -1.0 to +1.0
    sentiment: str  # "Positive" / "Neutral" / "Negative"


@dataclass
class StockNewsSentiment:
    """Aggregated news sentiment for a stock."""
    ticker: str
    company_name: str
    news_items: List[NewsItem] = field(default_factory=list)
    avg_sentiment: float = 0.0
    overall_sentiment: str = "Neutral"
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    news_volume: int = 0
    sentiment_vs_verdict: str = ""  # "Aligned" / "Divergent" / "N/A"


def _score_headline(title: str) -> float:
    """Score a headline from -1.0 (very negative) to +1.0 (very positive)."""
    words = set(re.findall(r'\w+', title.lower()))
    pos_hits = len(words & POSITIVE_WORDS)
    neg_hits = len(words & NEGATIVE_WORDS)

    total = pos_hits + neg_hits
    if total == 0:
        return 0.0
    return (pos_hits - neg_hits) / total


def fetch_stock_news(ticker: str, company_name: str) -> List[NewsItem]:
    """Fetch and score news for a single stock."""
    try:
        stock = yf.Ticker(ticker)
        raw_news = stock.news if hasattr(stock, 'news') else []
    except Exception:
        raw_news = []

    items = []
    for article in raw_news[:10]:  # Last 10 articles
        title = article.get("title", "")
        if not title:
            continue

        score = _score_headline(title)
        if score > 0.1:
            sentiment = "Positive"
        elif score < -0.1:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        pub_date = None
        if "providerPublishTime" in article:
            try:
                pub_date = dt.datetime.fromtimestamp(
                    article["providerPublishTime"]
                ).strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass

        items.append(NewsItem(
            title=title[:120],
            publisher=article.get("publisher", "Unknown"),
            published=pub_date,
            link=article.get("link", ""),
            sentiment_score=round(score, 3),
            sentiment=sentiment,
        ))

    return items


def analyze_news_sentiment(verdicts: List[StockVerdict]) -> List[StockNewsSentiment]:
    """Analyze news sentiment for all stocks."""
    results = []

    for v in verdicts:
        sns = StockNewsSentiment(
            ticker=v.ticker,
            company_name=v.company_name,
        )

        news = fetch_stock_news(v.ticker, v.company_name)
        sns.news_items = news
        sns.news_volume = len(news)

        if news:
            scores = [n.sentiment_score for n in news]
            sns.avg_sentiment = sum(scores) / len(scores)
            sns.positive_count = sum(1 for n in news if n.sentiment == "Positive")
            sns.negative_count = sum(1 for n in news if n.sentiment == "Negative")
            sns.neutral_count = sum(1 for n in news if n.sentiment == "Neutral")

            if sns.avg_sentiment > 0.1:
                sns.overall_sentiment = "Positive"
            elif sns.avg_sentiment < -0.1:
                sns.overall_sentiment = "Negative"
            else:
                sns.overall_sentiment = "Neutral"

            # Check alignment with verdict
            verdict_positive = v.verdict in ("Buy", "Hold")
            news_positive = sns.avg_sentiment > 0
            if sns.avg_sentiment == 0:
                sns.sentiment_vs_verdict = "N/A"
            elif verdict_positive == news_positive:
                sns.sentiment_vs_verdict = "Aligned"
            else:
                sns.sentiment_vs_verdict = "Divergent"
        else:
            sns.sentiment_vs_verdict = "No News"

        results.append(sns)

    return results


def _sentiment_color(sentiment: str) -> str:
    colors = {"Positive": "green", "Neutral": "yellow", "Negative": "red"}
    return colors.get(sentiment, "white")


def _sentiment_bar(score: float, width: int = 20) -> str:
    """Visual sentiment bar centered at 0."""
    mid = width // 2
    if score >= 0:
        filled = int(score * mid)
        return f"[dim]{'░' * mid}[/dim][green]{'█' * filled}[/green][dim]{'░' * (mid - filled)}[/dim]"
    else:
        filled = int(abs(score) * mid)
        return f"[dim]{'░' * (mid - filled)}[/dim][red]{'█' * filled}[/red][dim]{'░' * mid}[/dim]"


def render_news_sentiment(verdicts: List[StockVerdict]):
    """Render news sentiment dashboard."""
    console.print(Panel("[bold]Fetching news sentiment...[/bold]", border_style="blue"))

    results = analyze_news_sentiment(verdicts)

    # Summary table
    table = Table(title="NEWS SENTIMENT LAYER", box=box.ROUNDED,
                  border_style="blue", title_style="bold blue")
    table.add_column("Ticker", style="bold cyan", width=8)
    table.add_column("Company", width=18)
    table.add_column("Sentiment", justify="center", width=10)
    table.add_column("Score", justify="center", width=7)
    table.add_column("Meter", width=22)
    table.add_column("+/-/0", justify="center", width=8)
    table.add_column("Volume", justify="center", width=7)
    table.add_column("vs Verdict", justify="center", width=12)

    for r in sorted(results, key=lambda x: x.avg_sentiment, reverse=True):
        sc = _sentiment_color(r.overall_sentiment)
        vs_color = {"Aligned": "green", "Divergent": "bold red", "No News": "dim",
                    "N/A": "dim"}.get(r.sentiment_vs_verdict, "white")

        table.add_row(
            r.ticker,
            r.company_name[:18],
            f"[{sc}]{r.overall_sentiment}[/{sc}]",
            f"[{sc}]{r.avg_sentiment:+.2f}[/{sc}]",
            _sentiment_bar(r.avg_sentiment),
            f"[green]{r.positive_count}[/green]/[red]{r.negative_count}[/red]/[dim]{r.neutral_count}[/dim]",
            str(r.news_volume),
            f"[{vs_color}]{r.sentiment_vs_verdict}[/{vs_color}]",
        )

    console.print(table)

    # Divergent alerts - these are the most interesting
    divergent = [r for r in results if r.sentiment_vs_verdict == "Divergent"]
    if divergent:
        console.print(Panel(
            "\n".join(
                f"[bold yellow]  {r.ticker}[/bold yellow]: News is "
                f"[{_sentiment_color(r.overall_sentiment)}]{r.overall_sentiment}[/{_sentiment_color(r.overall_sentiment)}] "
                f"but verdict is {next(v.verdict for v in verdicts if v.ticker == r.ticker)} — "
                f"investigate further"
                for r in divergent
            ),
            title="SENTIMENT / VERDICT DIVERGENCES",
            border_style="yellow",
        ))

    # Top headlines per stock
    for r in results:
        if r.news_items:
            headlines = []
            for n in r.news_items[:3]:
                sc = _sentiment_color(n.sentiment)
                headlines.append(
                    f"  [{sc}]{'▲' if n.sentiment == 'Positive' else '▼' if n.sentiment == 'Negative' else '●'}[/{sc}] "
                    f"[dim]{n.publisher}:[/dim] {n.title}"
                )
            console.print(f"\n[bold cyan]{r.ticker}[/bold cyan] headlines:")
            for h in headlines:
                console.print(h)

    console.print()
