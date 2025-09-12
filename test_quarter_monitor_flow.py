# test_quarter_monitor_flow.py - Test the complete quarter monitoring flow
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import time
import sqlite3
from datetime import datetime, timezone

def test_monitor_flow():
    """Test the complete quarter monitoring flow with a live game"""
    
    print("🧪 TESTING COMPLETE QUARTER MONITOR FLOW")
    print("=" * 60)
    
    # Import the fixed monitor
    try:
        from live_quarter_monitor import LiveQuarterMonitor
    except ImportError:
        print("❌ Cannot import LiveQuarterMonitor - make sure the fixed file exists")
        return
    
    # Create monitor instance
    monitor = LiveQuarterMonitor()
    
    # Run a few test cycles
    print("🔄 Running 3 test monitoring cycles...")
    
    for cycle in range(1, 4):
        print(f"\n--- CYCLE {cycle} ---")
        
        try:
            monitor.monitor_cycle()
            
            # Check database after each cycle
            check_database_updates()
            
            if cycle < 3:
                print("💤 Waiting 20 seconds before next cycle...")
                time.sleep(20)
                
        except Exception as e:
            print(f"❌ Error in cycle {cycle}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ TEST COMPLETED - 3 cycles finished")
    print_final_summary(monitor)

def check_database_updates():
    """Check what was added to the database"""
    try:
        with sqlite3.connect("data/ebasketball.db") as con:
            con.row_factory = sqlite3.Row
            
            # Check recent quarter_line entries
            recent_lines = con.execute("""
                SELECT event_id, quarter, market, line, captured_at_utc
                FROM quarter_line 
                WHERE captured_at_utc >= datetime('now', '-1 minute')
                ORDER BY captured_at_utc DESC
            """).fetchall()
            
            if recent_lines:
                print(f"  📊 {len(recent_lines)} new quarter lines captured:")
                for line in recent_lines:
                    print(f"    FI {line['event_id']} Q{line['quarter']} {line['market']}: {line['line']} @ {line['captured_at_utc']}")
            else:
                print(f"  📊 No new quarter lines captured in last minute")
                
    except Exception as e:
        print(f"  ❌ Database check error: {e}")

def print_final_summary(monitor):
    """Print final summary of the test"""
    print(f"\n📊 FINAL TEST SUMMARY")
    print("=" * 40)
    
    active_games = len(monitor.active_games)
    print(f"Active games tracked: {active_games}")
    
    total_captures = 0
    for event_id, game_state in monitor.active_games.items():
        captures = len(game_state.quarter_lines_captured)
        total_captures += captures
        
        if captures > 0:
            quarters = ", ".join(f"Q{q}" for q in sorted(game_state.quarter_lines_captured))
            print(f"  FI {event_id}: {captures}/3 quarters ({quarters})")
    
    print(f"Total quarter captures: {total_captures}")
    
    # Check database totals
    try:
        with sqlite3.connect("data/ebasketball.db") as con:
            total_db_lines = con.execute("SELECT COUNT(*) FROM quarter_line").fetchone()[0]
            recent_db_lines = con.execute("""
                SELECT COUNT(*) FROM quarter_line 
                WHERE captured_at_utc >= datetime('now', '-5 minutes')
            """).fetchone()[0]
            
            print(f"Total lines in database: {total_db_lines}")
            print(f"Lines captured in last 5 minutes: {recent_db_lines}")
            
    except Exception as e:
        print(f"Database summary error: {e}")
    
    print(f"\n💡 NEXT STEPS:")
    if total_captures > 0:
        print("✅ Quarter monitoring is working!")
        print("1. Run for longer periods during active eBasketball hours")
        print("2. Use: python quarter_analysis.py to analyze captured data")
    else:
        print("🤔 No quarter lines captured in this test")
        print("1. Make sure eBasketball games are live and near quarter endings")
        print("2. Try running during peak hours (9 AM - 11 PM EST)")
        print("3. Check that odds are available for the live games")

def quick_live_game_status():
    """Show current status of live games"""
    print(f"\n🎮 CURRENT LIVE GAME STATUS")
    print("-" * 40)
    
    try:
        import requests
        import os
        
        token = os.getenv("BETSAPI_KEY")
        url = f"https://api.b365api.com/v1/bet365/inplay_filter?sport_id=18&token={token}"
        
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            print("❌ Cannot get live games")
            return
        
        data = response.json()
        results = data.get('results', [])
        
        ebasketball_games = []
        for game in results:
            if not isinstance(game, dict):
                continue
                
            league = game.get('league', {})
            if isinstance(league, dict):
                league_name = league.get('name', '')
            else:
                league_name = str(league)
            
            league_name = league_name.lower()
            
            if ('ebasketball h2h gg league' in league_name and 
                '4x5mins' in league_name and 
                'battle' not in league_name):
                
                ebasketball_games.append(game)
        
        if not ebasketball_games:
            print("📭 No live eBasketball games right now")
            print("   Best times to test: 9 AM - 11 PM EST")
            return
        
        print(f"🎯 Found {len(ebasketball_games)} live eBasketball games:")
        
        for game in ebasketball_games:
            home = game.get('home', {})
            away = game.get('away', {})
            
            if isinstance(home, dict):
                home_name = home.get('name', 'Unknown')
            else:
                home_name = str(home)
            
            if isinstance(away, dict):
                away_name = away.get('name', 'Unknown')  
            else:
                away_name = str(away)
            
            score = game.get('ss', 'N/A')
            time_status = game.get('time_status', 'N/A')
            
            print(f"  FI {game.get('id')}: {home_name} vs {away_name}")
            print(f"    Score: {score} | Status: {time_status}")
        
        print(f"\n💡 These games are good candidates for quarter monitoring!")
        
    except Exception as e:
        print(f"❌ Error checking live games: {e}")

def main():
    quick_live_game_status()
    
    proceed = input(f"\n🔄 Run quarter monitor flow test? [y/N]: ")
    if proceed.lower() == 'y':
        test_monitor_flow()
    else:
        print("Test cancelled")

if __name__ == "__main__":
    main()
    