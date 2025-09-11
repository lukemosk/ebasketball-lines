# verify_fix.py - Main verification script
from __future__ import annotations
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

print("🔍 VERIFICATION: Checking if in-progress games fix worked")
print("=" * 60)

# 1. Check recent games with finals - are they actually finished?
print("\n1️⃣ CHECKING: Recent games marked as finished")
recent_finals = q("""
    SELECT event_id, start_time_utc, home_name, away_name, final_home, final_away
    FROM event 
    WHERE start_time_utc >= datetime('now', '-2 hours')
      AND final_home IS NOT NULL 
      AND final_away IS NOT NULL
    ORDER BY start_time_utc DESC
    LIMIT 10
""")

if not recent_finals:
    print("✅ No recent games marked as finished (good if no games have actually ended)")
else:
    print(f"Found {len(recent_finals)} recent games with finals. Verifying each...")
    
    false_positives = 0
    for r in recent_finals:
        eid = int(r["event_id"])
        
        # Check if actually finished via API
        fast = betsapi.get_event_score_fast(eid) or {}
        ts = str(fast.get("time_status") or "")
        
        result = betsapi.get_event_result(eid) or {}
        has_result_final = (result.get("final_home") is not None and result.get("final_away") is not None)
        
        actually_finished = (ts == "3") or has_result_final
        
        status = "✅ CORRECT" if actually_finished else "❌ FALSE POSITIVE"
        if not actually_finished:
            false_positives += 1
            
        print(f"  FI {eid}: {r['home_name']} vs {r['away_name']}")
        print(f"    DB final: {r['final_home']}-{r['final_away']} | API time_status: {ts} | {status}")
    
    if false_positives == 0:
        print(f"\n✅ ALL {len(recent_finals)} finished games are correctly marked!")
    else:
        print(f"\n❌ Found {false_positives} games incorrectly marked as finished")

# 2. Check live/upcoming games - do they have finals when they shouldn't?
print("\n2️⃣ CHECKING: Live/upcoming games (should NOT have finals)")
live_with_finals = q("""
    SELECT event_id, start_time_utc, home_name, away_name, final_home, final_away, status
    FROM event 
    WHERE start_time_utc >= datetime('now', '-1 hour')
      AND status IN ('live', 'not_started')
      AND (final_home IS NOT NULL OR final_away IS NOT NULL)
    ORDER BY start_time_utc DESC
""")

if not live_with_finals:
    print("✅ No live/upcoming games have finals (correct!)")
else:
    print(f"❌ Found {len(live_with_finals)} live/upcoming games with finals (this is the bug!):")
    for r in live_with_finals:
        print(f"  FI {r['event_id']}: {r['home_name']} vs {r['away_name']} | Status: {r['status']} | Finals: {r['final_home']}-{r['final_away']}")

# 3. Sample a few live games to see current API status
print("\n3️⃣ CHECKING: Sample of current live games from API")
try:
    # Get some recent events and check their live status
    sample_events = q("""
        SELECT event_id, home_name, away_name, start_time_utc, status, final_home, final_away
        FROM event 
        WHERE start_time_utc >= datetime('now', '-30 minutes')
        ORDER BY start_time_utc DESC
        LIMIT 5
    """)
    
    if sample_events:
        print("Sampling recent events to verify API status detection:")
        for r in sample_events:
            eid = int(r["event_id"])
            fast = betsapi.get_event_score_fast(eid) or {}
            ts = str(fast.get("time_status") or "unknown")
            ss = fast.get("SS") or fast.get("ss") or "no score"
            
            print(f"  FI {eid}: {r['home_name']} vs {r['away_name']}")
            print(f"    DB status: {r['status']} | DB finals: {r['final_home']}-{r['final_away'] if r['final_away'] else 'None'}")
            print(f"    API time_status: {ts} | API score: {ss}")
            
            if ts == "1" and r['final_home'] is not None:
                print(f"    ⚠️  WARNING: Game is live (ts=1) but has finals in DB!")
            elif ts == "3" and r['final_home'] is None:
                print(f"    ⚠️  WARNING: Game is finished (ts=3) but no finals in DB!")
    else:
        print("No recent events to sample")
        
except Exception as e:
    print(f"Error sampling live games: {e}")

# 4. Check for result rows without proper finals
print("\n4️⃣ CHECKING: Result rows for unfinished games")
bad_results = q("""
    SELECT e.event_id, e.home_name, e.away_name, e.final_home, e.final_away, e.status
    FROM event e
    JOIN result r ON r.event_id = e.event_id
    WHERE e.status != 'finished' OR e.final_home IS NULL OR e.final_away IS NULL
""")

if not bad_results:
    print("✅ No result rows for unfinished games")
else:
    print(f"❌ Found {len(bad_results)} result rows for unfinished games:")
    for r in bad_results:
        print(f"  FI {r['event_id']}: {r['home_name']} vs {r['away_name']} | Status: {r['status']} | Finals: {r['final_home']}-{r['final_away']}")

print("\n" + "=" * 60)
print("🏁 VERIFICATION COMPLETE")
print("\nTo run individual checks:")
print("- python verify_fix.py")
print("- python -c \"from verify_fix import *; check_specific_game(181234567)\"")

def check_specific_game(event_id: int):
    """Check a specific game's status"""
    print(f"\n🔍 Detailed check for FI {event_id}:")
    
    # DB status
    db_info = q("SELECT * FROM event WHERE event_id = ?", (event_id,))
    if not db_info:
        print("❌ Game not found in database")
        return
    
    r = db_info[0]
    print(f"📊 DB Info:")
    print(f"  Teams: {r['home_name']} vs {r['away_name']}")
    print(f"  Start: {r['start_time_utc']}")
    print(f"  Status: {r['status']}")
    print(f"  Finals: {r['final_home']}-{r['final_away'] if r['final_away'] else 'None'}")
    
    # API status
    print(f"\n🌐 API Status:")
    fast = betsapi.get_event_score_fast(event_id) or {}
    result = betsapi.get_event_result(event_id) or {}
    
    ts = str(fast.get("time_status") or "unknown")
    ss = fast.get("SS") or fast.get("ss") or "no score"
    result_finals = f"{result.get('final_home')}-{result.get('final_away')}" if result.get('final_home') else "None"
    
    print(f"  time_status: {ts} ({'Not started' if ts=='0' else 'Live' if ts=='1' else 'Finished' if ts=='3' else 'Unknown'})")
    print(f"  Live score (SS): {ss}")
    print(f"  Result finals: {result_finals}")
    
    # Analysis
    print(f"\n📋 Analysis:")
    if ts == "3" and r['final_home'] is None:
        print("⚠️  Game finished but no finals in DB - may need backfill")
    elif ts in ("0", "1") and r['final_home'] is not None:
        print("❌ Game not finished but has finals in DB - THIS IS THE BUG!")
    elif ts == "3" and r['final_home'] is not None:
        print("✅ Game finished and has finals - correct")
    elif ts in ("0", "1") and r['final_home'] is None:
        print("✅ Game not finished and no finals - correct")
    else:
        print("🤔 Unclear status - may need manual review")

if __name__ == "__main__":
    pass  # All checks run automatically above