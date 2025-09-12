# live_quarter_monitor.py - Monitor live games for quarter endings and capture lines
from __future__ import annotations
import time
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from src import betsapi
from src.config import CONF

DB_PATH = "data/ebasketball.db"
POLL_INTERVAL = 10  # Check every 10 seconds during live games
QUARTER_BUFFER = 15  # Seconds buffer around quarter end times

@dataclass
class GameState:
    event_id: int
    quarter: int
    time_remaining: str
    score: str
    last_poll: datetime
    quarter_lines_captured: set  # Track which quarters we've captured

class LiveQuarterMonitor:
    def __init__(self):
        self.active_games: Dict[int, GameState] = {}
        self.db_path = DB_PATH
        
    def get_live_games_from_api(self) -> List[Dict]:
        """Get live eBasketball games directly from API using correct endpoint"""
        try:
            import requests
            import os
            
            token = os.getenv("BETSAPI_KEY")
            url = f"https://api.b365api.com/v1/bet365/inplay_filter?sport_id=18&token={token}"
            
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = data.get('results', [])
            
            live_games = []
            for game in results:
                if not isinstance(game, dict):
                    continue
                    
                # Extract league name
                league = game.get('league', {})
                if isinstance(league, dict):
                    league_name = league.get('name', '')
                else:
                    league_name = str(league)
                
                league_name = league_name.lower()
                
                # Check if it's eBasketball
                if any(keyword in league_name for keyword in ['ebasketball h2h gg league', 'h2h gg league']):
                    home_name = game.get('home', {})
                    away_name = game.get('away', {})
                    
                    if isinstance(home_name, dict):
                        home_name = home_name.get('name', 'Unknown')
                    if isinstance(away_name, dict):
                        away_name = away_name.get('name', 'Unknown')
                    
                    live_games.append({
                        'event_id': game.get('id'),  # FI number
                        'home_name': str(home_name),
                        'away_name': str(away_name),
                        'league_name': league_name
                    })
            
            return live_games
            
        except Exception as e:
            print(f"Error getting live games from API: {e}")
            return []
        
    def get_live_games(self) -> List[Dict]:
        """Get games that should be live based on start time"""
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            # Games that started 0-30 minutes ago (should be live or recently finished)
            return con.execute("""
                SELECT event_id, home_name, away_name, start_time_utc
                FROM event 
                WHERE start_time_utc >= datetime('now', '-30 minutes')
                  AND start_time_utc <= datetime('now', '+2 minutes')
                  AND (final_home IS NULL OR final_away IS NULL)
                ORDER BY start_time_utc ASC
            """).fetchall()
    
    def parse_game_clock(self, clock_str: str) -> Tuple[int, int, int]:
        """
        Parse game clock string to extract quarter and time remaining
        Expected formats: "2Q 2:30", "3Q 0:05", "4Q 0:00", etc.
        Returns: (quarter, minutes_remaining, seconds_remaining)
        """
        if not clock_str or not isinstance(clock_str, str):
            return 0, 0, 0
            
        try:
            # Remove extra spaces and convert to uppercase
            clock = clock_str.strip().upper()
            
            # Extract quarter
            if 'Q' in clock:
                quarter_part = clock.split('Q')[0].strip()
                quarter = int(quarter_part) if quarter_part.isdigit() else 0
                time_part = clock.split('Q')[1].strip() if 'Q' in clock else ""
            else:
                quarter = 0
                time_part = clock
            
            # Extract time remaining (format: "M:SS")
            if ':' in time_part:
                time_parts = time_part.split(':')
                minutes = int(time_parts[0]) if time_parts[0].isdigit() else 0
                seconds = int(time_parts[1]) if len(time_parts) > 1 and time_parts[1].isdigit() else 0
            else:
                minutes = seconds = 0
                
            return quarter, minutes, seconds
        except Exception:
            return 0, 0, 0
    
    def is_quarter_ending(self, quarter: int, minutes: int, seconds: int) -> bool:
        """Check if we're at or near a quarter ending"""
        if quarter not in [1, 2, 3]:  # Only monitor first 3 quarters
            return False
            
        # Consider it quarter ending if 5 seconds or less remaining
        total_seconds = minutes * 60 + seconds
        return total_seconds <= 5
    
    def get_live_game_status(self, event_id: int) -> Dict:
        """Get detailed live status for a game using correct API endpoint"""
        try:
            import requests
            import os
            
            token = os.getenv("BETSAPI_KEY")
            url = f"https://api.b365api.com/v1/bet365/event?FI={event_id}&token={token}&stats=1"
            
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                return {}
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                return {}
            
            # Find the main event data (type='EV')
            event_data = None
            if isinstance(results, list):
                for item in results:
                    if isinstance(item, dict) and item.get('type') == 'EV':
                        event_data = item
                        break
            
            if not event_data:
                return {}
            
            # Extract fields based on API documentation
            score = event_data.get('SS', '')  # SHORT_SCORE
            time_minutes = event_data.get('TM', 0)  # TMR_MINS (elapsed)
            time_seconds = event_data.get('TS', 0)  # TMR_SECS (elapsed) 
            timer_ticking = event_data.get('TT', 0)  # TMR_TICKING
            
            # Convert to integers
            try:
                minutes_elapsed = int(time_minutes) if time_minutes else 0
                seconds_elapsed = int(time_seconds) if time_seconds else 0
                is_ticking = str(timer_ticking) == '1'
            except:
                minutes_elapsed = seconds_elapsed = 0
                is_ticking = False
            
            # Calculate quarter and remaining time
            total_elapsed = minutes_elapsed * 60 + seconds_elapsed
            
            if total_elapsed < 300:  # Q1: 0-5 minutes
                quarter = 1
                remaining = 300 - total_elapsed
            elif total_elapsed < 600:  # Q2: 5-10 minutes
                quarter = 2  
                remaining = 600 - total_elapsed
            elif total_elapsed < 900:  # Q3: 10-15 minutes
                quarter = 3
                remaining = 900 - total_elapsed
            elif total_elapsed < 1200:  # Q4: 15-20 minutes
                quarter = 4
                remaining = 1200 - total_elapsed
            else:
                quarter = 4
                remaining = 0
            
            remaining_minutes = remaining // 60
            remaining_seconds = remaining % 60
            
            return {
                'time_status': str(timer_ticking),
                'score': str(score),
                'clock': f"{remaining_minutes}:{remaining_seconds:02d}",
                'quarter': quarter,
                'minutes_remaining': remaining_minutes,
                'seconds_remaining': remaining_seconds,
                'is_live': is_ticking,
                'total_elapsed': total_elapsed
            }
            
        except Exception as e:
            print(f"Error getting live status for {event_id}: {e}")
            return {}
    
    def capture_quarter_lines(self, event_id: int, quarter: int) -> bool:
        """Capture the spread lines at quarter end"""
        try:
            # Get current prematch/live odds
            odds_data = betsapi.get_odds_openers(event_id)
            if not odds_data:
                print(f"No odds data available for FI {event_id} at Q{quarter} end")
                return False
            
            spread_line = odds_data.get("spread")
            total_line = odds_data.get("total")
            captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            
            # Store in quarter_line table
            with sqlite3.connect(self.db_path) as con:
                if spread_line is not None:
                    con.execute("""
                        INSERT OR REPLACE INTO quarter_line 
                        (event_id, bookmaker_id, market, quarter, line, captured_at_utc)
                        VALUES (?, ?, 'spread', ?, ?, ?)
                    """, (event_id, CONF["book"], quarter, float(spread_line), captured_at))
                
                if total_line is not None:
                    con.execute("""
                        INSERT OR REPLACE INTO quarter_line 
                        (event_id, bookmaker_id, market, quarter, line, captured_at_utc)
                        VALUES (?, ?, 'total', ?, ?, ?)
                    """, (event_id, CONF["book"], quarter, float(total_line), captured_at))
                
                con.commit()
            
            print(f"✅ Captured Q{quarter} lines for FI {event_id}: spread={spread_line}, total={total_line}")
            return True
            
        except Exception as e:
            print(f"❌ Error capturing Q{quarter} lines for FI {event_id}: {e}")
            return False
    
    def update_game_state(self, event_id: int, live_status: Dict):
        """Update the state of a live game"""
        try:
            # Extract quarter and timing from live status
            quarter = live_status.get('quarter', 0)
            minutes = live_status.get('minutes_remaining', 0) 
            seconds = live_status.get('seconds_remaining', 0)
            
            # Get or create game state
            if event_id not in self.active_games:
                self.active_games[event_id] = GameState(
                    event_id=event_id,
                    quarter=quarter,
                    time_remaining=f"{minutes}:{seconds:02d}",
                    score=live_status.get('score', ''),
                    last_poll=datetime.now(timezone.utc),
                    quarter_lines_captured=set()
                )
            
            game_state = self.active_games[event_id]
            
            # Check if we're at a quarter ending we haven't captured yet
            if (self.is_quarter_ending(quarter, minutes, seconds) and 
                quarter not in game_state.quarter_lines_captured and
                quarter in [1, 2, 3]):
                
                print(f"🎯 Quarter {quarter} ending detected for FI {event_id}: {minutes}:{seconds:02d} remaining")
                
                if self.capture_quarter_lines(event_id, quarter):
                    game_state.quarter_lines_captured.add(quarter)
            
            # Update game state
            game_state.quarter = quarter
            game_state.time_remaining = f"{minutes}:{seconds:02d}"
            game_state.score = live_status.get('score', '')
            game_state.last_poll = datetime.now(timezone.utc)
            
        except Exception as e:
            print(f"Error updating game state for {event_id}: {e}")
    
    def cleanup_finished_games(self):
        """Remove games that are no longer live from tracking"""
        to_remove = []
        
        for event_id, game_state in self.active_games.items():
            # Remove games we haven't polled in 5 minutes (likely finished)
            if (datetime.now(timezone.utc) - game_state.last_poll).seconds > 300:
                to_remove.append(event_id)
        
        for event_id in to_remove:
            print(f"🏁 Stopped monitoring FI {event_id} (no longer live)")
            del self.active_games[event_id]
    
    def monitor_cycle(self):
        """Run one monitoring cycle"""
        # Get live games directly from API instead of database
        live_games = self.get_live_games_from_api()
        
        if not live_games:
            print("No live eBasketball games found in API")
            return
        
        print(f"📡 Found {len(live_games)} live eBasketball games in API...")
        
        for game in live_games:
            event_id = int(game['event_id'])
            
            try:
                live_status = self.get_live_game_status(event_id)
                
                if live_status.get('is_live'):
                    if event_id not in self.active_games:
                        print(f"🔴 Started monitoring FI {event_id}: {game['home_name']} vs {game['away_name']}")
                    
                    self.update_game_state(event_id, live_status)
                    
                    # Debug info
                    game_state = self.active_games.get(event_id)
                    if game_state:
                        captured = len(game_state.quarter_lines_captured)
                        print(f"  FI {event_id}: Q{game_state.quarter} {game_state.time_remaining} | "
                              f"Score: {game_state.score} | Captured: {captured}/3 quarters")
                        
                elif event_id in self.active_games:
                    print(f"🏁 FI {event_id} no longer live")
                    del self.active_games[event_id]
                    
            except Exception as e:
                print(f"Error monitoring FI {event_id}: {e}")
        
        # Cleanup
        self.cleanup_finished_games()
        
        # Status summary
        if self.active_games:
            print(f"📊 Currently monitoring {len(self.active_games)} live games")
    
    def run(self, cycles: Optional[int] = None):
        """Run the live monitor"""
        print("🏀 Starting Live Quarter Monitor")
        print("=" * 50)
        
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                print(f"\n[Cycle {cycle_count}] {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
                
                self.monitor_cycle()
                
                if cycles and cycle_count >= cycles:
                    print(f"\nCompleted {cycles} monitoring cycles")
                    break
                
                print(f"💤 Sleeping {POLL_INTERVAL} seconds...")
                time.sleep(POLL_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n👋 Live monitor stopped by user")
        except Exception as e:
            print(f"\n❌ Monitor error: {e}")
        finally:
            print(f"\n📊 Final Status:")
            print(f"  Total cycles: {cycle_count}")
            print(f"  Games monitored: {len(self.active_games)}")
            for event_id, state in self.active_games.items():
                quarters = len(state.quarter_lines_captured)
                print(f"    FI {event_id}: {quarters}/3 quarters captured")

def main():
    monitor = LiveQuarterMonitor()
    monitor.run()

if __name__ == "__main__":
    main()