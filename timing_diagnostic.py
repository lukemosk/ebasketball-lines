# timing_diagnostic.py - Understand the actual timing data from API
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import requests
import os
import json
from datetime import datetime, timezone

def get_live_games():
    """Get live games from inplay_filter"""
    token = os.getenv("BETSAPI_KEY")
    url = f"https://api.b365api.com/v1/bet365/inplay_filter?sport_id=18&token={token}"
    
    response = requests.get(url, timeout=15)
    if response.status_code != 200:
        return []
    
    data = response.json()
    results = data.get('results', [])
    
    ebasketball_games = []
    for game in results:
        if not isinstance(game, dict):
            continue
            
        league = game.get('league', {})
        if isinstance(league, dict):
            league_name = league.get('name', '')
        else:
            league_name = str(league)
        
        league_name = league_name.lower()
        
        if ('ebasketball h2h gg league' in league_name and 
            '4x5mins' in league_name and 
            'battle' not in league_name):
            
            ebasketball_games.append({
                'id': game.get('id'),
                'home': game.get('home', {}).get('name', 'Unknown') if isinstance(game.get('home'), dict) else str(game.get('home', 'Unknown')),
                'away': game.get('away', {}).get('name', 'Unknown') if isinstance(game.get('away'), dict) else str(game.get('away', 'Unknown')),
                'ss': game.get('ss', ''),
                'time_status': game.get('time_status', '0')
            })
    
    return ebasketball_games

def get_detailed_timing(event_id):
    """Get detailed timing from bet365/event endpoint"""
    token = os.getenv("BETSAPI_KEY")
    url = f"https://api.b365api.com/v1/bet365/event?FI={event_id}&token={token}&stats=1"
    
    response = requests.get(url, timeout=15)
    if response.status_code != 200:
        return None, f"HTTP {response.status_code}"
    
    data = response.json()
    
    # Save the raw response for inspection
    with open(f"debug_detailed_{event_id}_{datetime.now().strftime('%H%M%S')}.json", "w") as f:
        json.dump(data, f, indent=2)
    
    return data, "success"

def find_ev_object(data):
    """Find the EV object in the response"""
    if isinstance(data, dict):
        if data.get('type') == 'EV':
            return data
        for value in data.values():
            result = find_ev_object(value)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_ev_object(item)
            if result:
                return result
    return None

def analyze_timing_fields():
    """Analyze what the timing fields actually mean"""
    print("🔍 BASKETBALL TIMING DIAGNOSTIC")
    print("=" * 50)
    
    # Get live games
    live_games = get_live_games()
    
    if not live_games:
        print("No live eBasketball games found")
        return
    
    print(f"Found {len(live_games)} live games\n")
    
    for i, game in enumerate(live_games):
        event_id = game['id']
        print(f"Game {i+1}: FI {event_id}")
        print(f"Teams: {game['home']} vs {game['away']}")
        print(f"inplay_filter data:")
        print(f"  ss (score): '{game['ss']}'")
        print(f"  time_status: '{game['time_status']}'")
        
        # Get detailed data
        detailed_data, status = get_detailed_timing(event_id)
        
        if status != "success":
            print(f"  ❌ Failed to get detailed data: {status}")
            continue
        
        # Find EV object
        ev_obj = find_ev_object(detailed_data)
        
        if not ev_obj:
            print(f"  ❌ No EV object found in detailed data")
            continue
        
        print(f"bet365/event EV data:")
        print(f"  SS: '{ev_obj.get('SS', 'N/A')}'")
        print(f"  TM: {ev_obj.get('TM', 'N/A')} (minutes?)")
        print(f"  TS: {ev_obj.get('TS', 'N/A')} (seconds?)")
        print(f"  TT: {ev_obj.get('TT', 'N/A')} (timer status?)")
        
        # Compare scores
        inplay_score = game['ss']
        detailed_score = ev_obj.get('SS', '')
        
        if inplay_score != detailed_score:
            print(f"  ⚠️  SCORE MISMATCH!")
            print(f"      inplay_filter: '{inplay_score}'")
            print(f"      bet365/event:  '{detailed_score}'")
        else:
            print(f"  ✅ Scores match: '{inplay_score}'")
        
        # Try to interpret timing
        try:
            tm = int(ev_obj.get('TM', 0))
            ts = int(ev_obj.get('TS', 0)) 
            tt = str(ev_obj.get('TT', '0'))
            
            print(f"Timing interpretation attempts:")
            
            # Theory 1: TM=quarter minutes, TS=quarter seconds
            print(f"  Theory 1 (TM=min, TS=sec in quarter): {tm}:{ts:02d} elapsed, timer {'running' if tt=='1' else 'stopped'}")
            
            # Theory 2: TM=total minutes, TS=total seconds  
            total_seconds = tm * 60 + ts
            quarter_est = (total_seconds // 300) + 1
            remaining_in_q = 300 - (total_seconds % 300)
            print(f"  Theory 2 (TM+TS=total time): {total_seconds}s total = Q{quarter_est}, {remaining_in_q}s left in quarter")
            
            # Theory 3: Different meanings entirely
            print(f"  Raw values: TM={tm}, TS={ts}, TT={tt}")
            
        except Exception as e:
            print(f"  Error interpreting timing: {e}")
        
        print(f"  📁 Saved debug file: debug_detailed_{event_id}_*.json")
        print("-" * 50)
        
        # Only analyze first 3 games to avoid API spam
        if i >= 2:
            break
    
    print(f"\n💡 NEXT STEPS:")
    print(f"1. Examine the saved debug_detailed_*.json files")
    print(f"2. Compare the timing values to what you see watching a live game")
    print(f"3. Look for patterns in how TM/TS change over time")
    print(f"4. Check if there are other timing fields in the response")

def check_alternative_endpoints():
    """Check if there are better endpoints for timing data"""
    print(f"\n🔍 CHECKING ALTERNATIVE TIMING SOURCES")
    print("=" * 50)
    
    live_games = get_live_games()
    if not live_games:
        return
    
    event_id = live_games[0]['id']
    token = os.getenv("BETSAPI_KEY")
    
    endpoints = [
        ("bet365/event (no stats)", f"https://api.b365api.com/v1/bet365/event?FI={event_id}&token={token}"),
        ("bet365/event (with stats)", f"https://api.b365api.com/v1/bet365/event?FI={event_id}&token={token}&stats=1"),
        ("event/view", f"https://api.b365api.com/v1/event/view?event_id={event_id}&token={token}"),
    ]
    
    for name, url in endpoints:
        print(f"\n--- {name} ---")
        try:
            response = requests.get(url, timeout=15)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Look for timing-related fields
                timing_fields = []
                
                def find_timing_fields(obj, path=""):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if any(t in key.lower() for t in ['time', 'clock', 'period', 'quarter', 'tm', 'ts', 'tt']):
                                timing_fields.append(f"{path}.{key}: {value}")
                            if isinstance(value, (dict, list)):
                                find_timing_fields(value, f"{path}.{key}")
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            find_timing_fields(item, f"{path}[{i}]")
                
                find_timing_fields(data)
                
                if timing_fields:
                    print("Timing-related fields found:")
                    for field in timing_fields[:10]:  # Show first 10
                        print(f"  {field}")
                else:
                    print("No obvious timing fields found")
                    
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    analyze_timing_fields()
    check_alternative_endpoints()