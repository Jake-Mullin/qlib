"""
Notion Integration
------------------
Pushes portfolio analysis results to a Notion database.
Each stock becomes a row with verdict, score, price target, etc.

Setup:
  1. Go to https://www.notion.so/my-integrations
  2. Create a new integration, copy the API key
  3. Create a Notion database (or let this script create one)
  4. Share the database with your integration

Requires: pip install requests
"""

import datetime as dt
import json
from typing import Dict, List, Optional

import requests

from .verdict_system import StockVerdict
from .macro_tracker import MacroDashboard


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Simple Notion API client for portfolio updates."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        url = f"{NOTION_API_BASE}{endpoint}"
        resp = requests.request(method, url, headers=self.headers, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def create_database(self, parent_page_id: str, title: str = "Portfolio Tracker") -> str:
        """Create a new Notion database with the portfolio schema.
        Returns the database ID."""
        payload = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": {
                "Ticker": {"title": {}},
                "Company": {"rich_text": {}},
                "Verdict": {
                    "select": {
                        "options": [
                            {"name": "Buy", "color": "green"},
                            {"name": "Hold", "color": "yellow"},
                            {"name": "Pass", "color": "default"},
                            {"name": "Avoid", "color": "red"},
                        ]
                    }
                },
                "Score": {"number": {"format": "number"}},
                "Price": {"number": {"format": "dollar"}},
                "1Y Target": {"number": {"format": "dollar"}},
                "Upside %": {"number": {"format": "percent"}},
                "Sector": {"select": {}},
                "Earnings Date": {"date": {}},
                "Earnings Countdown": {"number": {"format": "number"}},
                "Valuation Score": {"number": {"format": "number"}},
                "Quality Score": {"number": {"format": "number"}},
                "Momentum Score": {"number": {"format": "number"}},
                "Agent Consensus": {"number": {"format": "number"}},
                "Bull Case": {"rich_text": {}},
                "Bear Case": {"rich_text": {}},
                "Top Bull Agent": {"rich_text": {}},
                "Top Bear Agent": {"rich_text": {}},
                "Last Updated": {"date": {}},
            },
        }
        result = self._request("POST", "/databases", payload)
        return result["id"]

    def query_database(self, database_id: str) -> List[dict]:
        """Get all pages in the database."""
        result = self._request("POST", f"/databases/{database_id}/query", {})
        return result.get("results", [])

    def find_stock_page(self, database_id: str, ticker: str) -> Optional[str]:
        """Find an existing page for a ticker. Returns page_id or None."""
        payload = {
            "filter": {
                "property": "Ticker",
                "title": {"equals": ticker},
            }
        }
        result = self._request("POST", f"/databases/{database_id}/query", payload)
        pages = result.get("results", [])
        if pages:
            return pages[0]["id"]
        return None

    def _build_properties(self, verdict: StockVerdict) -> dict:
        """Build Notion properties dict from a StockVerdict."""
        props = {
            "Ticker": {"title": [{"text": {"content": verdict.ticker}}]},
            "Company": {"rich_text": [{"text": {"content": verdict.company_name}}]},
            "Verdict": {"select": {"name": verdict.verdict}},
            "Score": {"number": verdict.score},
            "Price": {"number": round(verdict.current_price, 2) if verdict.current_price else None},
            "1Y Target": {"number": round(verdict.one_year_target, 2) if verdict.one_year_target else None},
            "Sector": {"select": {"name": verdict.sector}} if verdict.sector else {"select": None},
            "Valuation Score": {"number": round(verdict.valuation_score, 1)},
            "Quality Score": {"number": round(verdict.quality_score, 1)},
            "Momentum Score": {"number": round(verdict.momentum_score, 1)},
            "Agent Consensus": {"number": round(verdict.agent_consensus_score, 1)},
            "Last Updated": {"date": {"start": dt.date.today().isoformat()}},
        }

        # Upside as decimal for percent format (0.15 = 15%)
        if verdict.upside_pct is not None:
            props["Upside %"] = {"number": round(verdict.upside_pct / 100, 4)}

        # Earnings date
        if verdict.next_earnings:
            props["Earnings Date"] = {"date": {"start": verdict.next_earnings.isoformat()}}
        if verdict.earnings_countdown is not None:
            props["Earnings Countdown"] = {"number": verdict.earnings_countdown}

        # Bull/Bear case
        if verdict.bull_case:
            bull_text = " | ".join(verdict.bull_case[:3])
            props["Bull Case"] = {"rich_text": [{"text": {"content": bull_text[:2000]}}]}
        if verdict.bear_case:
            bear_text = " | ".join(verdict.bear_case[:3])
            props["Bear Case"] = {"rich_text": [{"text": {"content": bear_text[:2000]}}]}

        # Top bull/bear agents
        if verdict.agent_verdicts:
            bull_agent = max(verdict.agent_verdicts, key=lambda a: a.score)
            bear_agent = min(verdict.agent_verdicts, key=lambda a: a.score)
            props["Top Bull Agent"] = {"rich_text": [{"text": {"content": f"{bull_agent.agent_name} ({bull_agent.score}/10)"}}]}
            props["Top Bear Agent"] = {"rich_text": [{"text": {"content": f"{bear_agent.agent_name} ({bear_agent.score}/10)"}}]}

        return props

    def upsert_stock(self, database_id: str, verdict: StockVerdict):
        """Create or update a stock row in the database."""
        props = self._build_properties(verdict)
        existing_page = self.find_stock_page(database_id, verdict.ticker)

        if existing_page:
            # Update existing row
            self._request("PATCH", f"/pages/{existing_page}", {"properties": props})
        else:
            # Create new row
            payload = {
                "parent": {"database_id": database_id},
                "properties": props,
            }
            self._request("POST", "/pages", payload)

    def update_portfolio(self, database_id: str, verdicts: List[StockVerdict]):
        """Update all stocks in the Notion database."""
        for v in verdicts:
            self.upsert_stock(database_id, v)

    def update_macro_page(self, page_id: str, macro: MacroDashboard):
        """Update a Notion page with macro environment summary.
        This writes to a separate page (not the database)."""
        blocks = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": f"Macro Dashboard - {dt.date.today().isoformat()}"}}]
                },
            },
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {"content": f"Signal: {macro.overall_signal} ({macro.overall_score}/10) | Recession Risk: {macro.recession_probability}"}}],
                    "icon": {"emoji": "🟢" if macro.overall_signal == "Risk On" else "🟡" if macro.overall_signal == "Cautious" else "🔴"},
                },
            },
        ]

        for signal in macro.signals:
            emoji = "🟢" if signal.signal == "Green" else "🟡" if signal.signal == "Yellow" else "🔴"
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": f"{emoji} {signal.name}: {signal.description}"}}]
                },
            })

        self._request("PATCH", f"/blocks/{page_id}/children", {"children": blocks})


def push_to_notion(api_key: str, database_id: str, verdicts: List[StockVerdict],
                   macro: Optional[MacroDashboard] = None, macro_page_id: Optional[str] = None):
    """Convenience function to push everything to Notion."""
    client = NotionClient(api_key)
    print(f"  Pushing {len(verdicts)} stocks to Notion...")
    client.update_portfolio(database_id, verdicts)
    print("  Portfolio database updated.")

    if macro and macro_page_id:
        print("  Updating macro dashboard page...")
        client.update_macro_page(macro_page_id, macro)
        print("  Macro page updated.")


def export_notion_schema() -> dict:
    """Export the database schema for reference/documentation."""
    return {
        "database_name": "Portfolio Tracker",
        "columns": {
            "Ticker": "Title (e.g., AAPL)",
            "Company": "Text (e.g., Apple Inc.)",
            "Verdict": "Select: Buy / Hold / Pass / Avoid",
            "Score": "Number 1-10",
            "Price": "Dollar amount",
            "1Y Target": "Dollar amount",
            "Upside %": "Percentage",
            "Sector": "Select (Technology, Healthcare, etc.)",
            "Earnings Date": "Date",
            "Earnings Countdown": "Number (days until earnings)",
            "Valuation Score": "Number 1-10",
            "Quality Score": "Number 1-10",
            "Momentum Score": "Number 1-10",
            "Agent Consensus": "Number 1-10",
            "Bull Case": "Text (top reasons to buy)",
            "Bear Case": "Text (top risks)",
            "Top Bull Agent": "Text (most bullish investor)",
            "Top Bear Agent": "Text (most bearish investor)",
            "Last Updated": "Date",
        },
    }
