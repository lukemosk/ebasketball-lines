# comprehensive_cleanup.py - Clean all old bad data from database
import sqlite3
from datetime import datetime, timezone, timedelta
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

def find_bad_data():
    print("COMPREHENSIVE BAD DATA AUDIT")
    print("=" * 50)
    
    issues = []
    
    # 1. Games with finals that are too recent to be accurate
    recent_with_finals = q("""
        SELECT event_id, start_time_utc, home_name, away_name, final_home, final_away, status
        FROM event 
        WHERE start_time_utc >= datetime('now', '-48 hours')
          AND final_home IS NOT NULL
          AND final_away IS NOT NULL
        ORDER BY start_time_utc DESC
    """)
    
    suspicious_finals = []
    for game in recent_with_finals:
        try:
            start_time = datetime.fromisoformat(game['start_time_utc'])
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            hours_since_start = (now - start_time).total_seconds() / 3600
            
            # Check if finals look suspicious (too low scores for finished games)
            total_score = game['final_home'] + game['final_away']
            
            if total_score < 35 and hours_since_start < 2:
                suspicious_finals.append(game)
                issues.append(f"FI {game['event_id']}: Suspiciously low score {game['final_home']}-{game['final_away']} for recent game")
                
        except Exception:
            pass
    
    # 2. Result rows for games without proper finals
    orphaned_results = q("""
        SELECT r.event_id, e.final_home, e.final_away
        FROM result r
        JOIN event e ON e.event_id = r.event_id
        WHERE e.final_home IS NULL OR e.final_away IS NULL
    """)
    
    if orphaned_results:
        issues.append(f"{len(orphaned_results)} result rows exist for games without finals")
    
    # 3. Games marked as finished without finals
    finished_no_finals = q("""
        SELECT event_id, start_time_utc, home_name, away_name, status
        FROM event 
        WHERE status IN ('finished', 'ended')
          AND (final_home IS NULL OR final_away IS NULL)
          AND start_time_utc < datetime('now', '-2 hours')
    """)
    
    if finished_no_finals:
        issues.append(f"{len(finished_no_finals)} games marked finished but no finals")
    
    # 4. Very old games still marked as not_started/live
    old_not_finished = q("""
        SELECT event_id, start_time_utc, home_name, away_name, status
        FROM event 
        WHERE status IN ('not_started', 'live')
          AND start_time_utc < datetime('now', '-6 hours')
    """)
    
    if old_not_finished:
        issues.append(f"{len(old_not_finished)} very old games still marked as not finished")
    
    return {
        'suspicious_finals': suspicious_finals,
        'orphaned_results': orphaned_results,
        'finished_no_finals': finished_no_finals,
        'old_not_finished': old_not_finished,
        'issues': issues
    }

def verify_recent_finals():
    print("\nVERIFYING RECENT FINALS AGAINST API")
    print("-" * 40)
    
    # Check games from last 24 hours that have finals
    recent_finished = q("""
        SELECT event_id, start_time_utc, home_name, away_name, final_home, final_away
        FROM event 
        WHERE start_time_utc >= datetime('now', '-24 hours')
          AND final_home IS NOT NULL
          AND final_away IS NOT NULL
        ORDER BY start_time_utc DESC
        LIMIT 15
    """)
    
    wrong_finals = []
    
    for game in recent_finished:
        eid = int(game['event_id'])
        db_score = f"{game['final_home']}-{game['final_away']}"
        
        try:
            # Check API for actual finals
            fast = betsapi.get_event_score_fast(eid) or {}
            result = betsapi.get_event_result(eid) or {}
            
            api_fh = result.get("final_home") or fast.get("final_home")
            api_fa = result.get("final_away") or fast.get("final_away")
            
            if api_fh is not None and api_fa is not None:
                api_score = f"{api_fh}-{api_fa}"
                if str(api_fh) != str(game['final_home']) or str(api_fa) != str(game['final_away']):
                    wrong_finals.append({
                        'event_id': eid,
                        'teams': f"{game['home_name']} vs {game['away_name']}",
                        'db_score': db_score,
                        'api_score': api_score,
                        'api_fh': int(api_fh),
                        'api_fa': int(api_fa)
                    })
                    print(f"MISMATCH FI {eid}: DB {db_score} vs API {api_score}")
                else:
                    print(f"OK FI {eid}: {db_score}")
            else:
                print(f"NO API DATA FI {eid}: {db_score}")
                
        except Exception as e:
            print(f"API ERROR FI {eid}: {e}")
    
    return wrong_finals

def cleanup_database():
    print("\nCLEANUP RECOMMENDATIONS")
    print("-" * 40)
    
    bad_data = find_bad_data()
    wrong_finals = verify_recent_finals()
    
    cleanup_actions = []
    
    # Plan cleanup actions
    if bad_data['orphaned_results']:
        cleanup_actions.append(("Delete orphaned result rows", f"DELETE FROM result WHERE event_id IN ({','.join(str(r['event_id']) for r in bad_data['orphaned_results'])})"))
    
    if bad_data['finished_no_finals']:
        cleanup_actions.append(("Reset finished games without finals", "UPDATE event SET status='not_started' WHERE status IN ('finished', 'ended') AND (final_home IS NULL OR final_away IS NULL)"))
    
    if bad_data['old_not_finished']:
        cleanup_actions.append(("Mark very old games as ended", "UPDATE event SET status='ended' WHERE status IN ('not_started', 'live') AND start_time_utc < datetime('now', '-6 hours')"))
    
    if wrong_finals:
        print(f"\nFound {len(wrong_finals)} games with incorrect finals:")
        for game in wrong_finals:
            print(f"  FI {game['event_id']}: {game['teams']} - {game['db_score']} should be {game['api_score']}")
    
    if bad_data['issues']:
        print(f"\nIssues found:")
        for issue in bad_data['issues']:
            print(f"  - {issue}")
    
    if cleanup_actions or wrong_finals:
        print(f"\nProposed cleanup:")
        for description, sql in cleanup_actions:
            print(f"  - {description}")
        
        if wrong_finals:
            print(f"  - Fix {len(wrong_finals)} incorrect finals")
        
        proceed = input(f"\nExecute cleanup? [y/N]: ")
        if proceed.lower() == 'y':
            # Execute SQL cleanups
            for description, sql in cleanup_actions:
                exec_sql(sql, ())
                print(f"✅ {description}")
            
            # Fix wrong finals
            if wrong_finals:
                for game in wrong_finals:
                    exec_sql("UPDATE event SET final_home=?, final_away=? WHERE event_id=?", 
                            (game['api_fh'], game['api_fa'], game['event_id']))
                    exec_sql("DELETE FROM result WHERE event_id=?", (game['event_id'],))
                print(f"✅ Fixed {len(wrong_finals)} incorrect finals")
            
            print(f"\n✅ Database cleanup complete!")
            print(f"Run backfill_results.py to recalculate result rows")
        else:
            print("Cleanup cancelled")
    else:
        print("✅ Database looks clean - no bad data found")

if __name__ == "__main__":
    cleanup_database()