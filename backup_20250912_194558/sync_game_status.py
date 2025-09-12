# sync_game_status.py - Fix database status mismatches
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

def get_api_status_and_finals(event_id):
    """Get definitive status and finals from API"""
    try:
        # Check fast endpoint
        fast = betsapi.get_event_score_fast(event_id) or {}
        ts = str(fast.get("time_status") or "")
        
        # Check result endpoint  
        result = betsapi.get_event_result(event_id) or {}
        
        # Determine if finished and get finals
        finished = False
        final_home = final_away = None
        
        if ts == "3":
            finished = True
            # Try to get finals from fast endpoint
            final_home = fast.get("final_home")
            final_away = fast.get("final_away")
            
            # If not available, try parsing SS
            if final_home is None or final_away is None:
                ss = fast.get("SS") or fast.get("ss")
                if isinstance(ss, str) and "-" in ss:
                    try:
                        h, a = ss.split("-", 1)
                        final_home, final_away = int(h), int(a)
                    except:
                        pass
        
        # Check result endpoint as backup
        if result.get("final_home") is not None and result.get("final_away") is not None:
            finished = True
            final_home = int(result["final_home"])
            final_away = int(result["final_away"])
        
        # Determine status
        if finished:
            status = "finished"
        elif ts == "1":
            status = "live"
        elif ts == "0":
            status = "not_started"
        else:
            status = None  # Unknown, don't update
        
        return status, final_home, final_away, ts
        
    except Exception as e:
        print(f"  ❌ API error for FI {event_id}: {e}")
        return None, None, None, None

def sync_recent_games():
    print("🔄 SYNCING GAME STATUS WITH API")
    print("=" * 50)
    
    # Get recent games that might need status updates
    recent_games = q("""
        SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
        FROM event 
        WHERE start_time_utc >= datetime('now', '-6 hours')
        ORDER BY start_time_utc DESC
    """)
    
    print(f"Found {len(recent_games)} recent games to check")
    
    updates_made = 0
    finals_added = 0
    status_fixed = 0
    
    for i, game in enumerate(recent_games):
        eid = int(game['event_id'])
        
        if i % 10 == 0:
            print(f"  Progress: {i}/{len(recent_games)}")
        
        # Get API status
        api_status, api_fh, api_fa, api_ts = get_api_status_and_finals(eid)
        
        if api_status is None:
            continue  # Skip if API error
        
        updates_needed = []
        
        # Check if status needs updating
        if game['status'] != api_status:
            updates_needed.append(f"status: {game['status']} → {api_status}")
            status_fixed += 1
        
        # Check if finals need updating
        db_has_finals = (game['final_home'] is not None and game['final_away'] is not None)
        api_has_finals = (api_fh is not None and api_fa is not None)
        
        if api_has_finals and not db_has_finals:
            updates_needed.append(f"finals: None → {api_fh}-{api_fa}")
            finals_added += 1
        elif api_has_finals and db_has_finals and (game['final_home'] != api_fh or game['final_away'] != api_fa):
            updates_needed.append(f"finals: {game['final_home']}-{game['final_away']} → {api_fh}-{api_fa}")
        
        # Apply updates if needed
        if updates_needed:
            updates_made += 1
            print(f"  🔄 FI {eid}: {', '.join(updates_needed)}")
            
            exec_sql("""
                UPDATE event 
                SET status = ?, final_home = ?, final_away = ?
                WHERE event_id = ?
            """, (api_status, api_fh, api_fa, eid))
    
    print(f"\n📊 SYNC SUMMARY:")
    print(f"  Games checked: {len(recent_games)}")
    print(f"  Updates made: {updates_made}")
    print(f"  Status fixes: {status_fixed}")
    print(f"  Finals added: {finals_added}")
    
    if updates_made == 0:
        print(f"  ✅ All games already in sync!")
    else:
        print(f"  🔄 Synced {updates_made} games with API")

def find_problematic_games():
    """Find games with obvious status issues"""
    print(f"\n🔍 FINDING PROBLEMATIC GAMES:")
    
    # Games that started >30 minutes ago but still show as not_started
    old_not_started = q("""
        SELECT event_id, start_time_utc, home_name, away_name, status
        FROM event
        WHERE status = 'not_started'
          AND start_time_utc < datetime('now', '-30 minutes')
          AND start_time_utc >= datetime('now', '-6 hours')
        ORDER BY start_time_utc DESC
    """)
    
    if old_not_started:
        print(f"  ⚠️  {len(old_not_started)} games still 'not_started' >30min after start:")
        for game in old_not_started[:5]:
            print(f"    FI {game['event_id']}: {game['home_name']} vs {game['away_name']} @ {game['start_time_utc']}")
    
    # Games marked as live but started >2 hours ago (should be finished)
    old_live = q("""
        SELECT event_id, start_time_utc, home_name, away_name, status
        FROM event
        WHERE status = 'live'
          AND start_time_utc < datetime('now', '-2 hours')
        ORDER BY start_time_utc DESC
    """)
    
    if old_live:
        print(f"  ⚠️  {len(old_live)} games still 'live' >2h after start:")
        for game in old_live[:5]:
            print(f"    FI {game['event_id']}: {game['home_name']} vs {game['away_name']} @ {game['start_time_utc']}")

def main():
    find_problematic_games()
    
    proceed = input(f"\n🔄 Sync game status with API? [y/N]: ")
    if proceed.lower() == 'y':
        sync_recent_games()
    else:
        print("Cancelled")

if __name__ == "__main__":
    main()