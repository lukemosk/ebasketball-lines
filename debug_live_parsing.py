# debug_live_parsing.py - Debug the live game parsing issue
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import requests
import os
import json
from live_quarter_monitor import LiveQuarterMonitor

def debug_live_parsing():
    print("🔍 DEBUGGING LIVE GAME PARSING")
    print("=" * 60)
    
    monitor = LiveQuarterMonitor()
    
    # First, get the live games
    live_games = monitor.get_live_games_from_api()
    print(f"Step 1: Found {len(live_games)} live games")
    
    if not live_games:
        print("❌ No live games found - can't debug parsing")
        return
    
    # Test the first live game
    game = live_games[0]
    event_id = int(game['event_id'])
    
    print(f"Step 2: Testing FI {event_id}: {game['home_name']} vs {game['away_name']}")
    
    # Get the raw API response
    try:
        token = os.getenv("BETSAPI_KEY")
        url = f"https://api.b365api.com/v1/bet365/event?FI={event_id}&token={token}&stats=1"
        
        print(f"Step 3: Making API call to {url}")
        response = requests.get(url, timeout=15)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Save the response for inspection
            with open("debug_response.json", "w") as f:
                json.dump(data, f, indent=2)
            print("✅ Saved raw response to debug_response.json")
            
            # Check the basic structure
            print(f"Response keys: {list(data.keys())}")
            results = data.get('results', [])
            print(f"Results length: {len(results)}")
            
            if results:
                print(f"First result type: {type(results[0])}")
                
                # Look for EV type objects
                ev_objects = []
                for i, item in enumerate(results):
                    if isinstance(item, dict):
                        item_type = item.get('type')
                        if item_type == 'EV':
                            ev_objects.append((i, item))
                
                print(f"Found {len(ev_objects)} EV-type objects")
                
                if ev_objects:
                    idx, ev_obj = ev_objects[0]
                    print(f"\nEV object at index {idx}:")
                    print(f"  Keys: {list(ev_obj.keys())}")
                    
                    # Check for our target fields
                    target_fields = ['SS', 'TM', 'TS', 'TT']
                    for field in target_fields:
                        value = ev_obj.get(field)
                        print(f"  {field}: {value} (type: {type(value)})")
                    
                    # Test our parsing logic
                    print(f"\nStep 4: Testing our parsing logic...")
                    status = monitor.get_live_game_status(event_id)
                    print(f"Parsed status: {status}")
                    
                    if not status or not status.get('is_live'):
                        print("❌ Parsing failed or game not detected as live")
                        print("Raw field values from EV object:")
                        for field in ['SS', 'TM', 'TS', 'TT']:
                            print(f"  {field}: {repr(ev_obj.get(field))}")
                    else:
                        print("✅ Parsing successful!")
                        
                else:
                    print("❌ No EV-type objects found in results")
                    print("Available object types:")
                    for i, item in enumerate(results[:10]):  # Show first 10
                        if isinstance(item, dict):
                            print(f"  [{i}] type: {item.get('type', 'NO_TYPE')}")
            
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"❌ Exception during API call: {e}")

if __name__ == "__main__":
    debug_live_parsing()
    