# targeted_status_fix.py - Fix the specific status issues
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

def fix_status_issues():
    print("🎯 TARGETED STATUS FIX")
    print("=" * 40)
    
    # Get games from the last 4 hours that might have wrong status
    recent_games = q("""
        SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
        FROM event 
        WHERE start_time_utc >= datetime('now', '-4 hours')
        ORDER BY start_time_utc DESC
    """)
    
    print(f"Checking {len(recent_games)} recent games...")
    
    fixes_needed = []
    
    for game in recent_games:
        eid = int(game['event_id'])
        
        # Calculate time since start
        try:
            start_utc = datetime.fromisoformat(game['start_time_utc'])
            if start_utc.tzinfo is None:
                start_utc = start_utc.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            minutes_since_start = (now - start_utc).total_seconds() / 60
        except:
            minutes_since_start = 0
        
        # Check what status it SHOULD have
        current_status = game['status']
        has_finals = (game['final_home'] is not None and game['final_away'] is not None)
        
        # Determine correct status based on time and finals
        if has_finals:
            correct_status = "finished"
        elif minutes_since_start < -5:  # Starts in future
            correct_status = "not_started"
        elif -5 <= minutes_since_start <= 25:  # Should be live or recently finished
            # Check API to see if we can get more info
            try:
                fast = betsapi.get_event_score_fast(eid) or {}
                ts = str(fast.get("time_status") or "")
                ss = fast.get("SS") or fast.get("ss")
                
                if ts == "3":
                    correct_status = "finished"
                elif ts == "1" or (ss and "-" in str(ss)):
                    correct_status = "live"
                elif ts == "0":
                    correct_status = "not_started"
                else:
                    # API unclear - use time-based logic
                    if minutes_since_start > 20:
                        correct_status = "finished"  # Game should be done
                    elif minutes_since_start > 0:
                        correct_status = "live"
                    else:
                        correct_status = "not_started"
            except:
                # API error - use time-based logic
                if minutes_since_start > 20:
                    correct_status = "finished"
                elif minutes_since_start > 0:
                    correct_status = "live"
                else:
                    correct_status = "not_started"
        else:
            # Old game - should probably be finished or not_started
            correct_status = "not_started"  # Conservative approach
        
        # Check if fix needed
        if current_status != correct_status:
            fixes_needed.append({
                'event_id': eid,
                'teams': f"{game['home_name']} vs {game['away_name']}",
                'start_time': game['start_time_utc'],
                'minutes_ago': f"{minutes_since_start:.1f}",
                'current_status': current_status,
                'correct_status': correct_status,
                'has_finals': has_finals
            })
    
    if not fixes_needed:
        print("✅ All game statuses look correct!")
        return
    
    print(f"\n🔧 FOUND {len(fixes_needed)} GAMES NEEDING STATUS FIXES:")
    print("-" * 80)
    
    for fix in fixes_needed:
        print(f"FI {fix['event_id']}: {fix['teams']}")
        print(f"  Started {fix['minutes_ago']} min ago | {fix['current_status']} → {fix['correct_status']}")
        print(f"  Has finals: {fix['has_finals']}")
        print()
    
    # Apply fixes
    proceed = input(f"Apply these {len(fixes_needed)} status fixes? [y/N]: ")
    if proceed.lower() == 'y':
        for fix in fixes_needed:
            if fix['correct_status'] == "finished" and not fix['has_finals']:
                # Don't mark as finished without finals
                new_status = "live"
            else:
                new_status = fix['correct_status']
            
            exec_sql("UPDATE event SET status = ? WHERE event_id = ?", (new_status, fix['event_id']))
            print(f"✅ Fixed FI {fix['event_id']}: {fix['current_status']} → {new_status}")
        
        print(f"\n🎉 Applied {len(fixes_needed)} status fixes!")
        
        # Clean up any finals for games that shouldn't have them
        cleanup = input(f"Also clear finals for games marked as live/not_started? [y/N]: ")
        if cleanup.lower() == 'y':
            exec_sql("""
                UPDATE event 
                SET final_home = NULL, final_away = NULL 
                WHERE status IN ('live', 'not_started') 
                AND (final_home IS NOT NULL OR final_away IS NOT NULL)
            """)
            print("✅ Cleared finals for live/not_started games")
    else:
        print("Cancelled - no changes made")

if __name__ == "__main__":
    fix_status_issues()