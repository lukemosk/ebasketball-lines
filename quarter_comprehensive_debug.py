# quarter_comprehensive_debug.py - Test the fixed quarter monitor
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import requests
import os
import json
from datetime import datetime, timezone

def test_all_components():
    """Test all components of the quarter monitoring system"""
    
    print("🧪 COMPREHENSIVE QUARTER MONITOR TEST (FIXED VERSION)")
    print("=" * 70)
    
    # Test 1: API Connectivity
    print("\n🔍 TEST 1: API CONNECTIVITY")
    print("-" * 50)
    
    token = os.getenv("BETSAPI_KEY")
    if not token:
        print("❌ BETSAPI_KEY not found in environment")
        return
    
    print(f"✅ API Token: {token[:8]}...{token[-4:]}")
    
    # Test 2: Live Games API
    print("\n🔍 TEST 2: LIVE GAMES DISCOVERY")
    print("-" * 50)
    
    try:
        url = f"https://api.b365api.com/v1/bet365/inplay_filter?sport_id=18&token={token}"
        response = requests.get(url, timeout=15)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.text}")
            return
        
        data = response.json()
        results = data.get('results', [])
        
        print(f"Total live basketball games: {len(results)}")
        
        # Find eBasketball games
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
                
                ebasketball_games.append(game)
        
        print(f"eBasketball H2H GG games: {len(ebasketball_games)}")
        
        if not ebasketball_games:
            print("❌ No live eBasketball games found - cannot test further")
            return
        
        # Show first few games
        for i, game in enumerate(ebasketball_games[:3], 1):
            home = game.get('home', {})
            away = game.get('away', {})
            
            if isinstance(home, dict):
                home_name = home.get('name', 'Unknown')
            else:
                home_name = str(home)
            
            if isinstance(away, dict):
                away_name = away.get('name', 'Unknown')  
            else:
                away_name = str(away)
            
            print(f"  Game {i}: FI {game.get('id')}")
            print(f"    Teams: {home_name} vs {away_name}")
            print(f"    Score: {game.get('ss', 'N/A')}")
            print(f"    Time Status: {game.get('time_status', 'N/A')}")
        
        # Test 3: Detailed Game Data
        if ebasketball_games:
            test_game = ebasketball_games[0]
            test_game_id = test_game.get('id')
            
            print(f"\n🔍 TEST 3: DETAILED GAME DATA (FI {test_game_id})")
            print("-" * 50)
            
            test_detailed_game_data(test_game_id)
            
            # Test 4: Odds Capture
            print(f"\n🔍 TEST 4: ODDS CAPTURE (FI {test_game_id})")
            print("-" * 50)
            
            test_odds_capture(test_game_id)
            
            # Test 5: Quarter Detection Logic
            print(f"\n🔍 TEST 5: QUARTER DETECTION LOGIC")
            print("-" * 50)
            
            test_quarter_detection_logic()
        
        print(f"\n✅ COMPREHENSIVE TEST COMPLETE")
        
        if ebasketball_games:
            print(f"\n💡 RECOMMENDATIONS:")
            print(f"1. Run the fixed quarter monitor: python live_quarter_monitor.py")
            print(f"2. Let it run during active eBasketball hours (typically 9 AM - 11 PM EST)")
            print(f"3. Monitor output for quarter ending detections")
            print(f"4. Check quarter_line table for captured data")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_detailed_game_data(game_id):
    """Test getting detailed live data for a specific game"""
    try:
        token = os.getenv("BETSAPI_KEY")
        url = f"https://api.b365api.com/v1/bet365/event?FI={game_id}&token={token}&stats=1"
        
        response = requests.get(url, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.text}")
            return
        
        data = response.json()
        
        # Save for inspection
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"debug_game_{game_id}_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"💾 Saved full response to {filename}")
        
        # Parse the data
        results = data.get('results', [])
        
        if not results:
            print("❌ No results in response")
            return
        
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
            print("✅ Found EV object!")
            
            # Extract key timing fields
            ss = ev_obj.get('SS', '')
            tm = ev_obj.get('TM', 0)
            ts = ev_obj.get('TS', 0)
            tt = ev_obj.get('TT', 0)
            
            print(f"  EV Type: {ev_obj.get('type')}")
            print(f"  SS (Score): {ss}")
            print(f"  TM (Minutes): {tm}")
            print(f"  TS (Seconds): {ts}")
            print(f"  TT (Timer): {tt}")
            
            # Calculate timing
            try:
                minutes_elapsed = int(tm) if tm else 0
                seconds_elapsed = int(ts) if ts else 0
                timer_running = str(tt) == '1'
                
                total_elapsed_in_quarter = minutes_elapsed * 60 + seconds_elapsed
                remaining_in_quarter = max(0, 300 - total_elapsed_in_quarter)
                
                # Estimate quarter based on score
                quarter = 1
                if '-' in ss:
                    try:
                        home_score, away_score = map(int, ss.split('-'))
                        total_score = home_score + away_score
                        
                        if total_score < 30:
                            quarter = 1
                        elif total_score < 60:
                            quarter = 2
                        elif total_score < 90:
                            quarter = 3
                        else:
                            quarter = 4
                    except:
                        pass
                
                print(f"\n📊 Parsed Data:")
                print(f"    score: {ss}")
                print(f"    quarter: {quarter}")
                print(f"    total_remaining_seconds: {remaining_in_quarter}")
                print(f"    timer_running: {timer_running}")
                print(f"    is_live: {timer_running or remaining_in_quarter < 300}")
                print(f"    raw_tm: {tm}")
                print(f"    raw_ts: {ts}")
                print(f"    raw_tt: {tt}")
                
                return {
                    'quarter': quarter,
                    'remaining_seconds': remaining_in_quarter,
                    'score': ss,
                    'timer_running': timer_running
                }
                
            except Exception as e:
                print(f"❌ Error parsing timing: {e}")
        else:
            print("❌ No EV object found")
            print("Available object types:")
            
            def find_all_types(obj, depth=0):
                if depth > 2:
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
        print(f"❌ Error testing detailed game data: {e}")

def test_odds_capture(game_id):
    """Test multiple methods of getting odds for a live game"""
    
    # Method 1: Original betsapi function
    print("🎯 Method 1: Original betsapi.get_odds_openers")
    try:
        from src import betsapi
        odds = betsapi.get_odds_openers(game_id) or {}
        
        spread = odds.get('spread')
        total = odds.get('total')
        
        print(f"  Spread: {spread}")
        print(f"  Total: {total}")
        print(f"  Opened at: {odds.get('opened_at_utc', '')}")
        
        if spread is None and total is None:
            print("  ⚠️  No lines from original method")
        else:
            print("  ✅ Got lines from original method")
            
    except Exception as e:
        print(f"  ❌ Error with original method: {e}")
    
    # Method 2: Direct prematch API
    print(f"\n🎯 Method 2: Direct prematch API")
    try:
        token = os.getenv("BETSAPI_KEY")
        url = f"https://api.b365api.com/v3/bet365/prematch?FI={game_id}&token={token}"
        
        response = requests.get(url, timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            if results:
                main = results[0].get('main', {})
                sp = main.get('sp', {})
                game_lines = sp.get('game_lines', {})
                odds_list = game_lines.get('odds', [])
                
                print(f"  Found {len(odds_list)} odds entries")
                
                spread_vals = []
                total_vals = []
                
                for i, odds in enumerate(odds_list[:5]):  # Check first 5
                    if not isinstance(odds, dict):
                        continue
                    
                    name = str(odds.get('name', '')).lower()
                    handicap = odds.get('handicap')
                    total_val = odds.get('total')
                    
                    print(f"    Odds {i+1}: name='{name}', handicap={handicap}, total={total_val}")
                    
                    if ('spread' in name or 'handicap' in name) and handicap is not None:
                        try:
                            spread_vals.append(abs(float(str(handicap).replace('+', ''))))
                        except:
                            pass
                    
                    if ('total' in name or 'over' in name or 'under' in name) and total_val is not None:
                        try:
                            total_str = str(total_val).replace('O', '').replace('U', '').strip()
                            total_vals.append(float(total_str))
                        except:
                            pass
                
                if spread_vals or total_vals:
                    final_spread = min(spread_vals) if spread_vals else None
                    final_total = min(total_vals) if total_vals else None
                    print(f"  ✅ Extracted: spread={final_spread}, total={final_total}")
                else:
                    print(f"  ⚠️  No lines extracted from prematch")
            else:
                print(f"  ⚠️  No results in prematch response")
        else:
            print(f"  ❌ Prematch API failed: {response.text[:100]}")
            
    except Exception as e:
        print(f"  ❌ Error with prematch method: {e}")

def test_quarter_detection_logic():
    """Test the quarter ending detection logic"""
    
    test_cases = [
        (1, 5, False, "Q1 with 5 seconds - NOT ending"),
        (1, 3, True, "Q1 with 3 seconds - ENDING"),
        (1, 1, True, "Q1 with 1 second - ENDING"),
        (2, 2, True, "Q2 with 2 seconds - ENDING"),
        (3, 0, True, "Q3 with 0 seconds - ENDING"),
        (4, 2, False, "Q4 with 2 seconds - NOT monitored (Q4 not tracked)"),
        (1, 30, False, "Q1 with 30 seconds - NOT ending"),
        (2, 120, False, "Q2 with 2 minutes - NOT ending"),
    ]
    
    for quarter, remaining_seconds, expected, description in test_cases:
        # Test logic
        is_ending = (quarter in [1, 2, 3] and remaining_seconds <= 3)
        
        status = "✅ PASS" if is_ending == expected else "❌ FAIL"
        result = "ENDING" if is_ending else "NOT ENDING"
        
        print(f"  {status} {description}")
        print(f"       Quarter: {quarter}, Remaining: {remaining_seconds}s → {result}")
    
    print(f"\n💡 Detection Rule: Quarter must be 1, 2, or 3 AND remaining seconds ≤ 3")

def test_database_schema():
    """Test that the quarter_line table exists and is properly structured"""
    print(f"\n🔍 TEST 6: DATABASE SCHEMA")
    print("-" * 50)
    
    try:
        import sqlite3
        
        with sqlite3.connect("data/ebasketball.db") as con:
            # Check if quarter_line table exists
            cursor = con.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='quarter_line'
            """)
            
            if cursor.fetchone():
                print("✅ quarter_line table exists")
                
                # Check structure
                cursor = con.execute("PRAGMA table_info(quarter_line)")
                columns = cursor.fetchall()
                
                print("  Table structure:")
                for col in columns:
                    print(f"    {col[1]} ({col[2]})")
                
                # Check for existing data
                cursor = con.execute("SELECT COUNT(*) FROM quarter_line")
                count = cursor.fetchone()[0]
                print(f"  Existing records: {count}")
                
                if count > 0:
                    cursor = con.execute("""
                        SELECT event_id, quarter, market, line 
                        FROM quarter_line 
                        ORDER BY captured_at_utc DESC 
                        LIMIT 3
                    """)
                    recent = cursor.fetchall()
                    print("  Recent captures:")
                    for row in recent:
                        print(f"    FI {row[0]} Q{row[1]} {row[2]}: {row[3]}")
                
            else:
                print("❌ quarter_line table missing")
                print("  Run: python setup_quarter_monitoring.py")
                
    except Exception as e:
        print(f"❌ Database error: {e}")

def main():
    test_all_components()
    test_database_schema()

if __name__ == "__main__":
    main()