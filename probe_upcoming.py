import os, requests, collections
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BETSAPI_KEY")
S = requests.Session()
S.params = {"token": TOKEN}
S.timeout = 20

def get(page=1):
    r = S.get("https://api.b365api.com/v1/bet365/upcoming", params={"sport_id":18, "page":page})
    r.raise_for_status()
    return r.json()

all_rows = []
for page in range(1, 6):
    d = get(page)
    rows = d.get("results") or []
    if not rows:
        break
    all_rows.extend(rows)

print(f"Total upcoming basketball rows fetched: {len(all_rows)}")

# --- safely extract league names ---
def safe_league_name(r):
    val = r.get("league") or r.get("league_name") or ""
    if isinstance(val, dict):
        # Bet365 sometimes nests {"id": "...", "name": "..."}
        val = val.get("name") or val.get("league_name") or ""
    return str(val).strip().lower()

# Count unique league names
ctr = collections.Counter([safe_league_name(r) for r in all_rows])
print("\nTop league names:")
for name, cnt in ctr.most_common(40):
    print(f"{cnt:4d}  {name}")

# Show a few sample rows for suspected ebasketball leagues
def looks_like_ebasketball(name:str)->bool:
    name = (name or "").lower()
    return any(s in name for s in [
        "ebasketball", "e-basketball", "gg league", "h2h gg", "4x5", "blitz"
    ])

samples = [r for r in all_rows if looks_like_ebasketball(safe_league_name(r))]
print(f"\nSuspected ebasketball samples: {len(samples)}")
for r in samples[:10]:
    print({
        "id": r.get("id"),
        "league": safe_league_name(r),
        "home": r.get("home"),
        "away": r.get("away"),
        "time": r.get("time"),
        "time_status": r.get("time_status"),
    })
