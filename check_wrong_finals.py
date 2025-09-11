# check_wrong_finals.py - Find games with incorrect finals
import sqlite3
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from src import betsapi

DB = "data/ebasketball.db"

def check_recent_finals():
    print("🔍 CHECKING RECENT FINALS ACCURACY")
    print("=" * 50)
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Get recent finished games
        recent_finished = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
            FROM event 
            WHERE status = 'finished'
              AND final_home IS NOT NULL
              AND start_time_utc >= datetime('now', '-3 hours')
            ORDER BY start_time_utc DESC
            LIMIT 10
        """).fetchall()
    
    print(f"Checking {len(recent_finished)} recently finished games...")
    
    wrong_finals = []
    api_errors = []
    
    for game in recent_finished:
        eid = int(game['event_id'])
        db_score = f"{game['final_home']}-{game['final_away']}"
        
        print(f"\n🔍 FI {eid}: {game['home_name']} vs {game['away_name']}")
        print(f"  DB finals: {db_score}")
        
        try:
            # Check what API says the actual finals are
            result = betsapi.get_event_result(eid) or {}
            api_fh = result.get("final_home")
            api_fa = result.get("final_away")
            
            if api_fh is not None and api_fa is not None:
                api_score = f"{api_fh}-{api_fa}"
                print(f"  API result: {api_score}")
                
                if (int(api_fh) != game['final_home']) or (int(api_fa) != game['final_away']):
                    print(f"  ❌ MISMATCH! DB: {db_score} vs API: {api_score}")
                    wrong_finals.append({
                        'event_id': eid,
                        'teams': f"{game['home_name']} vs {game['away_name']}",
                        'db_score': db_score,
                        'api_score': api_score,
                        'api_fh': int(api_fh),
                        'api_fa': int(api_fa)
                    })
                else:
                    print(f"  ✅ Correct")
            else:
                print(f"  ⚠️  API has no finals")
                
                # Also check fast endpoint
                fast = betsapi.get_event_score_fast(eid) or {}
                fast_fh = fast.get("final_home")
                fast_fa = fast.get("final_away")
                ts = fast.get("time_status")
                
                if fast_fh is not None and fast_fa is not None:
                    fast_score = f"{fast_fh}-{fast_fa}"
                    print(f"  Fast endpoint: {fast_score} (ts={ts})")
                    
                    if (int(fast_fh) != game['final_home']) or (int(fast_fa) != game['final_away']):
                        print(f"  ❌ MISMATCH vs fast! DB: {db_score} vs Fast: {fast_score}")
                        wrong_finals.append({
                            'event_id': eid,
                            'teams': f"{game['home_name']} vs {game['away_name']}",
                            'db_score': db_score,
                            'api_score': fast_score,
                            'api_fh': int(fast_fh),
                            'api_fa': int(fast_fa)
                        })
                else:
                    print(f"  ❓ No finals from any API endpoint")
                
        except Exception as e:
            print(f"  ❌ API Error: {e}")
            api_errors.append(eid)
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print(f"  Games checked: {len(recent_finished)}")
    print(f"  Wrong finals: {len(wrong_finals)}")
    print(f"  API errors: {len(api_errors)}")
    
    if wrong_finals:
        print(f"\n❌ GAMES WITH WRONG FINALS:")
        for game in wrong_finals:
            print(f"  FI {game['event_id']}: {game['teams']}")
            print(f"    DB: {game['db_score']} → Should be: {game['api_score']}")
        
        # Offer to fix them
        fix_them = input(f"\n🔧 Fix these {len(wrong_finals)} wrong finals? [y/N]: ")
        if fix_them.lower() == 'y':
            with sqlite3.connect(DB) as con:
                for game in wrong_finals:
                    con.execute("""
                        UPDATE event 
                        SET final_home = ?, final_away = ?
                        WHERE event_id = ?
                    """, (game['api_fh'], game['api_fa'], game['event_id']))
                con.commit()
            
            print(f"✅ Fixed {len(wrong_finals)} games with correct finals!")
            
            # Also update result calculations
            recalc = input("Recalculate result rows for these games? [y/N]: ")
            if recalc.lower() == 'y':
                with sqlite3.connect(DB) as con:
                    for game in wrong_finals:
                        con.execute("DELETE FROM result WHERE event_id = ?", (game['event_id'],))
                con.commit()
                print("✅ Cleared result rows - they'll be recalculated by backfill_results.py")
    
    return len(wrong_finals) == 0

if __name__ == "__main__":
    all_correct = check_recent_finals()
    if all_correct:
        print("\n🎉 All recent finals are correct!")
    else:
        print("\n⚠️  Some finals need fixing - run backfill_results.py after fixing")