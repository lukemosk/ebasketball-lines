# test_live_parsing.py - Test the live data parsing with real data
from live_quarter_monitor import LiveQuarterMonitor
import json

def test_parsing():
    print("🧪 TESTING LIVE DATA PARSING")
    print("=" * 50)
    
    monitor = LiveQuarterMonitor()
    
    # Test with the live games we found
    test_games = [181160727, 181132336]
    
    for game_id in test_games:
        print(f"\nTesting FI {game_id}:")
        try:
            status = monitor.get_live_game_status(game_id)
            
            print(f"  Parsed status:")
            for key, value in status.items():
                if key != 'raw_data':  # Don't print the full raw data
                    print(f"    {key}: {value}")
            
            # Check if we'd detect quarter ending
            if 'quarter' in status and 'clock' in status:
                quarter, minutes, seconds = monitor.parse_game_clock(status['clock'])
                is_ending = monitor.is_quarter_ending(quarter, minutes, seconds)
                
                print(f"  Quarter ending detection:")
                print(f"    Parsed: Q{quarter} {minutes}:{seconds:02d}")
                print(f"    Is quarter ending? {is_ending}")
                
                if is_ending:
                    print(f"    🎯 WOULD CAPTURE Q{quarter} LINES!")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")

def test_api_live_detection():
    """Test the API live game detection"""
    print(f"\n🔍 TESTING API LIVE GAME DETECTION")
    print("=" * 50)
    
    monitor = LiveQuarterMonitor()
    live_games = monitor.get_live_games_from_api()
    
    print(f"Found {len(live_games)} live games from API:")
    for game in live_games:
        print(f"  FI {game['event_id']}: {game['home_name']} vs {game['away_name']}")

def test_monitor_cycle():
    """Test a single monitoring cycle"""
    print(f"\n🔄 TESTING MONITOR CYCLE")
    print("=" * 50)
    
    monitor = LiveQuarterMonitor()
    monitor.monitor_cycle()

if __name__ == "__main__":
    test_parsing()
    test_api_live_detection() 
    test_monitor_cycle()