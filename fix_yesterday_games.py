# fix_yesterday_games.py - Fix games from yesterday that should be finished
import sqlite3
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from src import betsapi

DB = "data/ebasketball.db"

def fix_yesterday_games():
    print("FIXING YESTERDAY'S GAMES THAT SHOULD BE FINISHED")
    print("=" * 50)
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Find games from yesterday that are still marked as not_started
        yesterday_games = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status
            FROM event 
            WHERE DATE(start_time_utc) = DATE('now', '-1 day')
              AND status = 'not_started'
            ORDER BY start_time_utc ASC
        """).fetchall()
        
        print(f"Found {len(yesterday_games)} games from yesterday still marked as 'not_started'")
        
        if not yesterday_games:
            print("No yesterday games need fixing")
            return
        
        print("\nChecking first 10 games with API...")
        
        fixed_count = 0
        api_errors = 0
        
        for i, game in enumerate(yesterday_games):
            if i >= 10:  # Just check first 10 for speed
                break
                
            eid = int(game['event_id'])
            print(f"\nChecking FI {eid}: {game['home_name']} vs {game['away_name']}")
            
            try:
                # Check both API endpoints for finals
                fast = betsapi.get_event_score_fast(eid) or {}
                result = betsapi.get_event_result(eid) or {}
                
                # Try to get finals from either endpoint
                fh = result.get("final_home") or fast.get("final_home")
                fa = result.get("final_away") or fast.get("final_away")
                
                # If no explicit finals, try parsing SS
                if fh is None or fa is None:
                    ss = fast.get("SS") or fast.get("ss") or result.get("SS") or result.get("ss")
                    if isinstance(ss, str) and "-" in ss:
                        try:
                            h, a = ss.split("-", 1)
                            fh, fa = int(h), int(a)
                        except:
                            pass
                
                if fh is not None and fa is not None:
                    # Update the game
                    con.execute("""
                        UPDATE event 
                        SET status = 'finished', final_home = ?, final_away = ?
                        WHERE event_id = ?
                    """, (int(fh), int(fa), eid))
                    
                    print(f"  ✅ Updated to finished: {fh}-{fa}")
                    fixed_count += 1
                else:
                    print(f"  ❓ No finals found in API")
                    
            except Exception as e:
                print(f"  ❌ API error: {e}")
                api_errors += 1
        
        con.commit()
        
        print(f"\n📊 SAMPLE RESULTS (first 10 games):")
        print(f"  Fixed: {fixed_count}")
        print(f"  API errors: {api_errors}")
        print(f"  No data: {10 - fixed_count - api_errors}")
        
        if fixed_count > 0:
            # Apply same fix to all yesterday games
            apply_all = input(f"\nApply similar fix to all {len(yesterday_games)} yesterday games? [y/N]: ")
            if apply_all.lower() == 'y':
                
                total_fixed = 0
                total_errors = 0
                
                print(f"Processing all {len(yesterday_games)} games...")
                
                for i, game in enumerate(yesterday_games):
                    if i % 20 == 0:
                        print(f"  Progress: {i}/{len(yesterday_games)}")
                    
                    eid = int(game['event_id'])
                    
                    try:
                        fast = betsapi.get_event_score_fast(eid) or {}
                        result = betsapi.get_event_result(eid) or {}
                        
                        fh = result.get("final_home") or fast.get("final_home")
                        fa = result.get("final_away") or fast.get("final_away")
                        
                        if fh is None or fa is None:
                            ss = fast.get("SS") or fast.get("ss") or result.get("SS") or result.get("ss")
                            if isinstance(ss, str) and "-" in ss:
                                try:
                                    h, a = ss.split("-", 1)
                                    fh, fa = int(h), int(a)
                                except:
                                    pass
                        
                        if fh is not None and fa is not None:
                            con.execute("""
                                UPDATE event 
                                SET status = 'finished', final_home = ?, final_away = ?
                                WHERE event_id = ?
                            """, (int(fh), int(fa), eid))
                            total_fixed += 1
                        
                    except Exception:
                        total_errors += 1
                
                con.commit()
                
                print(f"\n🎉 BULK UPDATE COMPLETE:")
                print(f"  Total fixed: {total_fixed}")
                print(f"  API errors: {total_errors}")
                print(f"  Remaining unfixed: {len(yesterday_games) - total_fixed}")
                
                # Run result calculations
                if total_fixed > 0:
                    recalc = input(f"Run result calculations for fixed games? [y/N]: ")
                    if recalc.lower() == 'y':
                        import subprocess
                        subprocess.run(["python", "backfill_results.py"])
                        print("Result calculations complete")

if __name__ == "__main__":
    fix_yesterday_games()