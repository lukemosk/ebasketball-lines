# peek_openers_per_game.py
import sqlite3

DB = "data/ebasketball.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

rows = con.execute("""
SELECT e.event_id,
       e.home_name || ' vs ' || e.away_name AS match,
       GROUP_CONCAT(o.market) AS markets
FROM event e
LEFT JOIN opener o ON o.event_id = e.event_id
GROUP BY e.event_id
ORDER BY e.start_time_utc
""").fetchall()

for r in rows:
    print(f"{r['event_id']} - {r['match']} -> {r['markets']}")
