# debug_game_status.py - Debug specific game status issues
import sqlite3
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from src import betsapi

DB = "data/ebasketball.db"

def debug_game(event_id):
    """Deep dive into a specific game's status"""
    
    print(f"🔍 DEEP DEBUG FOR FI {event_id}")
    print("=" * 60)
    
    # 1. Database info
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        db_info = con.execute("SELECT * FROM event WHERE event_id = ?", (event_id,)).fetchone()
    
    if not db_info:
        print("❌ Game not found in database")
        return
    
    print("📊 DATABASE INFO:")
    print(f"  Teams: {db_info['home_name']} vs {db_info['away_name']}")
    print(f"  Start time (UTC): {db_info['start_time_utc']}")
    print(f"  Status: {db_info['status']}")
    print(f"  Finals: {db_info['final_home']}-{db_info['final_away'] if db_info['final_away'] else 'None'}")
    
    # Calculate time since start
    try:
        start_utc = datetime.fromisoformat(db_info['start_time_utc'])
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        minutes_since_start = (now - start_utc).total_seconds() / 60
        local_start = start_utc - timedelta(hours=5)
        
        print(f"  Start time (Local): {local_start.strftime('%H:%M:%S')}")
        print(f"  Minutes since start: {minutes_since_start:.1f}")
    except Exception as e:
        print(f"  Time calculation error: {e}")
        minutes_since_start = 0
    
    # 2. API responses (detailed)
    print(f"\n🌐 API RESPONSES:")
    
    # Fast endpoint
    print("  📡 Fast endpoint (/v1/bet365/event):")
    try:
        fast = betsapi.get_event_score_fast(event_id) or {}
        print(f"    Raw response keys: {list(fast.keys())}")
        print(f"    time_status: {fast.get('time_status')} (type: {type(fast.get('time_status'))})")
        print(f"    final_home: {fast.get('final_home')}")
        print(f"    final_away: {fast.get('final_away')}")
        print(f"    SS: {fast.get('SS')}")
        print(f"    ss: {fast.get('ss')}")
        
        # Look for other status fields
        for key, value in fast.items():
            if 'status' in key.lower() or 'time' in key.lower():
                print(f"    {key}: {value}")
                
    except Exception as e:
        print(f"    ❌ Error: {e}")
        fast = {}
    
    # Result endpoint
    print(f"\n  📡 Result endpoint (/v1/bet365/result):")
    try:
        result = betsapi.get_event_result(event_id) or {}
        print(f"    Raw response keys: {list(result.keys())}")
        print(f"    final_home: {result.get('final_home')}")
        print(f"    final_away: {result.get('final_away')}")
        print(f"    SS: {result.get('SS')}")
        print(f"    ss: {result.get('ss')}")
        
        # Look for status fields
        for key, value in result.items():
            if 'status' in key.lower():
                print(f"    {key}: {value}")
                
    except Exception as e:
        print(f"    ❌ Error: {e}")
        result = {}
    
    # 3. Dashboard logic analysis
    print(f"\n🧠 DASHBOARD LOGIC ANALYSIS:")
    
    ts = str(fast.get("time_status") or "")
    ss = fast.get("SS") or fast.get("ss")
    has_result_finals = (result.get("final_home") is not None and result.get("final_away") is not None)
    
    print(f"  time_status: '{ts}' (empty: {ts == ''})")
    print(f"  Live score (SS/ss): {ss}")
    print(f"  Result has finals: {has_result_finals}")
    print(f"  Minutes since start: {minutes_since_start:.1f}")
    
    # Simulate dashboard logic
    if ts == "3" or has_result_finals:
        dashboard_status = "finished"
    elif ts == "1" or (ss and ts != "0"):
        dashboard_status = "live"  
    elif ts == "0":
        dashboard_status = "not_started"
    else:
        # Time-based fallback logic
        if minutes_since_start > 30:
            dashboard_status = "unknown_old"
        elif minutes_since_start > 0:
            dashboard_status = "unknown_started"
        else:
            dashboard_status = "not_started"
    
    print(f"  Dashboard would show: {dashboard_status}")
    print(f"  Database shows: {db_info['status']}")
    print(f"  Match: {'✅' if dashboard_status == db_info['status'] else '❌'}")
    
    # 4. Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    
    if ts == "":
        print("  🔶 API not returning time_status - this is the main issue")
        print("  🔶 BetsAPI might not have live data for this game")
        
    if minutes_since_start > 25 and not has_result_finals and ts != "3":
        print("  🔶 Game should be finished but API shows no finals")
        print("  🔶 Consider this game 'stale' or check different API endpoint")
        
    if ss and not has_result_finals:
        print("  🔶 Live score available but no official finals")
        print("  🔶 Game might still be in progress")

def debug_multiple_games():
    """Debug several problematic games"""
    
    # Get some games that would show as "Old Game" or "Started?"
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        problematic = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status
            FROM event 
            WHERE start_time_utc >= datetime('now', '-3 hours')
              AND start_time_utc < datetime('now', '-10 minutes')
            ORDER BY start_time_utc DESC
            LIMIT 5
        """).fetchall()
    
    print("🔍 DEBUGGING MULTIPLE PROBLEMATIC GAMES")
    print("=" * 60)
    
    for game in problematic:
        print(f"\nQuick check FI {game['event_id']} ({game['home_name']} vs {game['away_name']}):")
        
        try:
            fast = betsapi.get_event_score_fast(int(game['event_id'])) or {}
            ts = str(fast.get("time_status") or "")
            ss = fast.get("SS") or fast.get("ss")
            
            print(f"  DB status: {game['status']} | API time_status: '{ts}' | Score: {ss or 'None'}")
            
            if ts == "":
                print(f"    🔶 No time_status from API")
            elif ts not in ["0", "1", "3"]:
                print(f"    🔶 Unusual time_status: {ts}")
                
        except Exception as e:
            print(f"    ❌ API error: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Debug specific game
        event_id = int(sys.argv[1])
        debug_game(event_id)
    else:
        # Debug multiple games
        debug_multiple_games()
        
        print(f"\n" + "="*60)
        print("To debug a specific game:")
        print("python debug_game_status.py 181234567")