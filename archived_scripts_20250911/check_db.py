import sqlite3

db = r"data/ebasketball.db"
con = sqlite3.connect(db)
cur = con.cursor()

for t in ("event","opener","result","odds_snapshot","quarter_line"):
    try:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t}: {n}")
    except Exception as e:
        print(f"{t}: (table missing) {e}")

print("\nSample events:")
rows = cur.execute("""
    SELECT event_id, league_id, start_time_utc, status, home_name, away_name
    FROM event ORDER BY start_time_utc DESC LIMIT 5
""").fetchall()
for r in rows:
    print(r)

con.close()
