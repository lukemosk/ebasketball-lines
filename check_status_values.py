# check_status_values.py - See what status values actually exist
import sqlite3

DB = "data/ebasketball.db"

def check_status_values():
    print("📊 CHECKING ACTUAL STATUS VALUES IN DATABASE")
    print("=" * 50)
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Get all unique status values
        statuses = con.execute("""
            SELECT status, COUNT(*) as count
            FROM event 
            GROUP BY status
            ORDER BY count DESC
        """).fetchall()
        
        print("All status values in database:")
        for row in statuses:
            print(f"  '{row['status']}': {row['count']} games")
        
        print(f"\n🔍 RECENT GAMES (last 4 hours) BY STATUS:")
        recent_by_status = con.execute("""
            SELECT status, COUNT(*) as count
            FROM event 
            WHERE start_time_utc >= datetime('now', '-4 hours')
            GROUP BY status
            ORDER BY count DESC
        """).fetchall()
        
        for row in recent_by_status:
            print(f"  '{row['status']}': {row['count']} recent games")
        
        print(f"\n🎯 PROBLEMATIC GAMES (recent 'ended' games):")
        problem_games = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
            FROM event 
            WHERE status = 'ended'
              AND start_time_utc >= datetime('now', '-4 hours')
            ORDER BY start_time_utc DESC
            LIMIT 10
        """).fetchall()
        
        if problem_games:
            for game in problem_games:
                finals_str = f"{game['final_home']}-{game['final_away']}" if game['final_home'] else "None"
                print(f"  FI {game['event_id']}: {game['home_name']} vs {game['away_name']}")
                print(f"    Start: {game['start_time_utc']} | Finals: {finals_str}")
        else:
            print("  ✅ No recent 'ended' games found")
        
        print(f"\n📋 GAMES THAT SHOULD BE LIVE (started 5-60 min ago):")
        should_be_live = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
            FROM event 
            WHERE start_time_utc >= datetime('now', '-60 minutes')
              AND start_time_utc <= datetime('now', '-5 minutes')
            ORDER BY start_time_utc DESC
            LIMIT 10
        """).fetchall()
        
        for game in should_be_live:
            finals_str = f"{game['final_home']}-{game['final_away']}" if game['final_home'] else "None"
            print(f"  FI {game['event_id']}: {game['home_name']} vs {game['away_name']}")
            print(f"    Status: '{game['status']}' | Finals: {finals_str}")

if __name__ == "__main__":
    check_status_values()