# check_finished_candidates.py
import sqlite3
from datetime import datetime, timezone

DB = "data/ebasketball.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

rows = con.execute("""
SELECT event_id, start_time_utc
FROM event
WHERE start_time_utc < datetime('now', '-30 minutes')
  AND final_home IS NULL
ORDER BY start_time_utc ASC
""").fetchall()

print(f"Older than 30m with no final: {len(rows)}")
for r in rows:
    print(dict(r))
