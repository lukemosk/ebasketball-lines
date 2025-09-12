# repair_finals_strict.py
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

try:
    from src.betsapi import get_event_score_fast, get_event_result
except Exception:
    from betsapi import get_event_score_fast, get_event_result

DB = "data/ebasketball.db"
WINDOW_MIN = 240  # clean last 4 hours (adjust as you like)

def q(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()

def exec_sql(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.execute(sql, args); con.commit()

def main():
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=WINDOW_MIN)).strftime("%Y-%m-%d %H:%M:%S")
    rows = q("""
        SELECT event_id, start_time_utc, final_home, final_away
        FROM event
        WHERE start_time_utc >= ?
          AND final_home IS NOT NULL
          AND final_away IS NOT NULL
        ORDER BY start_time_utc DESC
    """, (cutoff,))

    to_clear = []
    for r in rows:
        eid = int(r["event_id"])
        fast = get_event_score_fast(eid) or {}
        ts = str(fast.get("time_status") or "")
        finished = False

        if ts == "3":
            finished = True
        else:
            alt = get_event_result(eid) or {}
            if alt.get("final_home") is not None and alt.get("final_away") is not None:
                finished = True

        if not finished:
            to_clear.append(eid)

    for eid in to_clear:
        exec_sql("UPDATE event SET final_home=NULL, final_away=NULL WHERE event_id=?", (eid,))

    print(f"Done. Cleared {len(to_clear)} stale event(s).")

if __name__ == "__main__":
    main()
