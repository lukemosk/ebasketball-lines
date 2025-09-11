# debug_old_games.py - Figure out why the same 100 games keep appearing
import sqlite3
from datetime import datetime, timezone

DB = "data/ebasketball.db"

def debug_old_games():
    print("DEBUGGING PERSISTENT OLD GAMES")
    print("=" * 40)
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Find the old games that keep appearing
        old_games = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
            FROM event 
            WHERE status IN ('not_started', 'live')
              AND start_time_utc < datetime('now', '-6 hours')
            ORDER BY start_time_utc ASC
            LIMIT 10
        """).fetchall()
        
        print(f"Found {len(old_games)} old games still marked as not finished")
        print("Sample of oldest games:")
        
        for game in old_games:
            try:
                start_time = datetime.fromisoformat(game['start_time_utc'])
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                hours_ago = (now - start_time).total_seconds() / 3600
                
                print(f"\nFI {game['event_id']}: {game['home_name']} vs {game['away_name']}")
                print(f"  Started: {game['start_time_utc']} ({hours_ago:.1f}h ago)")
                print(f"  Status: {game['status']}")
                print(f"  Finals: {game['final_home']}-{game['final_away'] if game['final_away'] else 'None'}")
                
            except Exception as e:
                print(f"  Error processing: {e}")
        
        # Check the exact count
        total_count = con.execute("""
            SELECT COUNT(*) as count
            FROM event 
            WHERE status IN ('not_started', 'live')
              AND start_time_utc < datetime('now', '-6 hours')
        """).fetchone()['count']
        
        print(f"\nTotal old games: {total_count}")
        
        # Check if these are really old or there's a date issue
        oldest = con.execute("""
            SELECT MIN(start_time_utc) as oldest_start
            FROM event 
            WHERE status IN ('not_started', 'live')
              AND start_time_utc < datetime('now', '-6 hours')
        """).fetchone()['oldest_start']
        
        print(f"Oldest game start time: {oldest}")
        
        # Check if the cleanup SQL would actually work
        print(f"\nTesting cleanup SQL...")
        test_update = con.execute("""
            SELECT COUNT(*) as would_update
            FROM event 
            WHERE status IN ('not_started', 'live') 
              AND start_time_utc < datetime('now', '-6 hours')
        """).fetchone()['would_update']
        
        print(f"Games that would be updated: {test_update}")

def manual_cleanup():
    print(f"\nMANUAL CLEANUP OPTIONS:")
    print(f"1. Mark all old games as 'ended'")
    print(f"2. Delete very old games (>7 days)")
    print(f"3. Just mark games >24h as 'ended'")
    print(f"4. Check specific date ranges")
    
    choice = input(f"Choose option (1-4) or 'n' to skip: ")
    
    if choice == '1':
        with sqlite3.connect(DB) as con:
            result = con.execute("""
                UPDATE event 
                SET status = 'ended' 
                WHERE status IN ('not_started', 'live') 
                  AND start_time_utc < datetime('now', '-6 hours')
            """)
            con.commit()
            print(f"Updated {result.rowcount} games to 'ended'")
            
    elif choice == '2':
        count = input(f"Delete games older than how many days? (7): ") or "7"
        with sqlite3.connect(DB) as con:
            result = con.execute(f"""
                DELETE FROM event 
                WHERE start_time_utc < datetime('now', '-{count} days')
            """)
            con.commit()
            print(f"Deleted {result.rowcount} old games")
            
    elif choice == '3':
        with sqlite3.connect(DB) as con:
            result = con.execute("""
                UPDATE event 
                SET status = 'ended' 
                WHERE status IN ('not_started', 'live') 
                  AND start_time_utc < datetime('now', '-24 hours')
            """)
            con.commit()
            print(f"Updated {result.rowcount} games to 'ended'")
            
    elif choice == '4':
        with sqlite3.connect(DB) as con:
            con.row_factory = sqlite3.Row
            ranges = con.execute("""
                SELECT 
                    DATE(start_time_utc) as game_date,
                    COUNT(*) as count,
                    COUNT(CASE WHEN status IN ('not_started', 'live') THEN 1 END) as unfinished
                FROM event 
                WHERE start_time_utc >= datetime('now', '-7 days')
                GROUP BY DATE(start_time_utc)
                ORDER BY game_date DESC
            """).fetchall()
            
            for row in ranges:
                print(f"  {row['game_date']}: {row['count']} games, {row['unfinished']} unfinished")

if __name__ == "__main__":
    debug_old_games()
    manual_cleanup()