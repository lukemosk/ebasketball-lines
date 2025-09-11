# clean_suspect_results.py
from __future__ import annotations
import sqlite3, argparse
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

DB = "data/ebasketball.db"
from src import betsapi

def q(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()

def execmany(ops):
    with sqlite3.connect(DB) as con:
        for sql, args in ops:
            con.execute(sql, args)
        con.commit()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=180, help="Lookback window")
    ap.add_argument("--fix", action="store_true", help="Apply fixes (delete result row and clear finals)")
    args = ap.parse_args()

    rows = q(f"""
    SELECT e.event_id, e.start_time_utc, e.final_home, e.final_away,
           r.event_id IS NOT NULL AS has_result
    FROM event e
    LEFT JOIN result r ON r.event_id = e.event_id
    WHERE e.start_time_utc >= datetime('now', ?)
    ORDER BY e.start_time_utc DESC
    """, (f"-{args.minutes} minutes",))

    suspects = []
    for r in rows:
        eid = int(r["event_id"])
        if not bool(r["has_result"]):
            continue
        fast = betsapi.get_event_score_fast(eid) or {}
        ts = (fast.get("time_status") or "").strip()
        res = betsapi.get_event_result(eid) or {}
        fhr, far = res.get("final_home"), res.get("final_away")
        finished = (ts == "3") or (fhr is not None and far is not None)
        if not finished:
            suspects.append((eid, r["start_time_utc"], ts, r["final_home"], r["final_away"]))

    if not suspects:
        print("No suspects.")
        return

    print(f"Found {len(suspects)} suspect event(s):")
    for eid, st, ts, fh, fa in suspects:
        print(f"- {eid} start={st} ts={ts or 'None'} event.final={fh}-{fa}")

    if args.fix:
        ops = []
        for eid, *_ in suspects:
            ops.append(("DELETE FROM result WHERE event_id=?", (eid,)))
            ops.append(("UPDATE event SET final_home=NULL, final_away=NULL WHERE event_id=?", (eid,)))
        execmany(ops)
        print("Cleaned suspect result rows and cleared finals.")

if __name__ == "__main__":
    main()
