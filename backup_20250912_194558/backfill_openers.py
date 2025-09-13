# backfill_openers.py
from __future__ import annotations
import os, sqlite3
from datetime import datetime, timezone
from typing import Any, Optional, Tuple
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Import betsapi from src if available; fall back to root module if not.
try:
    from src.betsapi import get_odds_openers  # preferred
except Exception:
    from betsapi import get_odds_openers      # fallback

DB_PATH = "data/ebasketball.db"
BOOKMAKER_ID = 0               # matches your schema
LOOKBACK_MINUTES = 240         # recent window to look for missing openers

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def to_iso(ts: str | int | float | None) -> str:
    """Return 'YYYY-MM-DD HH:MM:SS' UTC for epoch or pass-through string."""
    if ts is None:
        return utcnow_iso()
    try:
        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
            return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return str(ts)

def norm_line_ts(x: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Accepts:
      - {"line": float|str, "update_time": ..., "opened_at_utc": ...}
      - float/int/numeric string (legacy/simple)
      - None
    Returns (line, opened_at_utc) with opened_at_utc normalized to ISO.
    """
    if x is None:
        return None, None
    if isinstance(x, dict):
        line = x.get("line")
        ts = x.get("update_time") or x.get("opened_at_utc")
        if line is not None:
            try:
                val = float(str(line).replace("+", "").strip())
                return val, to_iso(ts)
            except Exception:
                return None, None
        return None, None
    # numeric or numeric-ish string
    try:
        return float(str(x).replace("+", "").strip()), utcnow_iso()
    except Exception:
        return None, None

def fetch_missing_recent(con: sqlite3.Connection) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    return con.execute(
        """
        WITH recent AS (
          SELECT event_id
          FROM event
          WHERE start_time_utc >= datetime('now', ?)
             OR start_time_utc IS NULL
        )
        SELECT r.event_id,
               MAX(CASE WHEN o.market='spread' THEN 1 END) AS has_spread,
               MAX(CASE WHEN o.market='total'  THEN 1 END) AS has_total
        FROM recent r
        LEFT JOIN opener o ON o.event_id = r.event_id
        GROUP BY r.event_id
        HAVING has_spread IS NULL OR has_total IS NULL
        ORDER BY r.event_id ASC
        """,
        (f"-{LOOKBACK_MINUTES} minutes",),
    ).fetchall()

def insert_opener(con: sqlite3.Connection, eid: int, market: str, line: float, opened_at_utc: str) -> None:
    con.execute(
        """
        INSERT OR IGNORE INTO opener(event_id, bookmaker_id, market, line, opened_at_utc)
        VALUES (?, ?, ?, ?, ?)
        """,
        (eid, BOOKMAKER_ID, market, float(line), opened_at_utc),
    )

def main():
    with sqlite3.connect(DB_PATH) as con:
        rows = fetch_missing_recent(con)
        print(f"events missing openers: {len(rows)}")
        fixed_sp, fixed_to = 0, 0

        for r in rows:
            eid = int(r["event_id"])
            odds = get_odds_openers(eid) or {}

            sp_line, sp_ts = norm_line_ts(odds.get("spread"))
            to_line, to_ts = norm_line_ts(odds.get("total"))

            print(f"- {eid}: opener spread={sp_line} total={to_line}")

            if sp_line is not None and r["has_spread"] is None:
                insert_opener(con, eid, "spread", sp_line, sp_ts or utcnow_iso())
                fixed_sp += 1

            if to_line is not None and r["has_total"] is None:
                insert_opener(con, eid, "total", to_line, to_ts or utcnow_iso())
                fixed_to += 1

        con.commit()
        print(f"Done. Added spread: {fixed_sp}, total: {fixed_to}")

if __name__ == "__main__":
    main()
