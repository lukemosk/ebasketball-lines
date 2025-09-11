# diag_recent.py
import sqlite3
from datetime import datetime, timezone

DB = "data/ebasketball.db"

with sqlite3.connect(DB) as con:
    con.row_factory = sqlite3.Row
    # last 120 minutes of events
    rows = con.execute("""
        SELECT
          e.event_id,
          e.start_time_utc,
          e.home_name, e.away_name,
          e.final_home, e.final_away,
          MAX(CASE WHEN o.market='spread' THEN 1 END) AS has_spread,
          MAX(CASE WHEN o.market='total'  THEN 1 END) AS has_total,
          CASE WHEN r.event_id IS NULL THEN 0 ELSE 1 END AS has_result
        FROM event e
        LEFT JOIN opener o ON o.event_id = e.event_id
        LEFT JOIN result r ON r.event_id = e.event_id
        WHERE e.start_time_utc >= datetime('now','-120 minutes')
        GROUP BY e.event_id
        ORDER BY e.start_time_utc DESC
        LIMIT 50
    """).fetchall()

now_utc = datetime.now(timezone.utc)
print(f"Now (UTC): {now_utc:%Y-%m-%d %H:%M:%S}")
print(f"Recent events (<=120m): {len(rows)}\n")

for r in rows:
    st = datetime.strptime(r["start_time_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    age_min = (now_utc - st).total_seconds() / 60.0
    print(
        f"{r['event_id']} | start={r['start_time_utc']} (age {age_min:5.1f}m) "
        f"| openers(spread,total)=({int(bool(r['has_spread']))},{int(bool(r['has_total']))}) "
        f"| finals={(r['final_home'], r['final_away'])} "
        f"| has_result={r['has_result']} "
        f"| {r['home_name']} vs {r['away_name']}"
    )
