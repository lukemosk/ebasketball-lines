# repair_recent_finals.py
from __future__ import annotations
import sqlite3
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

DB = "data/ebasketball.db"
from src import betsapi

def q(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()

def exec_sql(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.execute(sql, args); con.commit()

def get_true_prematch_openers(con, eid):
    con.row_factory = sqlite3.Row
    row = con.execute("""
        WITH start AS (SELECT start_time_utc AS st FROM event WHERE event_id=?),
        sp AS (SELECT line FROM opener WHERE event_id=? AND market='spread' AND opened_at_utc < (SELECT st FROM start) ORDER BY opened_at_utc ASC LIMIT 1),
        tt AS (SELECT line FROM opener WHERE event_id=? AND market='total'  AND opened_at_utc < (SELECT st FROM start) ORDER BY opened_at_utc ASC LIMIT 1)
        SELECT (SELECT line FROM sp) AS sp_line, (SELECT line FROM tt) AS to_line
    """, (eid, eid, eid)).fetchone()
    return (row["sp_line"] if row else None, row["to_line"] if row else None)

def upsert_result(eid, fh, fa):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        sp, to = get_true_prematch_openers(con, eid)
        margin, total = abs(fh-fa), fh+fa
        sd = td = None
        w2s=w3s=w4s=w5s = None
        w2t=w3t=w4t=w5t = None
        if sp is not None:
            sd = abs(margin - float(sp))
            w2s, w3s, w4s, w5s = sd<=2, sd<=3, sd<=4, sd<=5
        if to is not None:
            td = abs(total - float(to))
            w2t, w3t, w4t, w5t = td<=2, td<=3, td<=4, td<=5
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_result_event ON result(event_id)")
        con.execute("""
            INSERT INTO result(event_id,spread_delta,total_delta,
                               within2_spread,within3_spread,within4_spread,within5_spread,
                               within2_total, within3_total, within4_total, within5_total)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET
              spread_delta=excluded.spread_delta, total_delta=excluded.total_delta,
              within2_spread=excluded.within2_spread, within3_spread=excluded.within3_spread,
              within4_spread=excluded.within4_spread, within5_spread=excluded.within5_spread,
              within2_total=excluded.within2_total, within3_total=excluded.within3_total,
              within4_total=excluded.within4_total, within5_total=excluded.within5_total
        """, (eid, sd, td, w2s,w3s,w4s,w5s, w2t,w3t,w4t,w5t))
        con.commit()

def main():
    rows = q("""
        SELECT event_id, final_home, final_away
        FROM event
        WHERE start_time_utc >= datetime('now','-6 hours')
        ORDER BY start_time_utc DESC
    """)
    fixed = 0
    for r in rows:
        eid = int(r["event_id"])
        cur_fh, cur_fa = r["final_home"], r["final_away"]

        # Prefer authoritative result
        res = betsapi.get_event_result(eid) or {}
        fh, fa = res.get("final_home"), res.get("final_away")

        # Fallback: fast endpoint ONLY if finished
        if fh is None or fa is None:
            fast = betsapi.get_event_score_fast(eid) or {}
            ts = (fast.get("time_status") or "").strip()
            if ts == "3":
                fh, fa = fast.get("final_home"), fast.get("final_away")
                if (fh is None or fa is None) and isinstance(fast.get("ss"), str) and "-" in fast["ss"]:
                    try:
                        l, a = fast["ss"].split("-", 1)
                        fh, fa = int(l), int(a)
                    except Exception:
                        pass

        if fh is None or fa is None:
            continue

        fh, fa = int(fh), int(fa)
        if cur_fh != fh or cur_fa != fa:
            exec_sql("UPDATE event SET final_home=?, final_away=? WHERE event_id=?", (fh, fa, eid))
            upsert_result(eid, fh, fa)
            fixed += 1
            print(f"fixed {eid}: ({cur_fh},{cur_fa}) -> ({fh},{fa})")

    print(f"Done. Updated {fixed} event(s).")

if __name__ == "__main__":
    main()
