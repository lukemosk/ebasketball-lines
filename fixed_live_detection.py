# fixed_live_detection.py - Fix live game detection using correct API endpoints
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import requests
import os
import json
from datetime import datetime, timezone

def get_live_ebasketball_games_correct():
    """Use the correct API endpoint to find live eBasketball games"""
    print("🔧 USING CORRECT API ENDPOINT: /bet365/inplay_filter")
    print("=" * 60)
    
    try:
        token = os.getenv("BETSAPI_KEY")
        
        # Use inplay_filter with sport_id=18 (basketball)
        url = f"https://api.b365api.com/v1/bet365/inplay_filter?sport_id=18&token={token}"
        response = requests.get(url, timeout=15)
        
        print(f"URL: {url}")
        print(f"Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            return []
        
        data = response.json()
        print(f"Success: {data.get('success')}")
        
        results = data.get('results', [])
        print(f"Results: {len(results)} items")
        
        # Save for inspection
        with open("inplay_filter_response.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("Saved response to inplay_filter_response.json")
        
        # Look for eBasketball games
        ebasketball_games = []
        
        for game in results:
            if not isinstance(game, dict):
                continue
                
            # Extract league name
            league = game.get('league', {})
            if isinstance(league, dict):
                league_name = league.get('name', '')
            else:
                league_name = str(league)
            
            league_name = league_name.lower()
            
            # Check if it's eBasketball
            if any(keyword in league_name for keyword in ['ebasketball', 'h2h gg', '4x5']):
                ebasketball_games.append({
                    'id': game.get('id'),  # This should be the FI
                    'league': league_name,
                    'home': game.get('home', {}).get('name', 'Unknown') if isinstance(game.get('home'), dict) else str(game.get('home', 'Unknown')),
                    'away': game.get('away', {}).get('name', 'Unknown') if isinstance(game.get('away'), dict) else str(game.get('away', 'Unknown')),
                    'time': game.get('time', 'Unknown'),
                    'timer': game.get('timer', {}),
                    'full_data': game  # Keep full data for debugging
                })
        
        if ebasketball_games:
            print(f"\n🎯 Found {len(ebasketball_games)} live eBasketball games:")
            for game in ebasketball_games:
                print(f"  FI {game['id']}: {game['home']} vs {game['away']}")
                print(f"     League: {game['league']}")
                print(f"     Time: {game['time']}")
                if game['timer']:
                    print(f"     Timer: {game['timer']}")
        else:
            print("❌ No live eBasketball games found")
            
            # Show what leagues we did find
            all_leagues = []
            for game in results:
                if isinstance(game, dict):
                    league = game.get('league', {})
                    if isinstance(league, dict):
                        league_name = league.get('name', '')
                    else:
                        league_name = str(league)
                    if league_name:
                        all_leagues.append(league_name.lower())
            
            unique_leagues = list(set(all_leagues))
            print(f"\nFound {len(unique_leagues)} unique basketball leagues:")
            for league in sorted(unique_leagues)[:10]:  # Show first 10
                print(f"  - {league}")
        
        return ebasketball_games
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def test_live_game_data(game_id):
    """Test getting live data for a specific game"""
    print(f"\n🧪 TESTING LIVE DATA FOR FI {game_id}")
    print("=" * 60)
    
    try:
        token = os.getenv("BETSAPI_KEY")
        
        # Use /bet365/event endpoint as documented
        url = f"https://api.b365api.com/v1/bet365/event?FI={game_id}&token={token}&stats=1"
        response = requests.get(url, timeout=15)
        
        print(f"URL: {url}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Save for inspection
            with open(f"live_game_{game_id}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"Success: {data.get('success')}")
            results = data.get('results', [])
            print(f"Results: {len(results)} items")
            
            if results:
                if isinstance(results, list) and len(results) > 0:
                    game = results[0]
                elif isinstance(results, dict):
                    game = results
                else:
                    print(f"Unexpected results format: {type(results)}")
                    return None
                
                if isinstance(game, dict):
                    print(f"Game keys: {list(game.keys())}")
                    
                    # Look for timing/score info
                    key_fields = ['time_status', 'timer', 'scores', 'stats', 'periods', 'clock', 'tm', 'tt', 'q']
                    for field in key_fields:
                        if field in game:
                            print(f"{field}: {game[field]}")
                    
                    # Also check nested timer fields
                    timer = game.get('timer', {})
                    if timer and isinstance(timer, dict):
                        print(f"Timer details: {timer}")
                    
                    return game
                else:
                    print(f"Game data is not a dict: {type(game)}")
                    print(f"Game data: {game}")
                
                return None
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def main():
    # Get live games using correct endpoint
    live_games = get_live_ebasketball_games_correct()
    
    # If we found any, test getting detailed data
    if live_games:
        test_game = live_games[0]
        game_id = test_game['id']
        
        detailed_data = test_live_game_data(game_id)
        
        if detailed_data:
            print(f"\n✅ SUCCESS! We can get live data for FI {game_id}")
            print("This means we can monitor live games and detect quarter endings!")
        else:
            print(f"\n❌ Could not get detailed live data")
    else:
        print(f"\n💡 No live games right now, but the method should work when games are live")
        
        # Test with a known game ID if available
        test_id = input("\nEnter a game ID to test (or press Enter to skip): ").strip()
        if test_id and test_id.isdigit():
            test_live_game_data(int(test_id))

if __name__ == "__main__":
    main()