# live_monitor.py - Real-time monitoring of the fix
import sqlite3
import time
from datetime import datetime, timezone
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from src import betsapi

DB = "data/ebasketball.db"

def q(sql, args=()):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(sql, args).fetchall()

def check_current_state():
    """Check current state and return summary"""
    now = datetime.now(timezone.utc)
    
    # Recent games (last hour)
    recent = q("""
        SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
        FROM event 
        WHERE start_time_utc >= datetime('now', '-1 hour')
        ORDER BY start_time_utc DESC
    """)
    
    summary = {
        'total_recent': len(recent),
        'with_finals': 0,
        'false_positives': 0,
        'correctly_live': 0,
        'correctly_finished': 0,
        'issues': []
    }
    
    for r in recent:
        eid = int(r['event_id'])
        has_finals = (r['final_home'] is not None and r['final_away'] is not None)
        
        if has_finals:
            summary['with_finals'] += 1
            
            # Verify if actually finished
            try:
                fast = betsapi.get_event_score_fast(eid) or {}
                ts = str(fast.get("time_status") or "")
                actually_finished = (ts == "3")
                
                if actually_finished:
                    summary['correctly_finished'] += 1
                else:
                    summary['false_positives'] += 1
                    summary['issues'].append(f"FI {eid}: {r['home_name']} vs {r['away_name']} has finals but ts={ts}")
            except:
                summary['issues'].append(f"FI {eid}: API error checking status")
        else:
            # No finals - check if this is correct
            try:
                fast = betsapi.get_event_score_fast(eid) or {}
                ts = str(fast.get("time_status") or "")
                if ts in ("0", "1"):  # Not started or live
                    summary['correctly_live'] += 1
                elif ts == "3":
                    summary['issues'].append(f"FI {eid}: {r['home_name']} vs {r['away_name']} finished but no finals")
            except:
                pass
    
    return summary

def print_status(summary):
    """Print current status"""
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"\n[{now}] 📊 Current Status:")
    print(f"  Recent games (1h): {summary['total_recent']}")
    print(f"  With finals: {summary['with_finals']}")
    print(f"  ✅ Correctly finished: {summary['correctly_finished']}")
    print(f"  ✅ Correctly live/upcoming: {summary['correctly_live']}")
    print(f"  ❌ False positives: {summary['false_positives']}")
    
    if summary['issues']:
        print(f"  🚨 Issues found:")
        for issue in summary['issues'][:3]:  # Show max 3
            print(f"    {issue}")
        if len(summary['issues']) > 3:
            print(f"    ... and {len(summary['issues']) - 3} more")
    
    # Overall health
    if summary['false_positives'] == 0 and len(summary['issues']) == 0:
        print("  🎉 System is healthy!")
    elif summary['false_positives'] > 0:
        print(f"  ⚠️  Still has {summary['false_positives']} false positives")

def monitor_live(duration_minutes=10):
    """Monitor for a specified duration"""
    print(f"🔄 Starting live monitor for {duration_minutes} minutes...")
    print("Press Ctrl+C to stop early")
    
    end_time = time.time() + (duration_minutes * 60)
    
    try:
        while time.time() < end_time:
            summary = check_current_state()
            print_status(summary)
            
            time.sleep(30)  # Check every 30 seconds
            
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")

def quick_check():
    """Just do one quick check"""
    summary = check_current_state()
    print_status(summary)
    return summary['false_positives'] == 0 and len(summary['issues']) == 0

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        monitor_live(duration)
    else:
        # Quick check
        is_healthy = quick_check()
        sys.exit(0 if is_healthy else 1)