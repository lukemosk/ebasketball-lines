# check_captures.py
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "data/ebasketball.db"

def check_recent_captures():
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        
        # Get capture stats
        stats = con.execute("""
            SELECT 
                COUNT(DISTINCT event_id) as games,
                COUNT(*) as total_captures,
                COUNT(DISTINCT quarter) as quarters,
                MIN(captured_at_utc) as first_capture,
                MAX(captured_at_utc) as last_capture
            FROM quarter_line
        """).fetchone()
        
        print("QUARTER LINE CAPTURE STATS")
        print("=" * 50)
        print(f"Total games tracked: {stats['games']}")
        print(f"Total captures: {stats['total_captures']}")
        print(f"Quarters captured: {stats['quarters']}")
        print(f"First capture: {stats['first_capture']}")
        print(f"Last capture: {stats['last_capture']}")
        
        # Recent captures
        print("\nRECENT CAPTURES (Last 10):")
        print("-" * 50)
        
        recent = con.execute("""
            SELECT 
                q.event_id,
                q.quarter,
                q.market,
                q.line,
                q.captured_at_utc,
                q.game_time_remaining,
                q.home_score,
                q.away_score,
                e.home_name,
                e.away_name
            FROM quarter_line q
            JOIN event e ON e.event_id = q.event_id
            ORDER BY q.captured_at_utc DESC
            LIMIT 10
        """).fetchall()
        
        for r in recent:
            print(f"\n{r['captured_at_utc']} - Q{r['quarter']}")
            print(f"  {r['home_name']} vs {r['away_name']}")
            print(f"  Score: {r['home_score']}-{r['away_score']} ({r['game_time_remaining']}s remaining)")
            print(f"  {r['market']}: {r['line']}")

if __name__ == "__main__":
    check_recent_captures()