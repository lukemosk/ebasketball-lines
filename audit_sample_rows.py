# audit_sample_rows.py
import sqlite3

con = sqlite3.connect("data/ebasketball.db")
con.row_factory = sqlite3.Row
rows = con.execute("""
SELECT e.event_id, e.home_name, e.away_name, e.start_time_utc,
       e.final_home, e.final_away,
       MAX(CASE WHEN o.market='spread' THEN o.line END) AS spread_line,
       MAX(CASE WHEN o.market='total'  THEN o.line END) AS total_line,
       MIN(CASE WHEN o.market='spread' THEN o.opened_at_utc END) AS sp_time,
       MIN(CASE WHEN o.market='total'  THEN o.opened_at_utc END) AS to_time,
       r.spread_delta, r.total_delta,
       r.within2_spread, r.within3_spread, r.within4_spread, r.within5_spread,
       r.within2_total,  r.within3_total,  r.within4_total,  r.within5_total
FROM event e
LEFT JOIN opener o ON o.event_id=e.event_id
LEFT JOIN result r ON r.event_id=e.event_id
WHERE e.final_home IS NOT NULL
ORDER BY e.start_time_utc DESC
LIMIT 15
""").fetchall()

for r in rows:
    print(f"\nFI {r['event_id']} | {r['home_name']} vs {r['away_name']} @ {r['start_time_utc']}")
    print(f"  Final: {r['final_home']}-{r['final_away']} | margin={abs(r['final_home']-r['final_away'])} total={r['final_home']+r['final_away']}")
    print(f"  Opener: spread={r['spread_line']} (at {r['sp_time']}), total={r['total_line']} (at {r['to_time']})")
    print(f"  Deltas: spread={r['spread_delta']} | total={r['total_delta']}")
    print(f"  Flags:  S±2/3/4/5= {r['within2_spread']} {r['within3_spread']} {r['within4_spread']} {r['within5_spread']}"
          f" | T±2/3/4/5= {r['within2_total']} {r['within3_total']} {r['within4_total']} {r['within5_total']}")
