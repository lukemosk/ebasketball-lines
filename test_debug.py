# test_debug.py - Debug the API response
from live_quarter_monitor import LiveQuarterMonitor
import requests
import os
import json

def debug_api_call():
    event_id = 181160727  # One of your live games
    token = os.getenv("BETSAPI_KEY")
    url = f"https://api.b365api.com/v1/bet365/event?FI={event_id}&token={token}&stats=1"
    
    print(f"Debug API call for FI {event_id}")
    print(f"URL: {url}")
    
    response = requests.get(url, timeout=15)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success')}")
        
        results = data.get('results', [])
        print(f"Results length: {len(results)}")
        
        if results:
            # Save to file for inspection
            with open("debug_live_response.json", "w") as f:
                json.dump(data, f, indent=2)
            print("Saved response to debug_live_response.json")
            
            # Look for EV type
            for i, item in enumerate(results):
                if isinstance(item, dict):
                    print(f"Item {i}: type={item.get('type')}, keys={list(item.keys())[:10]}")
                    
                    if item.get('type') == 'EV':
                        print(f"Found EV item:")
                        print(f"  SS: {item.get('SS')}")
                        print(f"  TM: {item.get('TM')}")
                        print(f"  TS: {item.get('TS')}")
                        print(f"  TT: {item.get('TT')}")
                        break
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    debug_api_call()
    