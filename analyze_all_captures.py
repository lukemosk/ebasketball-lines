# analyze_all_captures.py
import sqlite3

def show_all_game_captures():
    """Show all captured lines for each game, organized by timing"""
    
    with sqlite3.connect("data/ebasketball.db") as con:
        con.row_factory = sqlite3.Row
        
        # Get all games with any captures
        games = con.execute("""
            SELECT DISTINCT e.event_id, e.home_name, e.away_name, e.start_time_utc
            FROM event e
            WHERE EXISTS (SELECT 1 FROM opener o WHERE o.event_id = e.event_id)
               OR EXISTS (SELECT 1 FROM quarter_line q WHERE q.event_id = e.event_id)
            ORDER BY e.start_time_utc DESC
            LIMIT 20
        """).fetchall()
        
        print("CAPTURED LINES BY GAME AND TIMING")
        print("=" * 80)
        
        for game in games:
            print(f"\nFI {game['event_id']}: {game['home_name']} vs {game['away_name']}")
            print(f"Started: {game['start_time_utc']}")
            
            # Get opening line
            opener = con.execute("""
                SELECT market, line, opened_at_utc 
                FROM opener 
                WHERE event_id = ? AND market = 'spread'
            """, (game['event_id'],)).fetchone()
            
            if opener:
                print(f"  📍 Opening (Q1 start): {opener['line']:.1f} @ {opener['opened_at_utc']}")
            else:
                print(f"  📍 Opening (Q1 start): Not captured")
            
            # Get quarter-end lines
            quarters = con.execute("""
                SELECT quarter, line, captured_at_utc, game_time_remaining, home_score, away_score
                FROM quarter_line
                WHERE event_id = ? AND market = 'spread'
                ORDER BY quarter
            """, (game['event_id'],)).fetchall()
            
            for q in quarters:
                print(f"  🏁 Q{q['quarter']} end: {q['line']:.1f} @ {q['captured_at_utc']} "
                      f"(score: {q['home_score']}-{q['away_score']}, {q['game_time_remaining']}s left)")
            
            if not quarters:
                print(f"  🏁 Quarter ends: None captured yet")

if __name__ == "__main__":
    show_all_game_captures()