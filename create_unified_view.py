# create_unified_view.py
import sqlite3

with sqlite3.connect("data/ebasketball.db") as con:
    con.execute("""
        CREATE VIEW IF NOT EXISTS all_game_lines AS
        SELECT 
            event_id,
            'opening' as capture_type,
            0 as quarter,
            market,
            line,
            opened_at_utc as captured_at,
            NULL as game_time_remaining,
            NULL as home_score,
            NULL as away_score
        FROM opener
        WHERE market = 'spread'
        
        UNION ALL
        
        SELECT 
            event_id,
            'quarter_end' as capture_type,
            quarter,
            market,
            line,
            captured_at_utc as captured_at,
            game_time_remaining,
            home_score,
            away_score
        FROM quarter_line
        WHERE market = 'spread'
        
        ORDER BY event_id, quarter
    """)
    
    print("Created unified view 'all_game_lines'")