# fix_stray_finals.py
import sqlite3

DB = "data/ebasketball.db"

with sqlite3.connect(DB) as con:
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT e.event_id, e.final_home, e.final_away
        FROM event e
        LEFT JOIN result r ON r.event_id = e.event_id
        WHERE r.event_id IS NULL
          AND e.final_home IS NOT NULL
          AND e.final_away IS NOT NULL
    """).fetchall()

    if not rows:
        print("No stray finals to clear.")
    else:
        print(f"Clearing {len(rows)} stray finals…")
        con.executemany(
            "UPDATE event SET final_home=NULL, final_away=NULL WHERE event_id=?",
            [(int(r["event_id"]),) for r in rows]
        )
        con.commit()
        print("Done.")
