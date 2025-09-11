import os, requests, json
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BETSAPI_KEY")
S = requests.Session()
S.params = {"token": TOKEN}
S.timeout = 20

def safe_name(v):
    if isinstance(v, dict):
        v = v.get("name") or v.get("league_name") or ""
    return str(v).strip().lower()

# --- Check UPCOMING fixtures (first 6 pages)
all_rows = []
for p in range(1, 7):
    r = S.get("https://api.b365api.com/v1/bet365/upcoming", params={"page": p})
    r.raise_for_status()
    data = r.json()
    rows = data.get("results") or []
    if not rows:
        break
    all_rows.extend(rows)

h2h_upcoming = [
    r for r in all_rows
    if "ebasketball h2h gg league - 4x5mins" in safe_name(r.get("league") or r.get("league_name"))
]

print(f"Total upcoming rows: {len(all_rows)}")
print(f"H2H GG upcoming rows: {len(h2h_upcoming)}")
print(json.dumps([
    {
        "id": r.get("id"),
        "home": r.get("home")["name"] if isinstance(r.get("home"), dict) else r.get("home"),
        "away": r.get("away")["name"] if isinstance(r.get("away"), dict) else r.get("away"),
        "time": r.get("time"),
        "time_status": r.get("time_status")
    }
    for r in h2h_upcoming[:5]
], indent=2, ensure_ascii=False))

# --- Check INPLAY fixtures
r = S.get("https://api.b365api.com/v1/bet365/inplay")
r.raise_for_status()
data = r.json()

def flatten(results):
    flat, stack = [], list(results or [])
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if "events" in x and isinstance(x["events"], list):
                stack.extend(x["events"])
            elif "id" in x and ("home" in x or "away" in x):
                flat.append(x)
            else:
                for v in x.values():
                    if isinstance(v, (list, dict)):
                        stack.append(v)
        elif isinstance(x, list):
            stack.extend(x)
    return flat

rows = flatten(data.get("results"))
h2h_inplay = [
    r for r in rows
    if "ebasketball h2h gg league - 4x5mins" in safe_name(r.get("league") or r.get("league_name"))
]

print(f"\nTotal inplay rows: {len(rows)}")
print(f"H2H GG inplay rows: {len(h2h_inplay)}")
print(json.dumps([
    {
        "id": r.get("id"),
        "home": r.get("home")["name"] if isinstance(r.get("home"), dict) else r.get("home"),
        "away": r.get("away")["name"] if isinstance(r.get("away"), dict) else r.get("away"),
        "time": r.get("time"),
        "time_status": r.get("time_status")
    }
    for r in h2h_inplay[:5]
], indent=2, ensure_ascii=False))
