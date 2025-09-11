# peek_openers_now.py
import os, sqlite3, requests, json
from dotenv import load_dotenv

load_dotenv()
S = requests.Session(); S.params = {"token": os.getenv("BETSAPI_KEY")}; S.timeout = 20
DB = "data/ebasketball.db"

def events_missing_openers():
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute("""
        SELECT e.event_id, e.home_name, e.away_name, e.start_time_utc
        FROM event e
        LEFT JOIN opener o ON o.event_id = e.event_id
        WHERE o.event_id IS NULL
        ORDER BY e.start_time_utc
        """).fetchall()

def prematch(fi: int):
    r = S.get("https://api.b365api.com/v3/bet365/prematch", params={"FI": fi})
    r.raise_for_status()
    return r.json()

rows = events_missing_openers()
print(f"events missing openers: {len(rows)}")
for r in rows:
    fi = int(r["event_id"])
    d = prematch(fi)
    res = d.get("results") or []
    print(f"\nFI={fi} {r['home_name']} vs {r['away_name']} @ {r['start_time_utc']}")
    if not res:
        print("  prematch: results=0 (no markets yet)")
        continue
    main = (res[0] or {}).get("main") or {}
    gl = ((main.get("sp") or {}).get("game_lines") or {})
    odds = gl.get("odds")
    print(f"  prematch: results={len(res)} | has game_lines odds? {'yes' if isinstance(odds,list) else 'no'}")
    if isinstance(odds, list):
        sample = [o for o in odds if o.get("name") in ("Spread","Total")][:6]
        print("  sample:", json.dumps(sample, indent=2)[:600])
