# cleanup_old_bad_data.py
import sqlite3
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from src import betsapi

DB = "data/ebasketball.db"

def q(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()

def exec_sql(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.execute(sql, args)
        con.commit()

def main():
    print("🧹 CLEANING UP OLD BAD DATA")
    print("=" * 50)
    
    # Find all games with result rows but incorrect status/finals
    bad_games = q("""
        SELECT e.event_id, e.home_name, e.away_name, e.status, e.final_home, e.final_away
        FROM event e
        JOIN result r ON r.event_id = e.event_id
        WHERE e.status != 'finished' OR e.final_home IS NULL OR e.final_away IS NULL
        ORDER BY e.event_id
    """)
    
    print(f"Found {len(bad_games)} games with inconsistent data")
    
    if not bad_games:
        print("✅ No cleanup needed!")
        return
    
    # Sample a few to verify they're actually finished or not
    print("\n🔍 Checking sample games to verify they're actually finished...")
    sample_size = min(5, len(bad_games))
    actually_finished = 0
    
    for i, r in enumerate(bad_games[:sample_size]):
        eid = int(r['event_id'])
        print(f"  Checking FI {eid}: {r['home_name']} vs {r['away_name']}")
        
        try:
            # Check if actually finished
            fast = betsapi.get_event_score_fast(eid) or {}
            ts = str(fast.get("time_status") or "")
            
            result = betsapi.get_event_result(eid) or {}
            has_result = (result.get("final_home") is not None)
            
            if ts == "3" or has_result:
                actually_finished += 1
                print(f"    ✅ Actually finished (ts={ts}, has_result={has_result})")
            else:
                print(f"    ❌ Not finished (ts={ts}, has_result={has_result})")
                
        except Exception as e:
            print(f"    ⚠️  API error: {e}")
    
    print(f"\nSample check: {actually_finished}/{sample_size} are actually finished")
    
    # Decision time
    print(f"\n📋 CLEANUP OPTIONS:")
    print(f"1. Conservative: Only clear games that are definitely not finished")
    print(f"2. Aggressive: Clear all {len(bad_games)} inconsistent games")
    print(f"3. Manual: Show me the first 10 to decide")
    print(f"4. Cancel")
    
    choice = input("\nChoose option (1-4): ").strip()
    
    if choice == "1":
        # Conservative: only clear games we can verify are not finished
        to_clear = []
        print(f"\n🔍 Checking all {len(bad_games)} games...")
        
        for i, r in enumerate(bad_games):
            if i % 20 == 0:
                print(f"  Progress: {i}/{len(bad_games)}")
            
            eid = int(r['event_id'])
            try:
                fast = betsapi.get_event_score_fast(eid) or {}
                ts = str(fast.get("time_status") or "")
                
                # Only clear if definitely not finished
                if ts in ("0", "1"):  # Not started or live
                    to_clear.append(eid)
            except:
                # If API fails, assume it might be finished (conservative)
                pass
        
        print(f"\nConservative cleanup: {len(to_clear)} games to clear")
        
    elif choice == "2":
        # Aggressive: clear all
        to_clear = [int(r['event_id']) for r in bad_games]
        print(f"\nAggressive cleanup: {len(to_clear)} games to clear")
        
    elif choice == "3":
        # Manual review
        print(f"\nFirst 10 games:")
        for r in bad_games[:10]:
            print(f"  FI {r['event_id']}: {r['home_name']} vs {r['away_name']} | Status: {r['status']} | Finals: {r['final_home']}-{r['final_away']}")
        
        decision = input(f"\nClear all {len(bad_games)} games? [y/N]: ")
        if decision.lower() == 'y':
            to_clear = [int(r['event_id']) for r in bad_games]
        else:
            print("Cancelled")
            return
            
    else:
        print("Cancelled")
        return
    
    # Execute cleanup
    if to_clear:
        confirm = input(f"\n⚠️  This will clear finals and results for {len(to_clear)} games. Continue? [y/N]: ")
        if confirm.lower() != 'y':
            print("Cancelled")
            return
        
        print(f"\n🧹 Cleaning {len(to_clear)} games...")
        
        for eid in to_clear:
            # Clear finals
            exec_sql("UPDATE event SET final_home=NULL, final_away=NULL WHERE event_id=?", (eid,))
            # Remove result rows
            exec_sql("DELETE FROM result WHERE event_id=?", (eid,))
        
        print(f"✅ Cleaned up {len(to_clear)} games")
        
        # Re-run verification
        print(f"\n📊 Re-running verification...")
        remaining = q("""
            SELECT COUNT(*) as count
            FROM event e
            JOIN result r ON r.event_id = e.event_id
            WHERE e.status != 'finished' OR e.final_home IS NULL OR e.final_away IS NULL
        """)[0]['count']
        
        if remaining == 0:
            print(f"🎉 All cleaned up! No more inconsistent data.")
        else:
            print(f"⚠️  Still {remaining} inconsistent games remaining")
    
    else:
        print("No games to clean")

if __name__ == "__main__":
    main()