import os, json, requests
from dotenv import load_dotenv

load_dotenv()
S = requests.Session(); S.params = {"token": os.getenv("BETSAPI_KEY")}; S.timeout = 20

def dump(fi: int):
    url = "https://api.b365api.com/v3/bet365/prematch"
    r = S.get(url, params={"FI": fi})
    print(f"\nFI={fi} HTTP {r.status_code}  ->  {r.url}")
    try:
        data = r.json()
    except Exception as e:
        print("JSON error:", e, "body:", r.text[:500]); return
    print("success:", data.get("success"))
    results = data.get("results") or []
    print("results len:", len(results))
    if results:
        # show first 1 item compactly so we can see the structure
        first = results[0]
        print("top-level keys:", list(first.keys()))
        print("sample:", json.dumps(first, indent=2)[:1200])

# probe the two you have
dump(181036928)
dump(181036931)
