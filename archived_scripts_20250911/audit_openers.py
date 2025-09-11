# audit_openers.py
import sqlite3

con = sqlite3.connect("data/ebasketball.db")
con.row_factory = sqlite3.Row

# 1) any events where "opener" was captured AFTER start? (not a real opener)
rows = con.execute("""
SELECT e.event_id, e.start_time_utc, o.opened_at_utc, e.home_name, e.away_name,
       GROUP_CONCAT(CASE WHEN o.market='spread' THEN o.line END) AS spread,
       GROUP_CONCAT(CASE WHEN o.market='total'  THEN o.line END)  AS total
FROM event e
JOIN opener o ON o.event_id = e.event_id
GROUP BY e.event_id
HAVING opened_at_utc >= e.start_time_utc
ORDER BY e.start_time_utc
""").fetchall()

print("Openers captured AFTER start (not true openers):", len(rows))
for r in rows[:10]:
    print(r["event_id"], r["start_time_utc"], "opened:", r["opened_at_utc"],
          "|", r["home_name"], "vs", r["away_name"], "| spread/total:", r["spread"], "/", r["total"])

# 2) duplicate opener rows per market? (should be 0 or you’ll bias)
dups = con.execute("""
SELECT event_id, market, COUNT(*) c
FROM opener
GROUP BY event_id, market
HAVING COUNT(*) > 1
""").fetchall()
print("\nDuplicate opener rows (event_id, market, count):", len(dups))
for d in dups[:10]:
    print(tuple(d))

# 3) How many finished games have a valid prematch opener captured BEFORE start?
ok = con.execute("""
WITH base AS (
  SELECT e.event_id,
         MIN(CASE WHEN o.market='spread' THEN o.opened_at_utc END) AS sp_time,
         MIN(CASE WHEN o.market='total'  THEN o.opened_at_utc END) AS to_time,
         MAX(CASE WHEN o.market='spread' THEN o.line END)          AS sp_line,
         MAX(CASE WHEN o.market='total'  THEN o.line END)          AS to_line,
         e.start_time_utc,
         e.final_home IS NOT NULL AS has_final
  FROM event e
  LEFT JOIN opener o ON o.event_id = e.event_id
  GROUP BY e.event_id
)
SELECT
  SUM(CASE WHEN has_final AND sp_line IS NOT NULL AND sp_time < start_time_utc THEN 1 ELSE 0 END) AS denom_spread_true,
  SUM(CASE WHEN has_final AND to_line IS NOT NULL AND to_time < start_time_utc THEN 1 ELSE 0 END) AS denom_total_true
FROM base
""").fetchone()

print("\nFinished games with **true** prematch openers:",
      "spread =", ok["denom_spread_true"], "| total =", ok["denom_total_true"])
