import os, requests, json
from dotenv import load_dotenv

load_dotenv()
tok = os.getenv("BETSAPI_KEY")
S = requests.Session(); S.params = {"token": tok}; S.timeout = 20

def show(tag, url, **params):
    try:
        r = S.get(url, params=params)
        print(f"\n[{tag}] HTTP {r.status_code}  url={r.url}")
        try:
            data = r.json()
        except Exception as e:
            print("JSON decode failed:", e)
            print("Body:", r.text[:500])
            return
        print("payload keys:", list(data.keys()))
        print("success:", data.get("success"), "error:", data.get("error"), "detail:", data.get("error_detail"))
        if isinstance(data.get("results"), list):
            print("results len:", len(data["results"]))
            # show first item briefly
            if data["results"]:
                print("sample:", json.dumps(data["results"][0], ensure_ascii=False)[:400])
        else:
            print("results type:", type(data.get("results")))
    except Exception as e:
        print(f"[{tag}] request error:", e)

BASE = "https://api.b365api.com/v1/bet365"
show("UPCOMING p1", f"{BASE}/upcoming", page=1)          # all sports
show("UPCOMING p1 + sport", f"{BASE}/upcoming", page=1, sport_id=18)  # basketball filter
show("INPLAY all", f"{BASE}/inplay")
show("INPLAY basketball", f"{BASE}/inplay", sport_id=18)
