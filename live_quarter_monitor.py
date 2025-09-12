# live_quarter_monitor.py - FIXED version using correct API endpoint for timing data
from __future__ import annotations
import time
import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from src import betsapi
from src.config import CONF

DB_PATH = "data/ebasketball.db"
POLL_INTERVAL = 15  # Check every 15 seconds

@dataclass
class GameState:
    event_id: int
    quarter: int
    time_remaining_seconds: int
    score: str
    last_poll: datetime
    quarter_lines_captured: set

class LiveQuarterMonitor:
    def __init__(self):
        self.active_games: Dict[int, GameState] = {}
        self.db_path = DB_PATH
        
    def get_live_games_from_inplay(self) -> List[Dict]:
        """Get live eBasketball games from inplay_filter endpoint"""
        try:
            import requests
            import os
            
            token = os.getenv("BETSAPI_KEY")
            url = f"https://api.b365api.com/v1/bet365/inplay_filter?sport_id=18&token={token}"
            
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                print(f"❌ inplay_filter API Error: {response.status_code}")
                return []
            
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
                
                # Filter for eBasketball H2H GG League (exclude Battle)
                if ('ebasketball h2h gg league' in league_name and 
                    '4x5mins' in league_name and 
                    'battle' not in league_name):
                    
                    ebasketball_games.append({
                        'id': game.get('id'),
                        'home': self._safe_team_name(game.get('home')),
                        'away': self._safe_team_name(game.get('away')),
                        'ss': game.get('ss', ''),
                        'time_status': game.get('time_status', '0')
                    })
            
            return ebasketball_games
            
        except Exception as e:
            print(f"Error getting live games: {e}")
            return []
    
    def _safe_team_name(self, team) -> str:
        """Extract team name safely"""
        if isinstance(team, dict):
            return str(team.get('name', 'Unknown'))
        return str(team or 'Unknown')
    
    def get_detailed_game_timing(self, event_id: int) -> Optional[Dict]:
        """Get detailed timing from bet365/event endpoint with stats=1"""
        try:
            import requests
            import os
            
            token = os.getenv("BETSAPI_KEY")
            url = f"https://api.b365api.com/v1/bet365/event?FI={event_id}&token={token}&stats=1"
            
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                return None
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                return None
            
            # Look for the EV object with timing data
            ev_object = self._find_ev_object(results)
            if not ev_object:
                return None
            
            # Extract timing fields
            ss = ev_object.get('SS', '')  # Score like "64-39"
            tm = ev_object.get('TM', 0)   # Minutes elapsed 
            ts = ev_object.get('TS', 0)   # Seconds elapsed
            tt = ev_object.get('TT', 0)   # Timer ticking (1=yes, 0=no)
            
            # Calculate quarter and remaining time
            try:
                minutes_elapsed = int(tm) if tm else 0
                seconds_elapsed = int(ts) if ts else 0
                timer_running = str(tt) == '1'
                
                total_elapsed_seconds = minutes_elapsed * 60 + seconds_elapsed
                
                # Determine quarter (5 minutes = 300 seconds per quarter)
                if total_elapsed_seconds < 300:
                    quarter = 1
                    remaining_seconds = 300 - total_elapsed_seconds
                elif total_elapsed_seconds < 600:
                    quarter = 2
                    remaining_seconds = 600 - total_elapsed_seconds
                elif total_elapsed_seconds < 900:
                    quarter = 3
                    remaining_seconds = 900 - total_elapsed_seconds
                elif total_elapsed_seconds < 1200:
                    quarter = 4
                    remaining_seconds = 1200 - total_elapsed_seconds
                else:
                    # Overtime or game over
                    quarter = 4
                    remaining_seconds = 0
                
                return {
                    'score': ss,
                    'quarter': quarter,
                    'total_remaining_seconds': max(0, remaining_seconds),
                    'timer_running': timer_running,
                    'is_live': True,
                    'raw_tm': tm,
                    'raw_ts': ts,
                    'raw_tt': tt
                }
                
            except Exception as e:
                print(f"Error calculating timing for FI {event_id}: {e}")
                return None
                
        except Exception as e:
            print(f"Error getting detailed timing for FI {event_id}: {e}")
            return None
    
    def _find_ev_object(self, data) -> Optional[Dict]:
        """Recursively find the EV object in the response"""
        if isinstance(data, dict):
            if data.get('type') == 'EV':
                return data
            for value in data.values():
                result = self._find_ev_object(value)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_ev_object(item)
                if result:
                    return result
        return None
    
    def is_quarter_ending(self, quarter: int, remaining_seconds: int) -> bool:
        """Check if we're at the end of a quarter we want to monitor"""
        # Only monitor quarters 1, 2, and 3
        if quarter not in [1, 2, 3]:
            return False
            
        # Consider it ending if 3 seconds or less remaining
        return remaining_seconds <= 3
    
    def capture_quarter_lines(self, event_id: int, quarter: int) -> bool:
        """Capture spread and total lines at quarter end"""
        try:
            # Get current lines from prematch/live odds
            odds_data = betsapi.get_odds_openers(event_id)
            if not odds_data:
                print(f"  ⚠️  No odds available for FI {event_id} at Q{quarter} end")
                return False
            
            spread_line = odds_data.get("spread")
            total_line = odds_data.get("total")
            captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            
            # Store in database
            with sqlite3.connect(self.db_path) as con:
                lines_saved = 0
                
                if spread_line is not None:
                    con.execute("""
                        INSERT OR REPLACE INTO quarter_line 
                        (event_id, bookmaker_id, market, quarter, line, captured_at_utc)
                        VALUES (?, ?, 'spread', ?, ?, ?)
                    """, (event_id, CONF["book"], quarter, float(spread_line), captured_at))
                    lines_saved += 1
                
                if total_line is not None:
                    con.execute("""
                        INSERT OR REPLACE INTO quarter_line 
                        (event_id, bookmaker_id, market, quarter, line, captured_at_utc)
                        VALUES (?, ?, 'total', ?, ?, ?)
                    """, (event_id, CONF["book"], quarter, float(total_line), captured_at))
                    lines_saved += 1
                
                con.commit()
            
            print(f"  💎 Q{quarter} lines captured: spread={spread_line}, total={total_line}")
            return lines_saved > 0
            
        except Exception as e:
            print(f"  ❌ Error capturing Q{quarter} lines for FI {event_id}: {e}")
            return False
    
    def monitor_cycle(self):
        """Run one monitoring cycle"""
        print(f"\n🔄 [{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC] Quarter Monitor Cycle")
        
        # Get live games
        live_games = self.get_live_games_from_inplay()
        
        if not live_games:
            print("  📡 No live eBasketball games found")
            if self.active_games:
                print(f"  🧹 Clearing {len(self.active_games)} games from tracking")
                self.active_games.clear()
            return
        
        print(f"  📡 Found {len(live_games)} live eBasketball games")
        
        # Check detailed timing for each game
        games_monitored = 0
        new_captures = 0
        
        for game in live_games:
            event_id = int(game['id'])
            
            # Get detailed timing data
            timing = self.get_detailed_game_timing(event_id)
            if not timing:
                continue
            
            # Start tracking if not already
            if event_id not in self.active_games:
                self.active_games[event_id] = GameState(
                    event_id=event_id,
                    quarter=timing['quarter'],
                    time_remaining_seconds=timing['total_remaining_seconds'],
                    score=timing['score'],
                    last_poll=datetime.now(timezone.utc),
                    quarter_lines_captured=set()
                )
                print(f"🆕 Started tracking FI {event_id}: {game['home']} vs {game['away']}")
            
            # Update game state
            game_state = self.active_games[event_id]
            
            # Check for quarter ending
            if (self.is_quarter_ending(timing['quarter'], timing['total_remaining_seconds']) and
                timing['quarter'] not in game_state.quarter_lines_captured):
                
                remaining_min = timing['total_remaining_seconds'] // 60
                remaining_sec = timing['total_remaining_seconds'] % 60
                
                print(f"  🎯 Q{timing['quarter']} ending detected for FI {event_id}! ({remaining_min}:{remaining_sec:02d} remaining)")
                
                if self.capture_quarter_lines(event_id, timing['quarter']):
                    game_state.quarter_lines_captured.add(timing['quarter'])
                    new_captures += 1
            
            # Update state
            game_state.quarter = timing['quarter']
            game_state.time_remaining_seconds = timing['total_remaining_seconds']
            game_state.score = timing['score']
            game_state.last_poll = datetime.now(timezone.utc)
            
            # Display current status
            remaining_min = timing['total_remaining_seconds'] // 60
            remaining_sec = timing['total_remaining_seconds'] % 60
            captured_count = len(game_state.quarter_lines_captured)
            
            print(f"    FI {event_id}: Q{timing['quarter']} {remaining_min}:{remaining_sec:02d} | {timing['score']} | Captured: {captured_count}/3")
            
            games_monitored += 1
        
        # Clean up games no longer live
        to_remove = []
        for event_id in list(self.active_games.keys()):
            if not any(int(g['id']) == event_id for g in live_games):
                to_remove.append(event_id)
        
        for event_id in to_remove:
            del self.active_games[event_id]
            print(f"  🏁 Stopped tracking FI {event_id} (no longer live)")
        
        # Summary
        print(f"  📊 Monitoring {games_monitored} games | {new_captures} quarter lines captured")
        
        if new_captures == 0:
            recent_captures = self._count_recent_captures()
            print(f"  📊 No new quarter lines captured in last minute")
        
    def _count_recent_captures(self) -> int:
        """Count quarter lines captured in the last minute"""
        try:
            with sqlite3.connect(self.db_path) as con:
                count = con.execute("""
                    SELECT COUNT(*) 
                    FROM quarter_line 
                    WHERE captured_at_utc >= datetime('now', '-1 minute')
                """).fetchone()[0]
            return count
        except:
            return 0
    
    def run(self, cycles: Optional[int] = None):
        """Run the monitor for a specified number of cycles or indefinitely"""
        print("🏀 LIVE QUARTER MONITOR (FIXED VERSION)")
        print("=" * 60)
        print("- Monitors live eBasketball H2H GG League games")
        print("- Captures spread/total lines when quarters 1, 2, 3 end (≤3 seconds remaining)")
        print("- Uses correct API endpoints for accurate timing")
        print("- Press Ctrl+C to stop")
        print()
        
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                self.monitor_cycle()
                
                if cycles and cycle_count >= cycles:
                    print(f"\n✅ Completed {cycles} monitoring cycles")
                    break
                
                print(f"💤 Waiting {POLL_INTERVAL} seconds before next cycle...")
                time.sleep(POLL_INTERVAL)
                
        except KeyboardInterrupt:
            print(f"\n👋 Monitor stopped by user")
        except Exception as e:
            print(f"\n❌ Monitor error: {e}")
        finally:
            self._show_final_summary()
    
    def _show_final_summary(self):
        """Show final summary of captured data"""
        try:
            with sqlite3.connect(self.db_path) as con:
                con.row_factory = sqlite3.Row
                
                total_captures = con.execute("SELECT COUNT(*) as count FROM quarter_line").fetchone()['count']
                
                recent_captures = con.execute("""
                    SELECT COUNT(*) as count 
                    FROM quarter_line 
                    WHERE captured_at_utc >= datetime('now', '-1 hour')
                """).fetchone()['count']
                
                print(f"\n📊 FINAL SUMMARY:")
                print(f"  Total quarter lines in database: {total_captures}")
                print(f"  Captured in last hour: {recent_captures}")
                
                if recent_captures > 0:
                    print(f"\n💡 To analyze captured data:")
                    print(f"   python quarter_analysis.py")
                
        except Exception as e:
            print(f"Error generating summary: {e}")

# Standalone runner
def main():
    monitor = LiveQuarterMonitor()
    monitor.run()

if __name__ == "__main__":
    main()