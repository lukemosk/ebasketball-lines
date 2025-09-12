# analyze_accuracy.py
import sqlite3

DB = "data/ebasketball.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# Denominators: finished games that also have an opener for that market
counts = con.execute("""
WITH base AS (
  SELECT e.event_id,
         e.final_home, e.final_away,
         MAX(CASE WHEN o.market='spread' THEN o.line END) AS spread_line,
         MAX(CASE WHEN o.market='total'  THEN o.line END) AS total_line
  FROM event e
  LEFT JOIN opener o ON o.event_id = e.event_id
  WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
  GROUP BY e.event_id
)
SELECT
  SUM(CASE WHEN spread_line IS NOT NULL THEN 1 ELSE 0 END) AS denom_spread,
  SUM(CASE WHEN total_line  IS NOT NULL THEN 1 ELSE 0 END) AS denom_total
FROM base
""").fetchone()

denom_spread = counts["denom_spread"] or 0
denom_total  = counts["denom_total"]  or 0

# Use the precomputed flags in `result`
r = con.execute("""
SELECT
  SUM(CASE WHEN within2_spread THEN 1 ELSE 0 END) AS w2s,
  SUM(CASE WHEN within3_spread THEN 1 ELSE 0 END) AS w3s,
  SUM(CASE WHEN within4_spread THEN 1 ELSE 0 END) AS w4s,
  SUM(CASE WHEN within5_spread THEN 1 ELSE 0 END) AS w5s,
  SUM(CASE WHEN within2_total  THEN 1 ELSE 0 END) AS w2t,
  SUM(CASE WHEN within3_total  THEN 1 ELSE 0 END) AS w3t,
  SUM(CASE WHEN within4_total  THEN 1 ELSE 0 END) AS w4t,
  SUM(CASE WHEN within5_total  THEN 1 ELSE 0 END) AS w5t
FROM result
""").fetchone()

def pct(x, d):
    return f"{(100.0 * (x or 0) / d):.1f}%" if d else "n/a"

print("=== Denominators ===")
print(f"Spread: {denom_spread}  |  Total: {denom_total}\n")

print("=== Spread closeness (vs opener) ===")
print(f"±2: {r['w2s'] or 0} / {denom_spread}  ({pct(r['w2s'], denom_spread)})")
print(f"±3: {r['w3s'] or 0} / {denom_spread}  ({pct(r['w3s'], denom_spread)})")
print(f"±4: {r['w4s'] or 0} / {denom_spread}  ({pct(r['w4s'], denom_spread)})")
print(f"±5: {r['w5s'] or 0} / {denom_spread}  ({pct(r['w5s'], denom_spread)})\n")

print("=== Total closeness (vs opener) ===")
print(f"±2: {r['w2t'] or 0} / {denom_total}  ({pct(r['w2t'], denom_total)})")
print(f"±3: {r['w3t'] or 0} / {denom_total}  ({pct(r['w3t'], denom_total)})")
print(f"±4: {r['w4t'] or 0} / {denom_total}  ({pct(r['w4t'], denom_total)})")
print(f"±5: {r['w5t'] or 0} / {denom_total}  ({pct(r['w5t'], denom_total)})")
