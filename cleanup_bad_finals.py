# cleanup_bad_finals.py
from __future__ import annotations
import sqlite3
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

def main():
    # Find recent games (last 4 hours) that have finals but may not actually be finished
    rows = q("""
        SELECT event_id, final_home, final_away, home_name, away_name
        FROM event 
        WHERE start_time_utc >= datetime('now', '-4 hours')
          AND final_home IS NOT NULL 
          AND final_away IS NOT NULL
        ORDER BY start_time_utc DESC
    """)
    
    print(f"Checking {len(rows)} recent games with finals...")
    
    to_clear = []
    for r in rows:
        eid = int(r["event_id"])
        
        # Use your existing betsapi functions to verify if actually finished
        fast = betsapi.get_event_score_fast(eid) or {}
        ts = str(fast.get("time_status") or "")
        
        # Game is only finished if time_status == "3" 
        actually_finished = (ts == "3")
        
        # Double-check with result endpoint
        if not actually_finished:
            result = betsapi.get_event_result(eid) or {}
            if result.get("final_home") is not None and result.get("final_away") is not None:
                actually_finished = True
        
        if not actually_finished:
            to_clear.append((eid, r["home_name"], r["away_name"], ts))
    
    if not to_clear:
        print("✅ No incorrectly finished games found!")
        return
    
    print(f"\n❌ Found {len(to_clear)} games incorrectly marked as finished:")
    for eid, home, away, ts in to_clear:
        print(f"  FI {eid}: {home} vs {away} (time_status={ts})")
    
    confirm = input(f"\nClear finals for these {len(to_clear)} games? [y/N]: ")
    if confirm.lower() == 'y':
        for eid, _, _, _ in to_clear:
            # Clear the finals
            exec_sql("UPDATE event SET final_home=NULL, final_away=NULL WHERE event_id=?", (eid,))
            # Remove any result rows (they'll be recalculated when game actually finishes)
            exec_sql("DELETE FROM result WHERE event_id=?", (eid,))
        
        print(f"✅ Cleared {len(to_clear)} incorrect finals")
    else:
        print("Cancelled - no changes made")

if __name__ == "__main__":
    main()