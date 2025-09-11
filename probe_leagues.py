# probe_leagues.py
import os, requests, itertools
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("BETSAPI_KEY")
S = requests.Session(); S.params = {"token": TOKEN}; S.timeout = 20

def get(path, **params):
    r = S.get(f"https://api.b365api.com/v1/bet365/{path}", params=params)
    r.raise_for_status()
    return r.json()

def safe_name(x):
    v = x.get("name") or x.get("league_name") or x.get("league") or ""
    if isinstance(v, dict):
        v = v.get("name") or v.get("league_name") or ""
    return str(v).strip()

def list_leagues_for_sport(sport_id=None, pages=10):
    leagues = []
    for p in range(1, pages+1):
        params = {"page": p}
        if sport_id is not None:
            params["sport_id"] = sport_id
        try:
            d = get("leagues", **params)
        except requests.HTTPError as e:
            print(f"leagues page {p} failed: {e}")
            break
        rows = d.get("results") or []
        if not rows: break
        leagues.extend(rows)
    return leagues

targets = ["ebasketball", "h2h gg", "gg league", "blitz", "4x5"]

# try basketball-only first, then all-sports
for sid, label in [(18, "basketball-only"), (None, "all-sports")]:
    leagues = list_leagues_for_sport(sid)
    print(f"\n[{label}] leagues returned: {len(leagues)}")
    hits = [L for L in leagues if any(t in safe_name(L).lower() for t in targets)]
    print(f"matches to {targets}: {len(hits)}")
    for L in hits[:25]:
        print({"id": L.get("id"), "name": safe_name(L), "sport_id": L.get("sport_id")})
