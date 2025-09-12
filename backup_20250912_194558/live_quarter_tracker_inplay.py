# live_quarter_tracker_inplay.py
"""
Live Quarter Data Tracker for eBasketball using /v1/bet365/inplay endpoint
Captures spread/total lines at quarter breaks from real-time live data
"""

import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv, find_dotenv

# Load environment
load_dotenv(find_dotenv())

# Import your existing modules
from src.betsapi import _get_results

# Configuration
DB_PATH = "data/ebasketball.db"
BOOKMAKER_ID = "bet365"
SPORT_ID_BASKETBALL = 18
QUARTER_LENGTH_SECONDS = 300  # 5 minutes per quarter
CAPTURE_THRESHOLD_SECONDS = 10  # Capture when ≤10 seconds remain

# Target leagues
TARGET_LEAGUE_NAMES = {
    "ebasketball h2h gg league - 4x5mins",
    "ebasketball live arena - 4x5mins"
}

class LiveQuarterTrackerInplay:
    def __init__(self):
        self.db_path = DB_PATH
        self.bookmaker_id = BOOKMAKER_ID
        self.init_database()
        print(f"Initialized quarter tracker using /v1/bet365/inplay endpoint")
    
    def init_database(self):
        """Ensure quarter_line table exists"""
        with sqlite3.connect(self.db_path) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS quarter_line (
                    event_id INTEGER,
                    bookmaker_id TEXT,
                    quarter INTEGER,
                    market TEXT,
                    line REAL,
                    captured_at_utc TEXT,
                    game_time_remaining INTEGER,
                    home_score INTEGER,
                    away_score INTEGER,
                    PRIMARY KEY (event_id, bookmaker_id, quarter, market),
                    FOREIGN KEY (event_id) REFERENCES event(event_id)
                )
            """)
            con.commit()
    
    def get_live_basketball_games(self) -> List[Dict[str, Any]]:
        """Get all live basketball games from inplay endpoint"""
        try:
            print("Fetching live basketball games from /v1/bet365/inplay...")
            
            # Call the inplay endpoint with basketball filter
            results = _get_results("/v1/bet365/inplay", sport_id=SPORT_ID_BASKETBALL)
            
            if not results:
                print("No results from inplay endpoint")
                return []
            
            # Filter for eBasketball leagues and extract game data
            live_games = []
            for game_data in results:
                if not isinstance(game_data, list):
                    continue
                    
                # Find the EV (event) node in the data structure
                ev_node = None
                for item in game_data:
                    if isinstance(item, dict) and item.get("type") == "EV":
                        ev_node = item
                        break
                
                if not ev_node:
                    continue
                
                # Extract league and team info
                league_name = str(ev_node.get("CT", "")).lower()
                game_name = str(ev_node.get("NA", "")).lower()
                
                # Check if this is an eBasketball game
                if any(target in league_name for target in TARGET_LEAGUE_NAMES):
                    # Parse team names from game name
                    if " v " in game_name:
                        teams = game_name.split(" v ")
                        home_name = teams[0].strip()
                        away_name = teams[1].strip() if len(teams) > 1 else "Unknown"
                    else:
                        home_name = game_name
                        away_name = "Unknown"
                    
                    # Extract FI (fixture ID) from the data
                    fi = ev_node.get("C3", "")  # C3 appears to be the fixture ID
                    
                    if fi:
                        live_games.append({
                            'fi': fi,
                            'home': home_name,
                            'away': away_name,
                            'league': league_name,
                            'ev_data': ev_node  # Store the full EV node for timing analysis
                        })
            
            print(f"Found {len(live_games)} live eBasketball games")
            return live_games
            
        except Exception as e:
            print(f"Error getting live basketball games: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def parse_game_timing_from_inplay(self, ev_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse game timing from inplay EV node
        Based on the structure we saw: TM, TS, TT, MD, etc.
        """
        try:
            # Extract timing fields
            minutes = int(ev_data.get("TM", 0))
            seconds = int(ev_data.get("TS", 0)) 
            time_running = int(ev_data.get("TT", 0)) == 1
            period_indicator = ev_data.get("MD", "0")  # MD might be quarter indicator
            last_update = ev_data.get("TU", "")
            
            # Parse scores
            score_str = ev_data.get("SS", "0-0")
            try:
                scores = score_str.split("-")
                home_score = int(scores[0]) if len(scores) >= 1 else 0
                away_score = int(scores[1]) if len(scores) >= 2 else 0
            except:
                home_score = away_score = 0
            
            print(f"    Timing data: TM={minutes}, TS={seconds}, TT={time_running}, MD={period_indicator}")
            print(f"    Score: {score_str} -> {home_score}-{away_score}")
            print(f"    Last update: {last_update}")
            
            # Try to determine quarter from various indicators
            quarter = 0
            
            # Method 1: Check if MD directly indicates quarter
            if period_indicator in ["1", "2", "3", "4"]:
                quarter = int(period_indicator)
                print(f"    Quarter from MD: {quarter}")
            
            # Method 2: Infer from total elapsed time
            if quarter == 0:
                total_elapsed = minutes * 60 + seconds
                if total_elapsed <= 300:  # 0-5 minutes
                    quarter = 1
                elif total_elapsed <= 600:  # 5-10 minutes  
                    quarter = 2
                elif total_elapsed <= 900:  # 10-15 minutes
                    quarter = 3
                elif total_elapsed <= 1200:  # 15-20 minutes
                    quarter = 4
                else:
                    quarter = 5  # Overtime or beyond
                
                print(f"    Quarter inferred from time ({total_elapsed}s): {quarter}")
            
            # Calculate remaining seconds in current quarter
            if quarter <= 4:
                quarter_elapsed = ((quarter - 1) * 300) + (minutes * 60 + seconds)
                quarter_start = (quarter - 1) * 300
                seconds_into_quarter = quarter_elapsed - quarter_start
                remaining_seconds = QUARTER_LENGTH_SECONDS - seconds_into_quarter
            else:
                remaining_seconds = 0  # Overtime/unknown
            
            return {
                'quarter': quarter,
                'minutes': minutes,
                'seconds': seconds,
                'time_running': time_running,
                'remaining_seconds': remaining_seconds,
                'home_score': home_score,
                'away_score': away_score,
                'last_update': last_update,
                'period_indicator': period_indicator
            }
            
        except Exception as e:
            print(f"  Error parsing timing: {e}")
            return None
    
    def extract_lines_from_inplay_data(self, game_data: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
        """
        Extract spread and total lines from inplay data structure
        Look for MA (market) and PA (participant) nodes
        """
        lines = {'spread': None, 'total': None}
        
        try:
            for item in game_data:
                if not isinstance(item, dict):
                    continue
                
                # Look for market areas (MA) that might contain spreads/totals
                if item.get("type") == "MA":
                    market_name = str(item.get("NA", "")).lower()
                    
                    # Check for handicap (spread) markets
                    if "handicap" in market_name or "spread" in market_name:
                        # Look for subsequent PA (participant) nodes
                        continue
                    
                    # Check for total markets
                    if "total" in market_name or "over" in market_name or "under" in market_name:
                        continue
                
                # Look for participant areas (PA) with line values
                elif item.get("type") == "PA":
                    participant_name = str(item.get("NA", "")).lower()
                    handicap = item.get("HA", "")
                    
                    # Extract spread lines
                    if handicap and ("+" in str(handicap) or "-" in str(handicap)):
                        try:
                            line_value = float(str(handicap).replace("+", "").replace("-", ""))
                            if 0.5 <= line_value <= 50:  # Reasonable spread range
                                lines['spread'] = self.quantize_to_half(line_value)
                        except:
                            pass
                    
                    # Extract total lines
                    elif handicap and str(handicap).replace(".", "").isdigit():
                        try:
                            line_value = float(handicap)
                            if 50 <= line_value <= 300:  # Reasonable total range for basketball
                                lines['total'] = self.quantize_to_half(line_value)
                        except:
                            pass
            
            print(f"    Extracted lines: spread={lines['spread']}, total={lines['total']}")
            return lines
            
        except Exception as e:
            print(f"  Error extracting lines: {e}")
            return lines
    
    def quantize_to_half(self, value: float) -> float:
        """Quantize to nearest 0.5"""
        return round(value * 2) / 2
    
    def should_capture_quarter_end(self, timing: Dict[str, Any]) -> bool:
        """Determine if we should capture lines at quarter end"""
        remaining = timing['remaining_seconds']
        time_running = timing['time_running']
        quarter = timing['quarter']
        
        # Only capture for quarters 1-4
        if quarter < 1 or quarter > 4:
            return False
        
        # Capture if remaining time is low and clock is running
        if remaining <= CAPTURE_THRESHOLD_SECONDS and time_running:
            return True
            
        return False
    
    def is_already_captured(self, event_id: int, quarter: int) -> bool:
        """Check if we've already captured this quarter for this event"""
        with sqlite3.connect(self.db_path) as con:
            result = con.execute("""
                SELECT 1 FROM quarter_line 
                WHERE event_id = ? AND quarter = ?
                LIMIT 1
            """, (event_id, quarter)).fetchone()
            return result is not None
    
    def get_event_id_from_fi(self, fi: str) -> Optional[int]:
        """Get our internal event_id from BetsAPI FI"""
        try:
            # Your database shows FI = event_id directly
            event_id = int(fi)
            
            print(f"    Checking if FI {fi} exists in database as event_id...")
            
            # Verify it exists in our database
            with sqlite3.connect(self.db_path) as con:
                result = con.execute("""
                    SELECT event_id FROM event WHERE event_id = ?
                """, (event_id,)).fetchone()
                
                if result:
                    print(f"    ✅ Found event_id {event_id} in database")
                    return event_id
                else:
                    print(f"    ❌ Event_id {event_id} NOT found in database")
                    
                    # Try searching by team names instead as fallback
                    print(f"    Attempting team name matching as fallback...")
                    return None
                
        except (ValueError, TypeError):
            print(f"    ❌ Could not convert FI '{fi}' to integer")
            return None
    
    def store_quarter_lines(self, event_id: int, quarter: int, lines: Dict[str, Optional[float]], 
                           timing: Dict[str, Any]) -> None:
        """Store captured quarter lines to database"""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with sqlite3.connect(self.db_path) as con:
                for market, line in lines.items():
                    if line is not None:
                        con.execute("""
                            INSERT OR REPLACE INTO quarter_line 
                            (event_id, bookmaker_id, quarter, market, line, captured_at_utc, 
                             game_time_remaining, home_score, away_score)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            event_id, self.bookmaker_id, quarter, market, line, now_utc,
                            timing['remaining_seconds'], timing['home_score'], timing['away_score']
                        ))
                con.commit()
                print(f"    Successfully stored quarter lines to database")
        except Exception as e:
            print(f"    Error storing quarter lines: {e}")
            # Continue anyway - we can still track without database storage
    
    def process_live_games(self) -> None:
        """Main processing loop for live games"""
        live_games = self.get_live_basketball_games()
        
        if not live_games:
            print("No live eBasketball games found")
            return
        
        print(f"Processing {len(live_games)} live games...")
        
        games_found = len(live_games)
        games_processed = 0
        
        print(f"\nAttempting to process {games_found} live games...")
        
        for game in live_games:
            fi = game['fi']
            home = game['home']
            away = game['away']
            
            print(f"\nProcessing FI {fi}: {home} vs {away}")
            games_processed += 1
            
            try:
                # Get our internal event_id (or use FI directly for H2H GG games)
                event_id = self.get_event_id_from_fi(fi)
                if not event_id:
                    # For H2H GG games, use the FI directly since they might not be in database
                    print(f"  FI {fi} not in database - using FI as event_id for H2H GG tracking")
                    event_id = int(fi)  # Use the API FI as event_id
                
                print(f"  Mapped to event_id: {event_id}")
                
                # Parse timing from the live data we already have
                timing = self.parse_game_timing_from_inplay(game['ev_data'])
                if not timing:
                    print(f"  Could not parse timing data")
                    continue
                    
                quarter = timing['quarter']
                if quarter < 1 or quarter > 4:
                    print(f"  Not in trackable quarter (quarter: {quarter})")
                    continue
                
                print(f"  Q{quarter}: {timing['remaining_seconds']}s remaining, "
                      f"score: {timing['home_score']}-{timing['away_score']}")
                
                # Skip if already captured
                if self.is_already_captured(event_id, quarter):
                    print(f"  Q{quarter} already captured, skipping")
                    continue
                
                # Check if we should capture
                if not self.should_capture_quarter_end(timing):
                    print(f"  Not at quarter end ({timing['remaining_seconds']}s remaining)")
                    continue
                
                # We need to get detailed market data for lines
                # The inplay data might not have detailed betting markets
                print(f"  At quarter end! Getting detailed market data...")
                
                # Fall back to the detailed event endpoint for market data
                try:
                    detailed_results = _get_results("/v1/bet365/event", FI=fi, stats=1)
                    if detailed_results:
                        lines = self.extract_game_lines_from_detailed(detailed_results[0])
                    else:
                        lines = {'spread': None, 'total': None}
                        print(f"  No detailed market data available")
                except Exception as e:
                    print(f"  Error getting detailed market data: {e}")
                    lines = {'spread': None, 'total': None}
                
                # Store if we got valid lines
                if lines['spread'] is not None or lines['total'] is not None:
                    self.store_quarter_lines(event_id, quarter, lines, timing)
                    
                    print(f"  ✅ Captured Q{quarter}: spread={lines['spread']}, "
                          f"total={lines['total']}, {timing['remaining_seconds']}s remaining")
                else:
                    print(f"  No valid betting lines found at quarter end")
                
            except Exception as e:
                print(f"  Error processing FI {fi}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    def extract_game_lines_from_detailed(self, game_data: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """Extract lines from detailed /v1/bet365/event response (fallback method)"""
        lines = {'spread': None, 'total': None}
        
        try:
            # This uses your existing extraction logic from the original tracker
            def find_game_lines(data):
                if isinstance(data, dict):
                    if (data.get("type") == "MA" and 
                        "handicap" in str(data.get("NA", "")).lower()):
                        return "spread"
                    elif (data.get("type") == "MA" and 
                          "total" in str(data.get("NA", "")).lower()):
                        return "total"
                    
                    for value in data.values():
                        result = find_game_lines(value)
                        if result:
                            return result
                            
                elif isinstance(data, list):
                    for item in data:
                        result = find_game_lines(item)
                        if result:
                            return result
                return None
            
            # Extract odds from participants
            def extract_odds_from_participants(data, lines_dict):
                if isinstance(data, dict):
                    if data.get("type") == "PA":
                        name = str(data.get("NA", "")).lower()
                        handicap = data.get("HA", "")
                        
                        # Look for spread
                        if handicap and ("+" in str(handicap) or "-" in str(handicap)):
                            try:
                                line_val = float(str(handicap).replace("+", "").replace("-", ""))
                                if 0.5 <= line_val <= 50:
                                    lines_dict['spread'] = self.quantize_to_half(line_val)
                            except:
                                pass
                        
                        # Look for total
                        elif handicap and str(handicap).replace(".", "").isdigit():
                            try:
                                line_val = float(handicap)
                                if 50 <= line_val <= 300:
                                    lines_dict['total'] = self.quantize_to_half(line_val)
                            except:
                                pass
                    
                    for value in data.values():
                        extract_odds_from_participants(value, lines_dict)
                        
                elif isinstance(data, list):
                    for item in data:
                        extract_odds_from_participants(item, lines_dict)
            
            extract_odds_from_participants(game_data, lines)
            return lines
            
        except Exception as e:
            print(f"    Error in detailed extraction: {e}")
            return lines
    
    def run_continuous(self, poll_seconds: int = 20):
        """Run continuous monitoring with faster polling"""
        print(f"Starting live quarter tracker using inplay endpoint (polling every {poll_seconds}s)")
        
        while True:
            try:
                print(f"\n{datetime.now().strftime('%H:%M:%S')} - Checking live games...")
                self.process_live_games()
                time.sleep(poll_seconds)
                
            except KeyboardInterrupt:
                print("Stopping live quarter tracker...")
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(poll_seconds)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Live Quarter Data Tracker (Inplay)")
    parser.add_argument("--poll", type=int, default=20, 
                       help="Polling interval in seconds (default: 20)")
    parser.add_argument("--once", action="store_true", 
                       help="Run once instead of continuously")
    
    args = parser.parse_args()
    
    tracker = LiveQuarterTrackerInplay()
    
    if args.once:
        tracker.process_live_games()
    else:
        tracker.run_continuous(args.poll)


if __name__ == "__main__":
    main()