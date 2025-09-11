import sqlite3

DB = "data/ebasketball.db"
# 4x5 sims won't realistically have totals > ~125.
TOTAL_MAX = 125.0

with sqlite3.connect(DB) as con:
    con.row_factory = sqlite3.Row

    # Show worst offenders (optional)
    rows = con.execute("""
        SELECT e.event_id, e.home_name, e.away_name, o.line AS total_line,
               (e.final_home + e.final_away) AS total_pts,
               ABS((e.final_home + e.final_away) - o.line) AS delta, o.opened_at_utc
        FROM event e
        JOIN opener o ON o.event_id=e.event_id AND o.market='total'
        WHERE e.final_home IS NOT NULL
        ORDER BY delta DESC
        LIMIT 20
    """).fetchall()
    print("Worst 20 total deltas (before purge):")
    for r in rows:
        print(dict(r))

    cur = con.cursor()
    cur.execute("DELETE FROM opener WHERE market='total' AND line > ?", (TOTAL_MAX,))
    print("Deleted total openers >", TOTAL_MAX, "rows:", cur.rowcount)

    cur.execute("DELETE FROM result")
    print("Deleted all result rows:", cur.rowcount)

    con.commit()
print("Done.")
