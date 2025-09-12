# cleanup_bad_timing.py
import sqlite3

with sqlite3.connect("data/ebasketball.db") as con:
    # Remove quarter captures that have wrong timing
    # (e.g., captured with 29s remaining instead of at quarter end)
    con.execute("""
        DELETE FROM quarter_line 
        WHERE game_time_remaining > 10
    """)
    
    deleted = con.execute("SELECT changes()").fetchone()[0]
    print(f"Removed {deleted} incorrectly timed quarter captures")
    
    # Show what's left
    remaining = con.execute("SELECT COUNT(*) FROM quarter_line").fetchone()[0]
    print(f"Remaining quarter captures: {remaining}")