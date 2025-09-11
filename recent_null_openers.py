import sqlite3
con = sqlite3.connect("data/ebasketball.db")
con.row_factory = sqlite3.Row

rows = con.execute("""
WITH s AS (
  SELECT e.event_id, e.start_time_utc, e.home_name, e.away_name,
         e.final_home, e.final_away,
         MAX(CASE WHEN o.market='spread' THEN 1 END) AS has_spread,
         MAX(CASE WHEN o.market='total'  THEN 1 END) AS has_total,
         MIN(CASE WHEN o.market='spread' THEN o.opened_at_utc END) AS sp_time,
         MIN(CASE WHEN o.market='total'  THEN o.opened_at_utc END) AS to_time
  FROM event e
  LEFT JOIN opener o ON o.event_id=e.event_id
  WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
  GROUP BY e.event_id
)
SELECT *
FROM s
WHERE (has_spread IS NULL OR has_total IS NULL)
ORDER BY start_time_utc DESC
LIMIT 50;
""").fetchall()

print(f"Rows with finals but missing opener(s): {len(rows)}\n")
for r in rows:
    missing = []
    if r["has_spread"] is None: missing.append("spread")
    if r["has_total"]  is None: missing.append("total")
    print(f"- FI {r['event_id']} @ {r['start_time_utc']} | {r['home_name']} vs {r['away_name']}")
    print(f"    missing: {', '.join(missing)} | sp_time={r['sp_time']} | to_time={r['to_time']}")
