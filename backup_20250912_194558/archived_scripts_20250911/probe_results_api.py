# probe_results_api.py
import os, json, sqlite3, requests
from dotenv import load_dotenv

load_dotenv()
S = requests.Session()
S.params = {"token": os.getenv("BETSAPI_KEY")}
S.timeout = 20

DB = "data/ebasketball.db"

def fetch_fis_needing_finals():
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name
            FROM event
            WHERE final_home IS NULL OR final_away IS NULL
            ORDER BY start_time_utc
        """).fetchall()
    return rows

def get_result(fi: int):
    r = S.get("https://api.b365api.com/v1/bet365/result", params={"FI": fi})
    print(f"\nFI={fi} HTTP {r.status_code} -> {r.url}")
    try:
        data = r.json()
    except Exception as e:
        print("JSON error:", e, "body:", r.text[:500]); return None
    print("success:", data.get("success"))
    rs = data.get("results") or []
    print("results len:", len(rs))
    # probe_results_api.py (replace the print block inside get_result)
    if rs:
        ss = rs[0].get("SS") or rs[0].get("ss")
        print("SS:", ss)
        if not ss:
            # show more so we can see what's in there
            print("raw:", json.dumps(rs[0], indent=2))
    return data

if __name__ == "__main__":
    rows = fetch_fis_needing_finals()
    print("events needing finals:", len(rows))
    for r in rows[:20]:
        print(f"{r['event_id']} {r['home_name']} vs {r['away_name']} @ {r['start_time_utc']}")
        get_result(int(r["event_id"]))
