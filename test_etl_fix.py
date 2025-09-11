# test_etl_fix.py - Test that ETL no longer sets premature finals
import sqlite3
from datetime import datetime, timezone, timedelta

DB = "data/ebasketball.db"

def test_fix():
    print("Testing ETL Fix - Checking for Premature Finals")
    print("=" * 50)
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # 1. Check recent games that should NOT have finals yet
        print("\n1. Games that started recently (should NOT have finals):")
        recent_no_finals = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
            FROM event 
            WHERE start_time_utc >= datetime('now', '-25 minutes')
              AND start_time_utc <= datetime('now', '+5 minutes')
            ORDER BY start_time_utc DESC
        """).fetchall()
        
        if recent_no_finals:
            premature_count = 0
            for game in recent_no_finals:
                has_finals = (game['final_home'] is not None and game['final_away'] is not None)
                status = "❌ HAS FINALS" if has_finals else "✅ No finals"
                if has_finals:
                    premature_count += 1
                print(f"  FI {game['event_id']}: {game['home_name']} vs {game['away_name']}")
                print(f"    Start: {game['start_time_utc']} | Status: {game['status']} | {status}")
            
            if premature_count == 0:
                print(f"  ✅ All {len(recent_no_finals)} recent games correctly have no finals")
            else:
                print(f"  ❌ {premature_count} games have premature finals (fix not working)")
        else:
            print("  No recent games to check")
        
        # 2. Check older games that SHOULD have finals
        print("\n2. Older games (should have finals if finished):")
        older_games = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
            FROM event 
            WHERE start_time_utc >= datetime('now', '-2 hours')
              AND start_time_utc < datetime('now', '-35 minutes')
            ORDER BY start_time_utc DESC
            LIMIT 10
        """).fetchall()
        
        missing_finals = 0
        for game in older_games:
            has_finals = (game['final_home'] is not None and game['final_away'] is not None)
            if game['status'] == 'finished' and not has_finals:
                missing_finals += 1
                print(f"  ⚠️  FI {game['event_id']}: {game['home_name']} vs {game['away_name']}")
                print(f"    Status: finished but no finals (backfill needed)")
            elif has_finals:
                print(f"  ✅ FI {game['event_id']}: Has finals {game['final_home']}-{game['final_away']}")
        
        if missing_finals > 0:
            print(f"  📝 {missing_finals} finished games need backfill")
        
        # 3. Summary
        print(f"\n3. SUMMARY:")
        total_recent = len(recent_no_finals)
        premature = sum(1 for g in recent_no_finals if g['final_home'] is not None)
        
        print(f"  Recent games (<25 min): {total_recent}")
        print(f"  With premature finals: {premature}")
        
        if premature == 0:
            print(f"  🎉 ETL fix is working - no premature finals!")
            return True
        else:
            print(f"  ❌ ETL fix not working - still setting premature finals")
            return False

def monitor_live_games():
    """Monitor what happens to live games over time"""
    print("\n" + "=" * 50)
    print("LIVE GAME MONITORING")
    print("Run this periodically to watch live games...")
    
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        
        # Find games that should be live or recently started
        live_candidates = con.execute("""
            SELECT event_id, start_time_utc, home_name, away_name, status, final_home, final_away
            FROM event 
            WHERE start_time_utc >= datetime('now', '-30 minutes')
              AND start_time_utc <= datetime('now', '+5 minutes')
            ORDER BY start_time_utc DESC
        """).fetchall()
        
        now = datetime.now(timezone.utc)
        
        for game in live_candidates:
            try:
                start_time = datetime.fromisoformat(game['start_time_utc'])
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                
                minutes_since_start = (now - start_time).total_seconds() / 60
                
                print(f"\nFI {game['event_id']}: {game['home_name']} vs {game['away_name']}")
                print(f"  Started {minutes_since_start:.1f} minutes ago")
                print(f"  Status: {game['status']}")
                
                if game['final_home'] is not None:
                    print(f"  Finals: {game['final_home']}-{game['final_away']}")
                    if minutes_since_start < 20:
                        print(f"  ⚠️  Has finals but game is only {minutes_since_start:.1f} min old")
                else:
                    print(f"  Finals: None (correct for {minutes_since_start:.1f} min old game)")
                    
            except Exception as e:
                print(f"  Error processing game: {e}")

if __name__ == "__main__":
    is_working = test_fix()
    monitor_live_games()
    
    if is_working:
        print(f"\n✅ Test passed - ETL fix is working correctly!")
    else:
        print(f"\n❌ Test failed - check ETL implementation")
        
    print(f"\nTo continue monitoring:")
    print(f"python test_etl_fix.py")
    print(f"python improved_dashboard.py")