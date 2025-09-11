# probe_api.py
import os, json
from dotenv import load_dotenv
import requests

load_dotenv()
TOKEN = os.getenv("BETSAPI_KEY")
LEAGUES = [int(x) for x in os.getenv("LEAGUE_IDS","").split(",") if x]
print("Token present?:", bool(TOKEN))
print("Leagues:", LEAGUES)

S = requests.Session()
S.params = {"token": TOKEN}
S.timeout = 20

def get(url, **params):
    r = S.get(url, params=params); r.raise_for_status()
    return r.json()

# 1) Bet365 upcoming (what your ETL currently uses)
for lid in LEAGUES:
    d = get("https://api.b365api.com/v1/bet365/upcoming", sport_id=18, league_id=lid)
    print(f"\nBet365 upcoming league {lid}: success={d.get('success')} count={len(d.get('results', []))}")
    if not d.get("results"):
        print("Sample payload:", d)

# 2) Generic EVENTS upcoming (fallback many plans include)
for lid in LEAGUES:
    d = get("https://api.b365api.com/v1/events/upcoming", sport_id=18, league_id=lid)
    print(f"\nEvents upcoming league {lid}: success={d.get('success')} count={len(d.get('results', []))}")
    if d.get("results"):
        print("Sample event:", json.dumps(d['results'][0], indent=2)[:800])
