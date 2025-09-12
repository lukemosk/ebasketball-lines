# probe_inplay.py
import os, requests, collections
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BETSAPI_KEY")
S = requests.Session(); S.params = {"token": TOKEN}; S.timeout = 20

def get_inplay(**params):
    r = S.get("https://api.b365api.com/v1/bet365/inplay", params=params)
    r.raise_for_status()
    return r.json()

def flatten(results):
    """Flatten results into a list of event dicts, handling nested shapes."""
    flat = []
    stack = list(results or [])
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            # common nesting: {"sport_id":..., "events":[...]}
            if "events" in x and isinstance(x["events"], list):
                stack.extend(x["events"])
            # event-like dicts have id/home/away/time_status/etc.
            elif "id" in x and ("home" in x or "away" in x):
                flat.append(x)
            else:
                # unknown dict shape: scan values
                for v in x.values():
                    if isinstance(v, (list, dict)):
                        stack.append(v)
        elif isinstance(x, list):
            stack.extend(x)
    return flat

def safe_league_name(ev):
    v = ev.get("league") or ev.get("league_name") or ""
    if isinstance(v, dict):
        v = v.get("name") or v.get("league_name") or ""
    return str(v).strip().lower()

def looks_like_ebasketball(name:str)->bool:
    name = (name or "").lower()
    return any(s in name for s in ["ebasketball", "h2h gg", "gg league", "4x5", "blitz"])

# 1) try basketball-only
d = get_inplay(sport_id=18)
rows = flatten(d.get("results"))
print("Basketball inplay event rows (flattened):", len(rows))

# 2) fallback all-sport
if not rows:
    d = get_inplay()
    rows = flatten(d.get("results"))
    print("All-sport inplay event rows (flattened):", len(rows))

ctr = collections.Counter(safe_league_name(r) for r in rows)
print("\nTop inplay league names (first 40):")
for name, cnt in ctr.most_common(40):
    print(f"{cnt:4d}  {name}")

hits = [r for r in rows if looks_like_ebasketball(safe_league_name(r))]
print(f"\nSuspected ebasketball/H2H GG live rows: {len(hits)}")
for r in hits[:10]:
    print({
        "id": r.get("id"),
        "league": safe_league_name(r),
        "home": r.get("home"),
        "away": r.get("away"),
        "time_status": r.get("time_status"),
    })
