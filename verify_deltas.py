import sqlite3, math
con = sqlite3.connect("data/ebasketball.db")
con.row_factory = sqlite3.Row
rows = con.execute("""
WITH base AS (
  SELECT e.event_id, e.final_home, e.final_away,
         MAX(CASE WHEN o.market='spread' THEN o.line END) AS sp_line,
         MAX(CASE WHEN o.market='total'  THEN o.line END) AS to_line
  FROM event e LEFT JOIN opener o ON o.event_id=e.event_id
  WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
  GROUP BY e.event_id
)
SELECT b.*, r.spread_delta AS r_sp, r.total_delta AS r_to
FROM base b LEFT JOIN result r ON r.event_id=b.event_id
""").fetchall()

bad = 0
for r in rows:
    margin = abs(r["final_home"] - r["final_away"])
    total  = r["final_home"] + r["final_away"]
    exp_sp = None if r["sp_line"] is None else abs(margin - float(r["sp_line"]))
    exp_to = None if r["to_line"] is None else abs(total  - float(r["to_line"]))
    if (r["r_sp"] is not None and exp_sp is not None and abs(r["r_sp"]-exp_sp) > 1e-6) or \
       (r["r_to"] is not None and exp_to is not None and abs(r["r_to"]-exp_to) > 1e-6):
        bad += 1
        print(f"FI {r['event_id']}: stored ΔS={r['r_sp']} vs exp {exp_sp} | stored ΔT={r['r_to']} vs exp {exp_to} "
              f"| sp_line={r['sp_line']} to_line={r['to_line']} final={r['final_home']}-{r['final_away']}")
print("mismatches:", bad, "of", len(rows))
