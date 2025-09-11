# audit_sample_rows_fixed.py
import sqlite3

con = sqlite3.connect("data/ebasketball.db")
con.row_factory = sqlite3.Row

rows = con.execute("""
WITH s AS (
  SELECT
    e.event_id,
    e.home_name, e.away_name,
    e.start_time_utc,
    e.final_home, e.final_away,
    MAX(CASE WHEN o.market='spread' THEN o.line END) AS spread_open,
    MAX(CASE WHEN o.market='total'  THEN o.line END) AS total_open,
    MIN(CASE WHEN o.market='spread' THEN o.opened_at_utc END) AS sp_time,
    MIN(CASE WHEN o.market='total'  THEN o.opened_at_utc END) AS to_time,
    r.spread_delta AS spread_delta_stored,
    r.total_delta  AS total_delta_stored,
    r.within2_spread, r.within3_spread, r.within4_spread, r.within5_spread,
    r.within2_total,  r.within3_total,  r.within4_total,  r.within5_total
  FROM event e
  LEFT JOIN opener o ON o.event_id = e.event_id
  LEFT JOIN result r ON r.event_id = e.event_id
  WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
  GROUP BY e.event_id
)
SELECT *,
       ABS(ABS(final_home - final_away) - ABS(spread_open)) AS spread_delta_calc,
       ABS((final_home + final_away) - total_open)          AS total_delta_calc
FROM s
ORDER BY start_time_utc DESC
LIMIT 15;
""").fetchall()

for r in rows:
    margin = abs(r["final_home"] - r["final_away"])
    total  = (r["final_home"] + r["final_away"])
    print(f"\nFI {r['event_id']} | {r['home_name']} vs {r['away_name']} @ {r['start_time_utc']}")
    print(f"  Final: {r['final_home']}-{r['final_away']} | margin={margin} total={total}")
    print(f"  Opener: spread={r['spread_open']} (at {r['sp_time']}), total={r['total_open']} (at {r['to_time']})")
    print(f"  Stored deltas:  spread={r['spread_delta_stored']} | total={r['total_delta_stored']}")
    print(f"  Recalc deltas:  spread={r['spread_delta_calc']} | total={r['total_delta_calc']}")

    # Recompute flags on the fly using calc deltas (for sanity)
    def flags(d):
        return {
            "±2": 1 if d <= 2 else 0,
            "±3": 1 if d <= 3 else 0,
            "±4": 1 if d <= 4 else 0,
            "±5": 1 if d <= 5 else 0,
        }

    sf = flags(r["spread_delta_calc"]) if r["spread_delta_calc"] is not None else {"±2":0,"±3":0,"±4":0,"±5":0}
    tf = flags(r["total_delta_calc"])  if r["total_delta_calc"]  is not None else {"±2":0,"±3":0,"±4":0,"±5":0}

    print(f"  Stored flags:  S±2/3/4/5= {r['within2_spread']} {r['within3_spread']} {r['within4_spread']} {r['within5_spread']}"
          f" | T±2/3/4/5= {r['within2_total']} {r['within3_total']} {r['within4_total']} {r['within5_total']}")
    print(f"  Recalc flags:  S±2/3/4/5= {sf['±2']} {sf['±3']} {sf['±4']} {sf['±5']}"
          f" | T±2/3/4/5= {tf['±2']} {tf['±3']} {tf['±4']} {tf['±5']}")
