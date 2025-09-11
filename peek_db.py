# peek_db.py
import os, sqlite3, pathlib

DB = "data/ebasketball.db"
abs_path = str(pathlib.Path(DB).resolve())
print("DB path:", abs_path, "\n")

with sqlite3.connect(DB) as con:
    con.row_factory = sqlite3.Row

    def show_table(name):
        print(f"--- {name} schema ---")
        for r in con.execute(f"PRAGMA table_info({name})"):
            # columns: cid, name, type, notnull, dflt_value, pk
            print(dict(zip(("cid","name","type","notnull","dflt","pk"), r)))
        print()

    show_table("event")
    show_table("opener")
    show_table("result")

    print("--- opener rows (top 10) ---")
    for r in con.execute("SELECT * FROM opener LIMIT 10"):
        print(dict(r))
    print()

    print("--- counts ---")
    for t in ("event","opener","result","odds_snapshot","quarter_line"):
        try:
            c = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"{t}: {c}")
        except Exception as e:
            print(f"{t}: <error> {e}")
