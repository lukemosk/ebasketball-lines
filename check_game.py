# check_game.py - Quick check of a specific game
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import sqlite3
from src import betsapi

DB = "data/ebasketball.db"

def check_game(event_id):
    # Get from DB
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        db_info = con.execute("SELECT * FROM event WHERE event_id = ?", (event_id,)).fetchone()
    
    if not db_info:
        print(f"❌ Game {event_id} not found in database")
        return
    
    print(f"🔍 Checking FI {event_id}")
    print(f"📊 DB Status:")
    print(f"  Teams: {db_info['home_name']} vs {db_info['away_name']}")
    print(f"  Status: {db_info['status']}")
    print(f"  Finals: {db_info['final_home']}-{db_info['final_away'] if db_info['final_away'] else 'None'}")
    print(f"  Start: {db_info['start_time_utc']}")
    
    print(f"\n🌐 API Status:")
    try:
        # Check live status
        fast = betsapi.get_event_score_fast(event_id) or {}
        ts = str(fast.get("time_status") or "unknown")
        ss = fast.get("SS") or fast.get("ss") or "no score"
        
        # Check result
        result = betsapi.get_event_result(event_id) or {}
        result_finals = f"{result.get('final_home')}-{result.get('final_away')}" if result.get('final_home') else "None"
        
        print(f"  time_status: {ts} ({'Not started' if ts=='0' else 'Live' if ts=='1' else 'Finished' if ts=='3' else 'Unknown'})")
        print(f"  Live score: {ss}")
        print(f"  Result endpoint: {result_finals}")
        
        print(f"\n📋 Analysis:")
        if ts == "3" and db_info['final_home'] is None:
            print("⚠️  Game finished but no finals in DB - this is EXPECTED behavior now!")
            print("    (Finals will be added by backfill_results.py)")
        elif ts in ("0", "1") and db_info['final_home'] is not None:
            print("❌ PROBLEM: Game not finished but has finals in DB")
        elif ts == "3" and db_info['final_home'] is not None:
            print("✅ Game finished and has finals - perfect")
        elif ts in ("0", "1") and db_info['final_home'] is None:
            print("✅ Game not finished and no finals - perfect (this is the fix working!)")
        else:
            print("🤔 Unclear status")
            
    except Exception as e:
        print(f"❌ API Error: {e}")

# Check the unresolved game from your log
print("Checking the unresolved game from your ETL log:")
check_game(181084154)

print("\n" + "="*50)
print("Checking one of the new games without openers:")
check_game(181107462)