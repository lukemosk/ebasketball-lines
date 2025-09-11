# backfill_results_force.py
import os, sqlite3
from dotenv import load_dotenv
ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))
from src import betsapi

DB = "data/ebasketball.db"
THRESHOLDS = [2,3,4,5]

def q(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()

def exec_sql(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.execute(sql, args); con.commit()

rows = q("""
SELECT e.event_id, e.start_time_utc, e.home_name, e.away_name
FROM event e
LEFT JOIN result r ON r.event_id = e.event_id
WHERE r.event_id IS NULL
ORDER BY e.start_time_utc ASC
""")
print(f"events to check (force): {len(rows)}")

for r in rows:
    ev_id = int(r["event_id"])
    home, away = r["home_name"], r["away_name"]

    fast = betsapi.get_event_score_fast(ev_id)
    fh, fa = fast.get("final_home"), fast.get("final_away")
    ts = fast.get("time_status")

    if fh is None or fa is None:
        alt = betsapi.get_event_result(ev_id)
        if alt.get("final_home") is not None and alt.get("final_away") is not None:
            fh, fa = alt["final_home"], alt["final_away"]

    if fh is None or fa is None:
        print(f"- {ev_id}: pending (no score yet)  [{home} vs {away}] ts={ts}")
        continue

    exec_sql("UPDATE event SET final_home=?, final_away=? WHERE event_id=?",
             (int(fh), int(fa), ev_id))

    lr = q("""
        SELECT
            MAX(CASE WHEN market='spread' THEN line END) AS spread_line,
            MAX(CASE WHEN market='total'  THEN line END) AS total_line
        FROM opener WHERE event_id=?
    """, (ev_id,))
    spread_line = lr[0]["spread_line"] if lr else None
    total_line  = lr[0]["total_line"]  if lr else None

    margin = abs(int(fh) - int(fa))
    total_pts = int(fh) + int(fa)

    spread_delta = None
    total_delta  = None
    flags = {2:(None,None),3:(None,None),4:(None,None),5:(None,None)}

    if spread_line is not None:
        spread_delta = abs(margin - float(spread_line))
        for t in [2,3,4,5]:
            flags[t] = (spread_delta <= t, flags[t][1])

    if total_line is not None:
        total_delta = abs(total_pts - float(total_line))
        for t in [2,3,4,5]:
            prev = flags[t][0]
            flags[t] = (prev, total_delta <= t)

    exec_sql("""
        INSERT OR IGNORE INTO result(
            event_id,
            spread_delta, total_delta,
            within2_spread, within3_spread, within4_spread, within5_spread,
            within2_total,  within3_total,  within4_total,  within5_total
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        ev_id,
        spread_delta, total_delta,
        (flags[2][0] if flags[2][0] is not None else None),
        (flags[3][0] if flags[3][0] is not None else None),
        (flags[4][0] if flags[4][0] is not None else None),
        (flags[5][0] if flags[5][0] is not None else None),
        (flags[2][1] if flags[2][1] is not None else None),
        (flags[3][1] if flags[3][1] is not None else None),
        (flags[4][1] if flags[4][1] is not None else None),
        (flags[5][1] if flags[5][1] is not None else None),
    ))

    source = "event" if (fh is not None and fa is not None) else (
        "result" if ('alt' in locals() and alt.get('final_home') is not None and alt.get('final_away') is not None) else "none"
    )
    print(
        f"- {ev_id}: final {fh}-{fa} | src={source} ts={ts} "
        f"| spread_line={spread_line} total_line={total_line} "
        f"| Δspread={spread_delta} Δtotal={total_delta}"
    )
