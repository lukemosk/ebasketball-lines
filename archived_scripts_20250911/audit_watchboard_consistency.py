# audit_watchboard_consistency.py (v2)
from __future__ import annotations
import sqlite3
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

DB = "data/ebasketball.db"
from src import betsapi

LOOKBACK_MINUTES = 180

def q(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()

def parse_ss(ss: str):
    if isinstance(ss, str) and "-" in ss:
        try:
            l, r = ss.split("-", 1)
            return int(l), int(r)
        except Exception:
            return None
    return None

rows = q(f"""
SELECT
  e.event_id, e.start_time_utc, e.home_name, e.away_name,
  e.final_home, e.final_away,
  r.event_id IS NOT NULL AS has_result
FROM event e
LEFT JOIN result r ON r.event_id = e.event_id
WHERE e.start_time_utc >= datetime('now', ?)
ORDER BY e.start_time_utc DESC
""", (f"-{LOOKBACK_MINUTES} minutes",))

suspects = []
ok = []

for r in rows:
    if not bool(r["has_result"]):
        continue

    eid = int(r["event_id"])
    db_fh, db_fa = r["final_home"], r["final_away"]

    fast = betsapi.get_event_score_fast(eid) or {}
    ts = (fast.get("time_status") or "").strip()
    fast_fh, fast_fa = fast.get("final_home"), fast.get("final_away")
    ss_pair = parse_ss(fast.get("ss"))

    res = betsapi.get_event_result(eid) or {}
    res_fh, res_fa = res.get("final_home"), res.get("final_away")

    finished_by = []
    if ts == "3":
        finished_by.append("fast-ts=3")
    if fast_fh is not None and fast_fa is not None:
        finished_by.append("fast-finals")
    if res_fh is not None and res_fa is not None:
        finished_by.append("result-finals")
    if ss_pair and db_fh is not None and db_fa is not None and tuple(ss_pair) == (int(db_fh), int(db_fa)):
        finished_by.append("fast-ss==db")

    if finished_by:
        ok.append((eid, r["start_time_utc"], ",".join(finished_by), db_fh, db_fa))
    else:
        suspects.append((eid, r["start_time_utc"], ts or "None", db_fh, db_fa))

if ok:
    print("DB-settled events confirmed finished by API signals:")
    for eid, st, by, fh, fa in ok:
        print(f"- {eid} | start={st} | by={by} | final={fh}-{fa}")
    print()

if not suspects:
    print("No inconsistencies: all DB-settled events are finished per API.")
else:
    print("Inconsistent events (DB says settled; API gave no finishing signal):")
    for eid, st, ts, fh, fa in suspects:
        print(f"- {eid} | start={st} | ts={ts} | event.final={fh}-{fa}")
