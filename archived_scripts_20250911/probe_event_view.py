# probe_event_view.py
import os, requests, json, sqlite3
from dotenv import load_dotenv

load_dotenv()
S = requests.Session(); S.params = {"token": os.getenv("BETSAPI_KEY")}; S.timeout = 20
DB = "data/ebasketball.db"

def get_event_id_from_prematch(fi: int) -> str|None:
    d = S.get("https://api.b365api.com/v3/bet365/prematch", params={"FI": fi}).json()
    rs = d.get("results") or []
    if not rs: return None
    return rs[0].get("event_id")

def get_view(event_id: str):
    d = S.get("https://api.b365api.com/v1/event/view", params={"event_id": event_id}).json()
    return d

with sqlite3.connect(DB) as con:
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT event_id, home_name, away_name, start_time_utc
        FROM event
        WHERE final_home IS NULL
        ORDER BY start_time_utc ASC
        LIMIT 25
    """).fetchall()

print("Checking", len(rows), "events")
for r in rows:
    fi = int(r["event_id"])
    print(f"\nFI={fi}  {r['home_name']} vs {r['away_name']} @ {r['start_time_utc']}")
    ev_id = get_event_id_from_prematch(fi)
    print("  prematch.event_id:", ev_id)
    if not ev_id:
        print("  (no prematch)"); continue
    view = get_view(ev_id)
    rs = (view or {}).get("results") or []
    if not rs:
        print("  /event/view: no results"); continue
    top = rs[0]
    ss = top.get("ss") or top.get("SS")
    print("  /event/view ss:", ss)
    # optionally print teams/scores payload to inspect:
    # print("  raw:", json.dumps(top, indent=2)[:800])
