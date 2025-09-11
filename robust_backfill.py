# robust_backfill.py - More targeted approach to backfill old games
import sqlite3
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from src import betsapi

DB = "data/ebasketball.db"

def find_old_unfinished_games():
    print("FINDING OLD GAMES THAT SHOULD BE FINISHED")
    print("=" * 50)
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Find games that started more than 2 hours ago but don't have finals
        old_games = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status,
                   (julianday('now') - julianday(start_time_utc)) * 24 AS hours_old
            FROM event 
            WHERE start_time_utc < datetime('now', '-2 hours')
              AND (final_home IS NULL OR final_away IS NULL)
            ORDER BY start_time_utc ASC
        """).fetchall()
        
        print(f"Found {len(old_games)} games older than 2 hours without finals")
        
        if old_games:
            print("\nOldest 10 games:")
            for game in old_games[:10]:
                print(f"  FI {game['event_id']}: {game['home_name']} vs {game['away_name']}")
                print(f"    Started: {game['start_time_utc']} ({game['hours_old']:.1f}h ago)")
                print(f"    Status: {game['status']}")
        
        return old_games

def backfill_batch(games, batch_size=10):
    """Process games in small batches to avoid overwhelming the API"""
    
    fixed_count = 0
    error_count = 0
    no_data_count = 0
    
    with sqlite3.connect(DB) as con:
        for i in range(0, len(games), batch_size):
            batch = games[i:i+batch_size]
            print(f"\nProcessing batch {i//batch_size + 1} ({len(batch)} games)...")
            
            for game in batch:
                eid = int(game['event_id'])
                
                try:
                    # Try multiple methods to get finals
                    final_home, final_away = None, None
                    
                    # Method 1: Result endpoint
                    result = betsapi.get_event_result(eid) or {}
                    if result.get("final_home") is not None and result.get("final_away") is not None:
                        final_home, final_away = int(result["final_home"]), int(result["final_away"])
                        source = "result"
                    
                    # Method 2: Fast endpoint if result didn't work
                    if final_home is None:
                        fast = betsapi.get_event_score_fast(eid) or {}
                        
                        # Try explicit finals first
                        if fast.get("final_home") is not None and fast.get("final_away") is not None:
                            final_home, final_away = int(fast["final_home"]), int(fast["final_away"])
                            source = "fast-explicit"
                        
                        # Try parsing SS field
                        elif isinstance(fast.get("ss"), str) or isinstance(fast.get("SS"), str):
                            ss = fast.get("ss") or fast.get("SS")
                            if "-" in ss:
                                try:
                                    h, a = ss.split("-", 1)
                                    final_home, final_away = int(h.strip()), int(a.strip())
                                    source = "fast-ss"
                                except:
                                    pass
                    
                    # Method 3: Look for the game in ended events by date
                    if final_home is None:
                        try:
                            game_date = game['start_time_utc'][:10]  # YYYY-MM-DD
                            final_home, final_away = betsapi.find_final_in_ended(eid, game_date)
                            if final_home is not None:
                                source = "ended"
                        except:
                            pass
                    
                    # Update if we found finals
                    if final_home is not None and final_away is not None:
                        con.execute("""
                            UPDATE event 
                            SET status = 'finished', final_home = ?, final_away = ?
                            WHERE event_id = ?
                        """, (final_home, final_away, eid))
                        
                        print(f"  ✅ FI {eid}: {final_home}-{final_away} (via {source})")
                        fixed_count += 1
                    else:
                        print(f"  ❓ FI {eid}: No finals found")
                        no_data_count += 1
                        
                except Exception as e:
                    print(f"  ❌ FI {eid}: Error - {e}")
                    error_count += 1
            
            con.commit()
            
            # Brief pause between batches to be nice to the API
            if i + batch_size < len(games):
                import time
                time.sleep(2)
    
    return fixed_count, error_count, no_data_count

def backfill_historical_games():
    old_games = find_old_unfinished_games()
    
    if not old_games:
        print("No old games need backfilling")
        return
    
    print(f"\nFound {len(old_games)} games that could be backfilled")
    
    # Show breakdown by age
    now = datetime.now(timezone.utc)
    age_groups = {"2-6h": 0, "6-24h": 0, "1-7d": 0, ">7d": 0}
    
    for game in old_games:
        hours_old = game['hours_old']
        if hours_old < 6:
            age_groups["2-6h"] += 1
        elif hours_old < 24:
            age_groups["6-24h"] += 1
        elif hours_old < 168:  # 7 days
            age_groups["1-7d"] += 1
        else:
            age_groups[">7d"] += 1
    
    print(f"\nAge breakdown:")
    for age_range, count in age_groups.items():
        print(f"  {age_range}: {count} games")
    
    # Options for user
    print(f"\nBackfill options:")
    print(f"1. Backfill recent games (2-24 hours old) - {age_groups['2-6h'] + age_groups['6-24h']} games")
    print(f"2. Backfill all games up to 7 days old - {age_groups['2-6h'] + age_groups['6-24h'] + age_groups['1-7d']} games")
    print(f"3. Backfill everything - {len(old_games)} games")
    print(f"4. Cancel")
    
    choice = input(f"\nChoose option (1-4): ").strip()
    
    if choice == "1":
        target_games = [g for g in old_games if g['hours_old'] < 24]
    elif choice == "2":
        target_games = [g for g in old_games if g['hours_old'] < 168]
    elif choice == "3":
        target_games = old_games
    else:
        print("Cancelled")
        return
    
    if not target_games:
        print("No games in selected range")
        return
    
    print(f"\nStarting backfill for {len(target_games)} games...")
    fixed, errors, no_data = backfill_batch(target_games)
    
    print(f"\n🎉 BACKFILL COMPLETE:")
    print(f"  Successfully backfilled: {fixed} games")
    print(f"  API errors: {errors} games")
    print(f"  No data available: {no_data} games")
    
    if fixed > 0:
        print(f"\nRunning result calculations...")
        import subprocess
        result = subprocess.run(["python", "backfill_results.py"], capture_output=True, text=True)
        print("Result calculations complete")
        
        print(f"\nTo see your updated variance analysis:")
        print(f"python variance_analysis.py")

if __name__ == "__main__":
    backfill_historical_games()