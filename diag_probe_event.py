# diag_probe_event.py
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from src import betsapi

IDS = [
    181084210,  # most recent
    181084141,
    181084201,  # ~110m old
    181084132,  # ~114m old
    181084062,  # ~118m old
]

for eid in IDS:
    print(f"\n=== FI {eid} ===")

    fast = betsapi.get_event_score_fast(eid)
    ts = (fast or {}).get("time_status")
    fhf = (fast or {}).get("final_home")
    faf = (fast or {}).get("final_away")
    ss  = (fast or {}).get("ss")
    print(f"/event: time_status={ts} final_home={fhf} final_away={faf} ss={ss}")

    res = betsapi.get_event_result(eid)
    fhr = (res or {}).get("final_home")
    far = (res or {}).get("final_away")
    st  = (res or {}).get("status")  # sometimes shows 'ended', 'postponed', etc.
    print(f"/v1/bet365/result: status={st} final_home={fhr} final_away={far}")
