# src/backfill_openers_retry_missing.py
from __future__ import annotations
import os, sqlite3
from datetime import datetime, timezone
from typing import Dict, Any
from dotenv import load_dotenv, find_dotenv

# 1) Load .env BEFORE importing betsapi (and search upward from CWD)
load_dotenv(find_dotenv())

# 2) Now it's safe to import modules that read env at import-time
from src.config import CONF            # centralizes env (bookmaker id, etc.)
from .betsapi import get_odds_openers  # returns {"spread":{"line", "update_time}, "total": {...}}

DB_PATH = "data/ebasketball.db"
BOOKMAKER_ID = CONF["book"]                         # e.g., "bet365"
LOOKBACK_MINUTES = int(os.getenv("RETRY_LOOKBACK_MINUTES", "120"))

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def fetch_missing_event_ids(con: sqlite3.Connection) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    return con.execute("""
        WITH recent AS (
          SELECT *
          FROM event
          WHERE start_time_utc >= datetime('now', ?)
        )
        SELECT r.event_id,
               MAX(CASE WHEN o.market='spread' THEN 1 END) AS has_spread,
               MAX(CASE WHEN o.market='total'  THEN 1 END) AS has_total
        FROM recent r
        LEFT JOIN opener o ON o.event_id = r.event_id
        GROUP BY r.event_id
        HAVING has_spread IS NULL OR has_total IS NULL
        ORDER BY r.event_id DESC
    """, (f"-{LOOKBACK_MINUTES} minutes",)).fetchall()

def insert_opener_if_missing(con: sqlite3.Connection, fi: int, market: str, line: float, opened_at_utc: str):
    # Match your schema (7 columns; prices left NULL)
    con.execute("""
        INSERT OR IGNORE INTO opener(event_id, bookmaker_id, market, line, price_home, price_away, opened_at_utc)
        VALUES (?, ?, ?, ?, NULL, NULL, ?)
    """, (fi, BOOKMAKER_ID, market, float(line), opened_at_utc))

def run():
    con = sqlite3.connect(DB_PATH)
    try:
        rows = fetch_missing_event_ids(con)
        if not rows:
            print("No events missing openers in lookback window.")
            return

        print(f"[{utcnow_iso()}] Re-trying openers for {len(rows)} event(s)...")
        fixed_sp, fixed_to = 0, 0

        for r in rows:
            fi = r["event_id"]
            odds: Dict[str, Any] = get_odds_openers(fi) or {}

            sp = odds.get("spread") or {}
            to = odds.get("total")  or {}

            sp_line = sp.get("line")
            to_line = to.get("line")
            opened_at = sp.get("update_time") or to.get("update_time") or utcnow_iso()

            if sp_line is None and to_line is None:
                print(f"FI {fi}: still no game_lines (spread/total both None).")
                continue

            if sp_line is not None and r["has_spread"] is None:
                insert_opener_if_missing(con, fi, "spread", sp_line, opened_at)
                fixed_sp += 1

            if to_line is not None and r["has_total"] is None:
                insert_opener_if_missing(con, fi, "total", to_line, opened_at)
                fixed_to += 1

            if (sp_line is not None) ^ (to_line is not None):
                print(f"FI {fi}: only one market present on retry -> spread={sp_line} total={to_line} opened_at={opened_at}")

        con.commit()
        print(f"Backfill complete. Added spread: {fixed_sp}, total: {fixed_to}")

    finally:
        con.close()

if __name__ == "__main__":
    run()
