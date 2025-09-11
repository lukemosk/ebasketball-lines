# data_pipeline_diagnosis.py - Find why you have so few complete records
import sqlite3

DB = "data/ebasketball.db"

def diagnose_data_pipeline():
    print("DATA PIPELINE DIAGNOSIS")
    print("=" * 40)
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # 1. Total events tracked
        total_events = con.execute("SELECT COUNT(*) as count FROM event").fetchone()['count']
        print(f"Total events in database: {total_events}")
        
        # 2. Events with finals
        events_with_finals = con.execute("""
            SELECT COUNT(*) as count FROM event 
            WHERE final_home IS NOT NULL AND final_away IS NOT NULL
        """).fetchone()['count']
        print(f"Events with finals: {events_with_finals} ({events_with_finals/total_events*100:.1f}%)")
        
        # 3. Events with openers
        events_with_spread = con.execute("""
            SELECT COUNT(DISTINCT event_id) as count FROM opener WHERE market='spread'
        """).fetchone()['count']
        
        events_with_total = con.execute("""
            SELECT COUNT(DISTINCT event_id) as count FROM opener WHERE market='total'
        """).fetchone()['count']
        
        print(f"Events with spread openers: {events_with_spread} ({events_with_spread/total_events*100:.1f}%)")
        print(f"Events with total openers: {events_with_total} ({events_with_total/total_events*100:.1f}%)")
        
        # 4. Events with result calculations
        events_with_results = con.execute("SELECT COUNT(*) as count FROM result").fetchone()['count']
        print(f"Events with result calculations: {events_with_results} ({events_with_results/total_events*100:.1f}%)")
        
        # 5. The complete pipeline (event + opener + result)
        complete_spread = con.execute("""
            SELECT COUNT(DISTINCT e.event_id) as count
            FROM event e
            JOIN opener o ON o.event_id = e.event_id AND o.market = 'spread'
            JOIN result r ON r.event_id = e.event_id
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
        """).fetchone()['count']
        
        complete_total = con.execute("""
            SELECT COUNT(DISTINCT e.event_id) as count
            FROM event e
            JOIN opener o ON o.event_id = e.event_id AND o.market = 'total'
            JOIN result r ON r.event_id = e.event_id
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
        """).fetchone()['count']
        
        print(f"Complete spread pipeline: {complete_spread} games")
        print(f"Complete total pipeline: {complete_total} games")
        
        # 6. What's missing for each stage
        print(f"\nBREAKDOWN OF MISSING DATA:")
        
        # Events with finals but no openers
        finals_no_openers = con.execute("""
            SELECT COUNT(*) as count FROM event e
            LEFT JOIN opener o ON o.event_id = e.event_id
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
            AND o.event_id IS NULL
        """).fetchone()['count']
        print(f"Finished games missing openers: {finals_no_openers}")
        
        # Events with openers but no finals
        openers_no_finals = con.execute("""
            SELECT COUNT(DISTINCT o.event_id) as count FROM opener o
            LEFT JOIN event e ON e.event_id = o.event_id
            WHERE e.final_home IS NULL OR e.final_away IS NULL
        """).fetchone()['count']
        print(f"Games with openers but no finals: {openers_no_finals}")
        
        # Events with finals but no result calculations
        finals_no_results = con.execute("""
            SELECT COUNT(*) as count FROM event e
            LEFT JOIN result r ON r.event_id = e.event_id
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
            AND r.event_id IS NULL
        """).fetchone()['count']
        print(f"Finished games missing result calculations: {finals_no_results}")
        
        # 7. Recent data to see current pipeline health
        print(f"\nRECENT DATA PIPELINE (last 24 hours):")
        
        recent_stats = con.execute("""
            SELECT 
                COUNT(*) as total_recent,
                SUM(CASE WHEN final_home IS NOT NULL THEN 1 ELSE 0 END) as recent_finals,
                (SELECT COUNT(DISTINCT event_id) FROM opener WHERE event_id IN 
                 (SELECT event_id FROM event WHERE start_time_utc >= datetime('now', '-24 hours'))) as recent_openers,
                (SELECT COUNT(*) FROM result WHERE event_id IN 
                 (SELECT event_id FROM event WHERE start_time_utc >= datetime('now', '-24 hours'))) as recent_results
            FROM event 
            WHERE start_time_utc >= datetime('now', '-24 hours')
        """).fetchone()
        
        print(f"Recent events: {recent_stats['total_recent']}")
        print(f"Recent with finals: {recent_stats['recent_finals']}")
        print(f"Recent with openers: {recent_stats['recent_openers']}")
        print(f"Recent with results: {recent_stats['recent_results']}")

def show_missing_pieces():
    print(f"\n" + "="*40)
    print("SPECIFIC GAMES MISSING PIECES")
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Games with finals but missing openers (these would complete your dataset)
        print(f"\nFinished games missing openers (top 10):")
        missing_openers = con.execute("""
            SELECT e.event_id, e.home_name, e.away_name, e.final_home, e.final_away, e.start_time_utc
            FROM event e
            LEFT JOIN opener o ON o.event_id = e.event_id
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
            AND o.event_id IS NULL
            ORDER BY e.start_time_utc DESC
            LIMIT 10
        """).fetchall()
        
        for game in missing_openers:
            print(f"  FI {game['event_id']}: {game['home_name']} vs {game['away_name']} ({game['final_home']}-{game['final_away']})")
        
        # Games with openers but missing finals
        print(f"\nGames with openers missing finals (top 10):")
        missing_finals = con.execute("""
            SELECT DISTINCT e.event_id, e.home_name, e.away_name, e.start_time_utc, e.status
            FROM opener o
            JOIN event e ON e.event_id = o.event_id
            WHERE e.final_home IS NULL OR e.final_away IS NULL
            ORDER BY e.start_time_utc DESC
            LIMIT 10
        """).fetchall()
        
        for game in missing_finals:
            print(f"  FI {game['event_id']}: {game['home_name']} vs {game['away_name']} (status: {game['status']})")

def suggest_improvements():
    print(f"\n" + "="*40)
    print("SUGGESTIONS TO INCREASE COMPLETE DATA")
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Count potential gains
        finished_no_openers = con.execute("""
            SELECT COUNT(*) as count FROM event e
            LEFT JOIN opener o ON o.event_id = e.event_id
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
            AND o.event_id IS NULL
        """).fetchone()['count']
        
        openers_no_results = con.execute("""
            SELECT COUNT(DISTINCT o.event_id) as count FROM opener o
            JOIN event e ON e.event_id = o.event_id
            LEFT JOIN result r ON r.event_id = e.event_id
            WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
            AND r.event_id IS NULL
        """).fetchone()['count']
        
        print(f"1. Backfill openers for {finished_no_openers} finished games")
        print(f"   This would add {finished_no_openers} more complete records")
        
        print(f"2. Run result calculations for {openers_no_results} games")
        print(f"   This would complete the pipeline")
        
        print(f"3. Let system run longer to collect more data")
        print(f"   You're currently collecting ~20-40 games per day")

if __name__ == "__main__":
    diagnose_data_pipeline()
    show_missing_pieces()
    suggest_improvements()