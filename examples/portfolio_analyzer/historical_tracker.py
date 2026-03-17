"""
Historical Tracker
------------------
Stores each day's analysis in a SQLite database for trend tracking.
"""

import datetime as dt
import json
import os
import sqlite3
from typing import Dict, List, Optional

from .verdict_system import StockVerdict
from .macro_tracker import MacroDashboard

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "portfolio_history.db")


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH):
    """Create tables if they don't exist."""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            company_name TEXT,
            sector TEXT,
            current_price REAL,
            score REAL,
            verdict TEXT,
            valuation_score REAL,
            quality_score REAL,
            momentum_score REAL,
            agent_consensus_score REAL,
            macro_adjustment REAL,
            one_year_target REAL,
            upside_pct REAL,
            next_earnings TEXT,
            earnings_countdown INTEGER,
            bull_case TEXT,
            bear_case TEXT,
            agent_verdicts_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(run_date, ticker)
        );

        CREATE TABLE IF NOT EXISTS macro_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL UNIQUE,
            overall_signal TEXT,
            overall_score REAL,
            recession_probability TEXT,
            signals_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS earnings_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date TEXT NOT NULL,
            pre_earnings_price REAL,
            post_earnings_price REAL,
            price_change_pct REAL,
            pre_earnings_score REAL,
            pre_earnings_verdict TEXT,
            recorded_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ticker, earnings_date)
        );

        CREATE TABLE IF NOT EXISTS alerts_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_ticker ON snapshots(ticker);
        CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(run_date);
        CREATE INDEX IF NOT EXISTS idx_snapshots_verdict ON snapshots(verdict);
    """)
    conn.commit()
    conn.close()


def save_snapshot(verdicts: List[StockVerdict], macro: MacroDashboard,
                  db_path: str = DEFAULT_DB_PATH, run_date: str = None):
    """Save a full analysis run to the database."""
    init_db(db_path)
    conn = get_connection(db_path)
    date = run_date or dt.date.today().isoformat()

    for v in verdicts:
        agent_data = [
            {"agent": av.agent_name, "score": av.score, "verdict": av.verdict,
             "price_target": av.price_target}
            for av in v.agent_verdicts
        ]
        conn.execute("""
            INSERT OR REPLACE INTO snapshots
            (run_date, ticker, company_name, sector, current_price, score, verdict,
             valuation_score, quality_score, momentum_score, agent_consensus_score,
             macro_adjustment, one_year_target, upside_pct, next_earnings,
             earnings_countdown, bull_case, bear_case, agent_verdicts_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date, v.ticker, v.company_name, v.sector, v.current_price,
            v.score, v.verdict, v.valuation_score, v.quality_score,
            v.momentum_score, v.agent_consensus_score, v.macro_adjustment,
            v.one_year_target, v.upside_pct,
            v.next_earnings.isoformat() if v.next_earnings else None,
            v.earnings_countdown,
            json.dumps(v.bull_case), json.dumps(v.bear_case),
            json.dumps(agent_data),
        ))

    signals_data = [
        {"name": s.name, "value": s.value, "signal": s.signal, "description": s.description}
        for s in macro.signals
    ]
    conn.execute("""
        INSERT OR REPLACE INTO macro_snapshots
        (run_date, overall_signal, overall_score, recession_probability, signals_json)
        VALUES (?, ?, ?, ?, ?)
    """, (date, macro.overall_signal, macro.overall_score,
          macro.recession_probability, json.dumps(signals_data)))

    conn.commit()
    conn.close()


def get_stock_history(ticker: str, days: int = 30,
                      db_path: str = DEFAULT_DB_PATH) -> List[dict]:
    """Get historical snapshots for a ticker."""
    init_db(db_path)
    conn = get_connection(db_path)
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT run_date, score, verdict, current_price, one_year_target, upside_pct,
               valuation_score, quality_score, momentum_score, agent_consensus_score
        FROM snapshots
        WHERE ticker = ? AND run_date >= ?
        ORDER BY run_date ASC
    """, (ticker, cutoff)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_verdict_changes(ticker: str, db_path: str = DEFAULT_DB_PATH) -> List[dict]:
    """Find when a stock's verdict changed."""
    init_db(db_path)
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT run_date, score, verdict, current_price
        FROM snapshots WHERE ticker = ? ORDER BY run_date ASC
    """, (ticker,)).fetchall()
    conn.close()

    changes = []
    prev_verdict = None
    for r in rows:
        if r["verdict"] != prev_verdict:
            changes.append({
                "date": r["run_date"], "from_verdict": prev_verdict,
                "to_verdict": r["verdict"], "score": r["score"],
                "price": r["current_price"],
            })
            prev_verdict = r["verdict"]
    return changes


def get_score_trend(ticker: str, days: int = 30,
                    db_path: str = DEFAULT_DB_PATH) -> Optional[str]:
    """Determine if a stock's score is trending up, down, or flat."""
    history = get_stock_history(ticker, days, db_path)
    if len(history) < 2:
        return None
    recent_avg = sum(h["score"] for h in history[-3:]) / min(3, len(history))
    older_avg = sum(h["score"] for h in history[:3]) / min(3, len(history))
    diff = recent_avg - older_avg
    if diff > 1.0:
        return "Improving"
    elif diff < -1.0:
        return "Declining"
    return "Stable"


def get_macro_history(days: int = 30, db_path: str = DEFAULT_DB_PATH) -> List[dict]:
    """Get historical macro snapshots."""
    init_db(db_path)
    conn = get_connection(db_path)
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT run_date, overall_signal, overall_score, recession_probability
        FROM macro_snapshots WHERE run_date >= ? ORDER BY run_date ASC
    """, (cutoff,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_tickers_latest(db_path: str = DEFAULT_DB_PATH) -> List[dict]:
    """Get the latest snapshot for every ticker."""
    init_db(db_path)
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT s.* FROM snapshots s
        INNER JOIN (
            SELECT ticker, MAX(run_date) as max_date FROM snapshots GROUP BY ticker
        ) latest ON s.ticker = latest.ticker AND s.run_date = latest.max_date
        ORDER BY s.score DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def record_earnings_event(ticker: str, earnings_date: str,
                          pre_price: float, post_price: float,
                          pre_score: float, pre_verdict: str,
                          db_path: str = DEFAULT_DB_PATH):
    """Record an earnings event with before/after data."""
    init_db(db_path)
    conn = get_connection(db_path)
    change_pct = ((post_price - pre_price) / pre_price) * 100 if pre_price > 0 else None
    conn.execute("""
        INSERT OR REPLACE INTO earnings_events
        (ticker, earnings_date, pre_earnings_price, post_earnings_price,
         price_change_pct, pre_earnings_score, pre_earnings_verdict)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ticker, earnings_date, pre_price, post_price, change_pct, pre_score, pre_verdict))
    conn.commit()
    conn.close()


def get_earnings_history(ticker: str = None,
                         db_path: str = DEFAULT_DB_PATH) -> List[dict]:
    """Get earnings event history, optionally filtered by ticker."""
    init_db(db_path)
    conn = get_connection(db_path)
    if ticker:
        rows = conn.execute(
            "SELECT * FROM earnings_events WHERE ticker = ? ORDER BY earnings_date DESC",
            (ticker,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM earnings_events ORDER BY earnings_date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
