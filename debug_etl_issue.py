# debug_etl_issue.py - Figure out why the fix isn't working
import sqlite3
from datetime import datetime, timezone

DB = "data/ebasketball.db"

def check_recent_updates():
    print("DEBUGGING ETL ISSUE")
    print("=" * 40)
    
    # Check the problematic game
    problematic_id = 181107468
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        game = con.execute("SELECT * FROM event WHERE event_id = ?", (problematic_id,)).fetchone()
        
        if game:
            print(f"Problematic game FI {problematic_id}:")
            print(f"  Teams: {game['home_name']} vs {game['away_name']}")
            print(f"  Start: {game['start_time_utc']}")
            print(f"  Status: {game['status']}")
            print(f"  Finals: {game['final_home']}-{game['final_away']}")
            
            # Calculate time since start
            try:
                start_time = datetime.fromisoformat(game['start_time_utc'])
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                minutes_since_start = (now - start_time).total_seconds() / 60
                
                print(f"  Minutes since start: {minutes_since_start:.1f}")
                
                if minutes_since_start < 30:
                    print(f"  ❌ Game has finals but is only {minutes_since_start:.1f} min old")
                    print(f"  This should NOT happen with the fix")
                
            except Exception as e:
                print(f"  Time calculation error: {e}")
    
    print(f"\nPOSSIBLE CAUSES:")
    print(f"1. ETL code change didn't save properly")
    print(f"2. Running cached version of ETL")
    print(f"3. Another process is setting finals")
    print(f"4. backfill_results.py is setting them")
    
    print(f"\nDEBUGGING STEPS:")
    print(f"1. Check your src/etl.py file - verify the change is there")
    print(f"2. Restart Python completely")
    print(f"3. Check if backfill_results.py is running and setting finals")

def check_etl_file():
    """Check if the ETL file has the fix"""
    print(f"\nCHECKING ETL FILE:")
    
    try:
        with open("src/etl.py", "r") as f:
            content = f.read()
            
        # Look for the conservative fix
        if "minutes_since_start > 30" in content:
            print("✅ ETL file contains the fix (minutes_since_start > 30)")
        else:
            print("❌ ETL file does NOT contain the fix")
            print("Need to update src/etl.py with the conservative logic")
            
        # Look for old problematic code
        if 'if ev.get("ss"):' in content and "minutes_since_start" not in content:
            print("❌ ETL still has old logic that sets finals immediately")
            
    except Exception as e:
        print(f"❌ Could not read ETL file: {e}")

def check_what_processes_run():
    """See what might be setting finals"""
    print(f"\nWHAT COULD BE SETTING FINALS:")
    print(f"1. src/etl.py - main ETL process")
    print(f"2. backfill_results.py - backfill process")
    print(f"3. Any other scripts in run_tracker.py")
    
    try:
        with open("run_tracker.py", "r") as f:
            content = f.read()
            print(f"\nrun_tracker.py contains:")
            lines = content.split('\n')
            for line in lines:
                if 'subprocess.run' in line or 'python' in line:
                    print(f"  {line.strip()}")
    except:
        print("Could not read run_tracker.py")

if __name__ == "__main__":
    check_recent_updates()
    check_etl_file()
    check_what_processes_run()
    
    print(f"\nNEXT STEPS:")
    print(f"1. If ETL file doesn't have fix, add it")
    print(f"2. Stop run_tracker.py completely")
    print(f"3. Run ETL manually once: python -m src.etl")
    print(f"4. Test again: python test_etl_fix.py")