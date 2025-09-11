import sqlite3
con = sqlite3.connect("data/ebasketball.db")
con.row_factory = sqlite3.Row
row = con.execute("""
WITH s AS (
  SELECT e.event_id, e.final_home, e.final_away,
         MAX(CASE WHEN o.market='spread' THEN o.line END) AS spread_open,
         MAX(CASE WHEN o.market='total'  THEN o.line END) AS total_open,
         r.spread_delta, r.total_delta
  FROM event e
  LEFT JOIN opener o ON o.event_id=e.event_id
  LEFT JOIN result r ON r.event_id=e.event_id
  WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
  GROUP BY e.event_id
),
m AS (
  SELECT *,
         ABS(ABS(final_home - final_away) - ABS(spread_open)) AS spread_delta_calc,
         ABS((final_home + final_away) - total_open)          AS total_delta_calc
  FROM s
)
SELECT
  SUM(CASE WHEN spread_open IS NOT NULL AND spread_delta IS NOT NULL
            AND ABS(spread_delta - spread_delta_calc) > 0.25 THEN 1 ELSE 0 END) AS bad_spread_delta,
  SUM(CASE WHEN total_open IS NOT NULL AND total_delta IS NOT NULL
            AND ABS(total_delta - total_delta_calc) > 0.25 THEN 1 ELSE 0 END)   AS bad_total_delta,
  SUM(CASE WHEN spread_open IS NOT NULL THEN 1 ELSE 0 END) AS spread_openers,
  SUM(CASE WHEN total_open  IS NOT NULL THEN 1 ELSE 0 END) AS total_openers,
  COUNT(*) AS finals
FROM m;
""").fetchone()
for k in row.keys():
    print(f"{k}: {row[k]}")
