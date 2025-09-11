# fix_incorrectly_ended_games.py
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

def fix_incorrectly_ended_games():
    print("🔧 FIXING INCORRECTLY ENDED GAMES")
    print("=" * 50)
    
    # Find games marked as "ended" that started recently (last 4 hours)
    # These are likely incorrectly marked
    recent_ended = q("""
        SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
        FROM event 
        WHERE status IN ('ended', 'finished')
          AND start_time_utc >= datetime('now', '-4 hours')
          AND (final_home IS NULL OR final_away IS NULL)
        ORDER BY start_time_utc DESC
    """)
    
    print(f"Found {len(recent_ended)} recently 'ended' games without finals")
    
    if not recent_ended:
        print("✅ No incorrectly ended games found!")
        return
    
    # Check each game's actual status
    to_fix = []
    actually_finished = []
    
    for game in recent_ended:
        eid = int(game['event_id'])
        
        print(f"\n🔍 Checking FI {eid}: {game['home_name']} vs {game['away_name']}")
        
        try:
            # Check API status
            fast = betsapi.get_event_score_fast(eid) or {}
            result = betsapi.get_event_result(eid) or {}
            
            ts = str(fast.get("time_status") or "")
            ss = fast.get("SS") or fast.get("ss")
            has_result_finals = (result.get("final_home") is not None and result.get("final_away") is not None)
            
            print(f"  API: time_status='{ts}' | score={ss} | result_finals={has_result_finals}")
            
            # Determine correct status
            if ts == "3" or has_result_finals:
                # Actually finished
                actually_finished.append((eid, result.get("final_home"), result.get("final_away")))
                print(f"  ✅ Actually finished")
            elif ts == "1" or (ss and "-" in str(ss)):
                # Should be live
                to_fix.append((eid, "live"))
                print(f"  🔄 Should be LIVE")
            elif ts == "0" or ts == "":
                # Should be not_started
                to_fix.append((eid, "not_started"))
                print(f"  🔄 Should be NOT_STARTED")
            else:
                # Unclear
                print(f"  ❓ Unclear status (ts={ts})")
                
        except Exception as e:
            print(f"  ❌ API error: {e}")
    
    # Show summary
    print(f"\n📊 SUMMARY:")
    print(f"  Games to fix status: {len(to_fix)}")
    print(f"  Games actually finished: {len(actually_finished)}")
    
    if to_fix:
        print(f"\n🔄 GAMES TO FIX:")
        for eid, new_status in to_fix:
            game = next(g for g in recent_ended if g['event_id'] == eid)
            print(f"  FI {eid}: {game['home_name']} vs {game['away_name']} → {new_status}")
    
    if actually_finished:
        print(f"\n✅ GAMES TO UPDATE WITH FINALS:")
        for eid, fh, fa in actually_finished:
            game = next(g for g in recent_ended if g['event_id'] == eid)
            print(f"  FI {eid}: {game['home_name']} vs {game['away_name']} → {fh}-{fa}")
    
    # Apply fixes
    if to_fix or actually_finished:
        proceed = input(f"\n🔧 Apply fixes? [y/N]: ")
        if proceed.lower() == 'y':
            
            # Fix status for incorrectly ended games
            for eid, new_status in to_fix:
                exec_sql("""
                    UPDATE event 
                    SET status = ?, final_home = NULL, final_away = NULL 
                    WHERE event_id = ?
                """, (new_status, eid))
                print(f"  ✅ Fixed FI {eid} → {new_status}")
            
            # Add finals for actually finished games
            for eid, fh, fa in actually_finished:
                if fh is not None and fa is not None:
                    exec_sql("""
                        UPDATE event 
                        SET status = 'finished', final_home = ?, final_away = ? 
                        WHERE event_id = ?
                    """, (int(fh), int(fa), eid))
                    print(f"  ✅ Added finals FI {eid} → {fh}-{fa}")
            
            print(f"\n🎉 Fixed {len(to_fix) + len(actually_finished)} games!")
            
        else:
            print("Cancelled - no changes made")

def clean_old_incorrectly_ended():
    """Also clean up older games that are definitely wrong"""
    print(f"\n🧹 CHECKING OLDER INCORRECTLY ENDED GAMES:")
    
    # Games marked as ended >2 hours ago without finals (probably wrong)
    old_ended = q("""
        SELECT event_id, start_time_utc, home_name, away_name, status
        FROM event 
        WHERE status IN ('ended', 'finished')
          AND start_time_utc < datetime('now', '-2 hours')
          AND start_time_utc >= datetime('now', '-24 hours')
          AND final_home IS NULL
        ORDER BY start_time_utc DESC
        LIMIT 20
    """)
    
    if old_ended:
        print(f"  Found {len(old_ended)} older games marked 'ended' without finals")
        print(f"  These are probably incorrectly marked...")
        
        reset_old = input(f"  Reset these to 'not_started'? [y/N]: ")
        if reset_old.lower() == 'y':
            for game in old_ended:
                exec_sql("UPDATE event SET status = 'not_started' WHERE event_id = ?", (game['event_id'],))
            print(f"  ✅ Reset {len(old_ended)} old games to 'not_started'")
    else:
        print(f"  ✅ No old incorrectly ended games found")

if __name__ == "__main__":
    fix_incorrectly_ended_games()
    clean_old_incorrectly_ended()