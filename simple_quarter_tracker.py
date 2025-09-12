# simple_quarter_tracker.py
"""
Simple quarter tracker using the proven working logic from minimal test
"""

import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from src.betsapi import _get_results

TARGET_LEAGUE_PATTERNS = ["ebasketball h2h gg league"]
QUARTER_LENGTH_SECONDS = 300
CAPTURE_THRESHOLD_SECONDS = 10

def get_live_games():
    """Get live eBasketball H2H GG games - using proven working logic"""
    
    print("Fetching live eBasketball games...")
    
    try:
        results = _get_results("/v1/bet365/inplay")
        
        if not results:
            print("No results from inplay endpoint")
            return []
        
        live_games = []
        
        for result_group in results:
            if not isinstance(result_group, list):
                continue
            
            current_league = None
            
            for item in result_group:
                if not isinstance(item, dict):
                    continue
                
                item_type = item.get("type")
                
                if item_type == "CT":
                    current_league = item.get("NA", "").lower()
                    continue
                
                elif item_type == "EV":
                    if not current_league:
                        continue
                    
                    game_name = str(item.get("NA", "")).lower()
                    
                    # Check for eBasketball H2H GG League
                    is_ebasketball = any(pattern in current_league for pattern in TARGET_LEAGUE_PATTERNS)
                    
                    if is_ebasketball:
                        print(f"Found: {game_name} in {current_league}")
                        
                        # Get FI - fix the selection logic
                        c3 = item.get("C3", "")
                        c2 = item.get("C2", "")
                        id_field = item.get("ID", "")
                        
                        # Use C2 if C3 is "0" or empty
                        if c3 and c3 != "0":
                            fi = c3
                        elif c2 and c2 != "0":
                            fi = c2
                        elif id_field and id_field != "0":
                            fi = id_field
                        else:
                            fi = ""
                        
                        print(f"  FI values: C3={c3}, C2={c2}, ID={id_field}, selected={fi}")
                        
                        if fi and fi != "0":
                            # Parse teams
                            if " @ " in game_name:
                                teams = game_name.split(" @ ")
                                away_name = teams[0].strip()
                                home_name = teams[1].strip() if len(teams) > 1 else "Unknown"
                            else:
                                home_name = game_name
                                away_name = "Unknown"
                            
                            live_games.append({
                                'fi': fi,
                                'home': home_name,
                                'away': away_name,
                                'ev_data': item
                            })
                            
                            print(f"  Added: FI {fi}, {home_name} vs {away_name}")
        
        # Remove duplicates by FI
        unique_games = {}
        for game in live_games:
            unique_games[game['fi']] = game
        
        result = list(unique_games.values())
        print(f"Found {len(result)} unique live eBasketball games")
        return result
        
    except Exception as e:
        print(f"Error getting live games: {e}")
        return []

def parse_timing(ev_data):
    """Parse timing from EV data"""
    try:
        minutes = int(ev_data.get("TM", 0))
        seconds = int(ev_data.get("TS", 0))
        time_running = int(ev_data.get("TT", 0)) == 1
        
        # Parse score
        score_str = ev_data.get("SS", "0-0")
        try:
            scores = score_str.split("-")
            home_score = int(scores[0]) if len(scores) >= 1 else 0
            away_score = int(scores[1]) if len(scores) >= 2 else 0
        except:
            home_score = away_score = 0
        
        # Determine quarter
        total_elapsed = minutes * 60 + seconds
        if total_elapsed <= 300:
            quarter = 1
        elif total_elapsed <= 600:
            quarter = 2
        elif total_elapsed <= 900:
            quarter = 3
        elif total_elapsed <= 1200:
            quarter = 4
        else:
            quarter = 5  # OT
        
        # Calculate remaining in quarter
        if quarter <= 4:
            quarter_start = (quarter - 1) * 300
            seconds_into_quarter = total_elapsed - quarter_start
            remaining_seconds = QUARTER_LENGTH_SECONDS - seconds_into_quarter
        else:
            remaining_seconds = 0
        
        return {
            'quarter': quarter,
            'minutes': minutes,
            'seconds': seconds,
            'time_running': time_running,
            'remaining_seconds': remaining_seconds,
            'home_score': home_score,
            'away_score': away_score,
            'total_elapsed': total_elapsed
        }
        
    except Exception as e:
        print(f"Error parsing timing: {e}")
        return None

def track_games_once():
    """Track games once"""
    
    live_games = get_live_games()
    
    if not live_games:
        print("No live games to track")
        return
    
    print(f"\nTracking {len(live_games)} games:")
    
    for game in live_games:
        fi = game['fi']
        home = game['home']
        away = game['away']
        
        print(f"\nFI {fi}: {home} vs {away}")
        
        print(f"  Raw EV data - CP: '{game['ev_data'].get('CP')}', MD: '{game['ev_data'].get('MD')}', TM: {game['ev_data'].get('TM')}, TS: {game['ev_data'].get('TS')}")
        
        timing = parse_timing(game['ev_data'])
        if not timing:
            print("  Could not parse timing")
            continue
        
        print(f"  Q{timing['quarter']}: {timing['minutes']}:{timing['seconds']:02d}")
        if 'current_period' in timing:
            print(f"  API fields: CP='{timing['current_period']}', MD='{timing['match_details']}'")
        print(f"  Score: {timing['home_score']}-{timing['away_score']}")
        print(f"  Time running: {timing['time_running']}")
        print(f"  Remaining in quarter: {timing['remaining_seconds']}s")
        
        # Check if at quarter end
        if timing['remaining_seconds'] <= CAPTURE_THRESHOLD_SECONDS and timing['time_running']:
            print(f"  *** AT QUARTER END - WOULD CAPTURE LINES ***")
        
        # Show quarter progression
        if timing['quarter'] <= 4:
            progress = ((timing['quarter'] - 1) * 300 + (timing['minutes'] * 60 + timing['seconds'])) / 1200 * 100
            print(f"  Game progress: {progress:.1f}%")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple Quarter Tracker")
    parser.add_argument("--once", action="store_true", help="Run once")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    
    args = parser.parse_args()
    
    if args.continuous:
        print("Running continuous tracking (Ctrl+C to stop)...")
        while True:
            try:
                track_games_once()
                time.sleep(20)
            except KeyboardInterrupt:
                print("Stopping...")
                break
    else:
        track_games_once()

if __name__ == "__main__":
    main()