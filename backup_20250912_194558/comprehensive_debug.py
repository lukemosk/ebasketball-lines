# comprehensive_debug.py - Debug all aspects of live game detection
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import requests
import os
import json
from datetime import datetime, timezone

def test_league_filtering():
    """Test what leagues are available and our filtering"""
    print("🔍 TESTING LEAGUE FILTERING")
    print("=" * 60)
    
    try:
        token = os.getenv("BETSAPI_KEY")
        url = f"https://api.b365api.com/v1/bet365/inplay_filter?sport_id=18&token={token}"
        
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            return
        
        data = response.json()
        results = data.get('results', [])
        
        print(f"Total basketball games live: {len(results)}")
        
        # Analyze all league names
        leagues = {}
        for game in results:
            if not isinstance(game, dict):
                continue
            
            league = game.get('league', {})
            if isinstance(league, dict):
                league_name = league.get('name', '')
            else:
                league_name = str(league)
            
            league_name = league_name.lower()
            
            if league_name not in leagues:
                leagues[league_name] = []
            
            leagues[league_name].append({
                'id': game.get('id'),
                'home': game.get('home', {}).get('name') if isinstance(game.get('home'), dict) else str(game.get('home', '')),
                'away': game.get('away', {}).get('name') if isinstance(game.get('away'), dict) else str(game.get('away', ''))
            })
        
        print(f"\nAll available leagues:")
        for league_name, games in leagues.items():
            print(f"  '{league_name}': {len(games)} games")
            if 'ebasketball' in league_name or 'basket' in league_name:
                print(f"    📍 EBASKETBALL LEAGUE - Games:")
                for game in games[:3]:  # Show first 3 games
                    print(f"      FI {game['id']}: {game['home']} vs {game['away']}")
        
        # Test our current filter
        print(f"\nCurrent filter results:")
        current_filter_games = []
        for game in results:
            if not isinstance(game, dict):
                continue
            
            league = game.get('league', {})
            if isinstance(league, dict):
                league_name = league.get('name', '')
            else:
                league_name = str(league)
            
            league_name = league_name.lower()
            
            # Current filter logic
            if ('ebasketball h2h gg league' in league_name and 
                '4x5mins' in league_name and 
                'battle' not in league_name):
                current_filter_games.append(game)
        
        print(f"Games passing current filter: {len(current_filter_games)}")
        
        # Suggest better filter
        ebasketball_leagues = [name for name in leagues.keys() if 'ebasketball' in name]
        print(f"\nAll eBasketball league names found:")
        for league in ebasketball_leagues:
            print(f"  '{league}'")
        
        return results
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def test_live_parsing(games):
    """Test live parsing on multiple games"""
    print(f"\n🔍 TESTING LIVE PARSING ON MULTIPLE GAMES")
    print("=" * 60)
    
    if not games:
        print("No games to test")
        return
    
    token = os.getenv("BETSAPI_KEY")
    
    # Test first few games regardless of league
    test_games = games[:5]  # Test first 5 games
    
    for i, game in enumerate(test_games):
        if not isinstance(game, dict):
            continue
        
        event_id = game.get('id')
        home = game.get('home', {}).get('name') if isinstance(game.get('home'), dict) else str(game.get('home', ''))
        away = game.get('away', {}).get('name') if isinstance(game.get('away'), dict) else str(game.get('away', ''))
        
        print(f"\n--- Game {i+1}: FI {event_id} ---")
        print(f"Teams: {home} vs {away}")
        
        try:
            url = f"https://api.b365api.com/v1/bet365/event?FI={event_id}&token={token}&stats=1"
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code}")
                continue
            
            data = response.json()
            results = data.get('results', [])
            
            # Find EV object
            def find_ev_object(obj):
                if isinstance(obj, dict):
                    if obj.get('type') == 'EV':
                        return obj
                    for value in obj.values():
                        result = find_ev_object(value)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_ev_object(item)
                        if result:
                            return result
                return None
            
            ev_obj = find_ev_object(results)
            
            if ev_obj:
                print(f"✅ Found EV object")
                
                # Extract key fields
                ss = ev_obj.get('SS', '')
                tm = ev_obj.get('TM', 0)
                ts = ev_obj.get('TS', 0)
                tt = ev_obj.get('TT', 0)
                
                print(f"  SS (Score): '{ss}'")
                print(f"  TM (Minutes): {tm}")
                print(f"  TS (Seconds): {ts}")
                print(f"  TT (Timer): {tt}")
                
                # Calculate elapsed time
                try:
                    minutes_elapsed = int(tm) if tm else 0
                    seconds_elapsed = int(ts) if ts else 0
                    total_elapsed = minutes_elapsed * 60 + seconds_elapsed
                    is_ticking = str(tt) == '1'
                    
                    print(f"  Total elapsed: {minutes_elapsed}:{seconds_elapsed:02d} ({total_elapsed}s)")
                    print(f"  Timer ticking: {is_ticking}")
                    
                    # Calculate quarter
                    if total_elapsed < 300:
                        quarter = 1
                        remaining = 300 - total_elapsed
                    elif total_elapsed < 600:
                        quarter = 2
                        remaining = 600 - total_elapsed
                    elif total_elapsed < 900:
                        quarter = 3
                        remaining = 900 - total_elapsed
                    else:
                        quarter = 4
                        remaining = max(0, 1200 - total_elapsed)
                    
                    rem_min = remaining // 60
                    rem_sec = remaining % 60
                    
                    print(f"  Calculated: Q{quarter} {rem_min}:{rem_sec:02d} remaining")
                    
                except Exception as e:
                    print(f"  ❌ Calculation error: {e}")
                
            else:
                print(f"❌ No EV object found")
                print(f"  Available object types:")
                
                def find_all_types(obj, depth=0):
                    if depth > 3:  # Prevent infinite recursion
                        return
                    if isinstance(obj, dict):
                        obj_type = obj.get('type')
                        if obj_type:
                            print(f"    {'  ' * depth}type: {obj_type}")
                        for value in obj.values():
                            find_all_types(value, depth + 1)
                    elif isinstance(obj, list):
                        for item in obj:
                            find_all_types(item, depth + 1)
                
                find_all_types(results)
            
        except Exception as e:
            print(f"❌ Error testing game: {e}")

def compare_api_endpoints():
    """Compare different API endpoints for the same game"""
    print(f"\n🔍 COMPARING API ENDPOINTS")
    print("=" * 60)
    
    # Get a live game first
    token = os.getenv("BETSAPI_KEY")
    
    try:
        # Get live games from inplay_filter
        url = f"https://api.b365api.com/v1/bet365/inplay_filter?sport_id=18&token={token}"
        response = requests.get(url, timeout=15)
        data = response.json()
        results = data.get('results', [])
        
        if not results:
            print("No live games to compare")
            return
        
        # Pick the first game
        game = results[0]
        event_id = game.get('id')
        
        print(f"Testing FI {event_id}")
        
        # Test different endpoints
        endpoints = [
            ("inplay_filter", f"https://api.b365api.com/v1/bet365/inplay_filter?sport_id=18&token={token}"),
            ("event", f"https://api.b365api.com/v1/bet365/event?FI={event_id}&token={token}"),
            ("event_with_stats", f"https://api.b365api.com/v1/bet365/event?FI={event_id}&token={token}&stats=1")
        ]
        
        for name, url in endpoints:
            print(f"\n--- {name} ---")
            try:
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Look for score/time info
                    def find_score_time(obj, path=""):
                        findings = []
                        if isinstance(obj, dict):
                            for key in ['SS', 'ss', 'TM', 'tm', 'TS', 'ts', 'TT', 'tt', 'time_status', 'timer']:
                                if key in obj:
                                    findings.append(f"{path}.{key}: {obj[key]}")
                            for key, value in obj.items():
                                findings.extend(find_score_time(value, f"{path}.{key}"))
                        elif isinstance(obj, list):
                            for i, item in enumerate(obj):
                                findings.extend(find_score_time(item, f"{path}[{i}]"))
                        return findings
                    
                    findings = find_score_time(data, name)
                    if findings:
                        for finding in findings[:10]:  # Show first 10
                            print(f"  {finding}")
                    else:
                        print(f"  No score/time fields found")
                        
                else:
                    print(f"  HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"  Error: {e}")
    
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("🏀 COMPREHENSIVE LIVE GAME DEBUG")
    print("=" * 60)
    
    # Test 1: League filtering
    games = test_league_filtering()
    
    # Test 2: Live parsing
    test_live_parsing(games)
    
    # Test 3: Compare endpoints
    compare_api_endpoints()
    
    print(f"\n📋 SUMMARY & RECOMMENDATIONS")
    print("=" * 60)
    print("1. Check the league names above - you might need to adjust the filter")
    print("2. Look at the live parsing results - are the SS/TM/TS/TT values correct?")
    print("3. Compare the different endpoints to see which gives the freshest data")

if __name__ == "__main__":
    main()
    