# check_backfill_behavior.py - See what backfill_results.py is doing wrong
import sqlite3
from datetime import datetime, timezone

DB = "data/ebasketball.db"

def analyze_backfill_candidates():
    print("ANALYZING BACKFILL_RESULTS.PY BEHAVIOR")
    print("=" * 50)
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Check what games backfill_results.py would target
        candidates = con.execute("""
            SELECT e.event_id, e.start_time_utc, e.home_name, e.away_name, e.status, 
                   e.final_home, e.final_away,
                   r.event_id IS NOT NULL AS has_result
            FROM event e
            LEFT JOIN result r ON r.event_id = e.event_id
            WHERE e.start_time_utc >= datetime('now', '-6 hours')
              AND e.start_time_utc < datetime('now', '-10 minutes')
            ORDER BY e.start_time_utc DESC
        """).fetchall()
        
        print(f"Games that backfill_results.py might target:")
        print("(Started >10 min ago, within last 6 hours)")
        
        problematic = []
        
        for game in candidates:
            try:
                start_time = datetime.fromisoformat(game['start_time_utc'])
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                minutes_since_start = (now - start_time).total_seconds() / 60
                
                has_finals = (game['final_home'] is not None and game['final_away'] is not None)
                
                print(f"\nFI {game['event_id']}: {game['home_name']} vs {game['away_name']}")
                print(f"  Started {minutes_since_start:.1f} min ago | Status: {game['status']}")
                print(f"  Has finals: {has_finals} | Has result: {game['has_result']}")
                
                # Check if this is problematic
                if has_finals and minutes_since_start < 25:
                    problematic.append(game['event_id'])
                    print(f"  ❌ PROBLEM: Has finals but only {minutes_since_start:.1f} min old")
                elif not has_finals and minutes_since_start > 40:
                    print(f"  ⚠️  Old game without finals (might need backfill)")
                else:
                    print(f"  ✅ Looks correct")
                    
            except Exception as e:
                print(f"  Error: {e}")
        
        print(f"\n📊 SUMMARY:")
        print(f"  Total candidates: {len(candidates)}")
        print(f"  Problematic (premature finals): {len(problematic)}")
        
        if problematic:
            print(f"\n🔧 SOLUTION:")
            print(f"  backfill_results.py needs to be more conservative")
            print(f"  It should only process games >30 minutes old")

def check_backfill_logic():
    print(f"\n" + "="*50)
    print("CHECKING BACKFILL_RESULTS.PY LOGIC")
    
    try:
        with open("backfill_results.py", "r") as f:
            content = f.read()
            
        # Look for the age check
        if "MIN_AGE_MIN" in content:
            print("✅ backfill_results.py has MIN_AGE_MIN parameter")
            
            # Extract the value
            import re
            match = re.search(r'MIN_AGE_MIN\s*=\s*int\(os\.getenv\("RESULT_MIN_AGE_MINUTES",\s*"(\d+)"\)\)', content)
            if match:
                min_age = match.group(1)
                print(f"  Current MIN_AGE_MIN: {min_age} minutes")
                
                if int(min_age) < 25:
                    print(f"  ❌ Too aggressive! Should be at least 25-30 minutes")
                    print(f"  This is why games get finals after 10-15 minutes")
                else:
                    print(f"  ✅ Reasonable age threshold")
            else:
                print("  Could not extract MIN_AGE_MIN value")
        else:
            print("❌ backfill_results.py has no MIN_AGE_MIN check")
            print("  It processes all games regardless of age")
            
    except Exception as e:
        print(f"❌ Could not read backfill_results.py: {e}")

if __name__ == "__main__":
    analyze_backfill_candidates()
    check_backfill_logic()