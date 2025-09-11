import sqlite3

DB = "data/ebasketball.db"
with sqlite3.connect(DB) as con:
    cur = con.cursor()

    # Preview how many rows look numeric
    n_all = cur.execute("""
        SELECT COUNT(*) FROM opener
        WHERE opened_at_utc IS NOT NULL
          AND opened_at_utc <> ''
          AND opened_at_utc GLOB '[0-9][0-9]*'
    """).fetchone()[0]
    print("Numeric-looking opened_at_utc rows:", n_all)

    # Convert 13-digit ms epochs -> seconds; 10-digit seconds stay as-is.
    # Use COALESCE so we NEVER write NULL into a NOT NULL column.
    cur.execute("""
        UPDATE opener
        SET opened_at_utc = COALESCE(
            CASE
                WHEN opened_at_utc GLOB '[0-9][0-9]*' AND length(opened_at_utc) >= 13
                    THEN datetime(substr(opened_at_utc, 1, 10), 'unixepoch')
                WHEN opened_at_utc GLOB '[0-9][0-9]*'
                    THEN datetime(opened_at_utc, 'unixepoch')
                ELSE opened_at_utc
            END,
            opened_at_utc
        )
        WHERE opened_at_utc IS NOT NULL
          AND opened_at_utc <> ''
          AND opened_at_utc GLOB '[0-9][0-9]*'
    """)
    print("Epoch→ISO updates attempted:", cur.rowcount)

    # Fill any empty strings with current UTC so audits aren't broken
    cur.execute("""
        UPDATE opener
        SET opened_at_utc = datetime('now')
        WHERE opened_at_utc = ''
    """)
    print("Empty→now() fixes:", cur.rowcount)

    con.commit()

print("Done.")
