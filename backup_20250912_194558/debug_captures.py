# debug_captures.py
import sqlite3

def debug_database():
    with sqlite3.connect("data/ebasketball.db") as con:
        con.row_factory = sqlite3.Row
        
        print("DATABASE DEBUG")
        print("=" * 80)
        
        # Check events
        events = con.execute("SELECT COUNT(*) as count FROM event").fetchone()
        print(f"\nTotal events: {events['count']}")
        
        recent_events = con.execute("""
            SELECT event_id, home_name, away_name, status, start_time_utc 
            FROM event 
            ORDER BY start_time_utc DESC 
            LIMIT 5
        """).fetchall()
        
        print("\nRecent events:")
        for e in recent_events:
            print(f"  FI {e['event_id']}: {e['home_name']} vs {e['away_name']} - {e['status']}")
        
        # Check openers
        openers = con.execute("SELECT COUNT(*) as count FROM opener").fetchone()
        print(f"\nTotal openers: {openers['count']}")
        
        if openers['count'] > 0:
            recent_openers = con.execute("""
                SELECT event_id, market, line, opened_at_utc 
                FROM opener 
                ORDER BY opened_at_utc DESC 
                LIMIT 5
            """).fetchall()
            
            print("\nRecent openers:")
            for o in recent_openers:
                print(f"  FI {o['event_id']}: {o['market']}={o['line']} @ {o['opened_at_utc']}")
        
        # Check quarter_lines
        quarter_lines = con.execute("SELECT COUNT(*) as count FROM quarter_line").fetchone()
        print(f"\nTotal quarter_lines: {quarter_lines['count']}")
        
        if quarter_lines['count'] > 0:
            all_quarters = con.execute("""
                SELECT event_id, quarter, market, line, captured_at_utc, 
                       game_time_remaining, home_score, away_score
                FROM quarter_line 
                ORDER BY captured_at_utc DESC
            """).fetchall()
            
            print("\nALL quarter captures:")
            for q in all_quarters:
                print(f"  FI {q['event_id']}: Q{q['quarter']} {q['market']}={q['line']} "
                      f"@ {q['captured_at_utc']} (time_left: {q['game_time_remaining']}s)")
        
        # Check if we have the unified view
        view_test = con.execute("""
            SELECT COUNT(*) as count FROM all_game_lines
        """).fetchone()
        print(f"\nUnified view 'all_game_lines' has: {view_test['count']} rows")

if __name__ == "__main__":
    debug_database()