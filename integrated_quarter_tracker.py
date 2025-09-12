# integrated_quarter_tracker.py
"""
Clean eBasketball Quarter Line Tracker with working line extraction
Incorporates the proven line extraction method from working_line_extractor.py
"""

import os
import time
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from src.betsapi import _get_results

# Configuration
DB_PATH = "data/ebasketball.db"
BOOKMAKER_ID = "bet365"
QUARTER_LENGTH_SECONDS = 300  # 5 minutes per quarter
CAPTURE_THRESHOLD_SECONDS = 10  # Capture when ≤10 seconds remain
TARGET_LEAGUE = "ebasketball h2h gg league"

def ensure_event_exists(fi: str, home: str, away: str) -> None:
    """Ensure event record exists before capturing lines"""
    try:
        with sqlite3.connect(DB_PATH) as con:
            con.execute("""
                INSERT OR IGNORE INTO event(
                    event_id, league_id, start_time_utc, status, 
                    home_name, away_name, final_home, final_away
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(fi), 
                0,  # Default league_id 
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                'live',
                home,
                away,
                None,
                None
            ))
            con.commit()
    except Exception as e:
        print(f"  Warning: Could not create event record: {e}")


def get_live_h2h_games() -> List[Dict]:
    """Get live eBasketball H2H GG League games"""
    
    try:
        results = _get_results("/v1/bet365/inplay")
        if not results:
            return []
        
        games = {}  # Use dict to deduplicate by FI
        
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
                
                elif item_type == "EV" and current_league:
                    if TARGET_LEAGUE in current_league:
                        # Extract game info
                        game_name = item.get("NA", "")
                        
                        # Get valid FI (use C2 since C3 is "0" for H2H games)
                        fi = item.get("C2", "") or item.get("C3", "") or item.get("ID", "")
                        
                        if fi and fi != "0":
                            # Parse team names
                            if " @ " in game_name:
                                teams = game_name.split(" @ ")
                                away_team = teams[0].strip()
                                home_team = teams[1].strip()
                            else:
                                home_team = game_name
                                away_team = "Unknown"
                            
                            games[fi] = {
                                'fi': fi,
                                'home': home_team,
                                'away': away_team,
                                'league': current_league,
                                'raw_data': item
                            }
        
        return list(games.values())
        
    except Exception as e:
        print(f"Error getting live games: {e}")
        return []

def parse_game_state(raw_data: Dict) -> Optional[Dict]:
    """Parse timing and score data from raw EV data"""
    
    try:
        # Extract timing fields
        minutes = int(raw_data.get("TM", 0))
        seconds = int(raw_data.get("TS", 0))
        time_running = int(raw_data.get("TT", 0)) == 1
        
        # Extract quarter from CP field
        current_period = raw_data.get("CP", "")
        if current_period and current_period.startswith("Q"):
            try:
                quarter = int(current_period[1:])  # "Q2" -> 2
            except:
                quarter = 1
        else:
            quarter = 1  # Default to Q1 if no period info
        
        # Extract scores
        score_str = raw_data.get("SS", "0-0")
        try:
            home_score, away_score = map(int, score_str.split("-"))
        except:
            home_score = away_score = 0
        
        # FIXED: TM and TS are TIME REMAINING, not elapsed!
        # Convert to remaining seconds directly
        remaining_seconds = minutes * 60 + seconds
        
        # For display/debugging - calculate elapsed time
        elapsed_in_quarter = QUARTER_LENGTH_SECONDS - remaining_seconds
        
        return {
            'quarter': quarter,
            'minutes': minutes,
            'seconds': seconds,
            'time_running': time_running,
            'remaining_seconds': remaining_seconds,
            'elapsed_in_quarter': elapsed_in_quarter,
            'home_score': home_score,
            'away_score': away_score,
            'current_period': current_period
        }
        
    except Exception as e:
        print(f"Error parsing game state: {e}")
        return None

def is_at_quarter_end(game_state: Dict) -> bool:
    """Check if game is at quarter end and should capture lines"""
    
    # Only capture Q1-Q3 quarter lines
    if game_state['quarter'] not in [1, 2, 3]:
        return False
    
    # Capture at 0:00 even if paused (quarter definitely ended)
    if game_state['remaining_seconds'] == 0:
        return True
    
    # Normal case: ≤10 seconds and clock running
    return (
        game_state['remaining_seconds'] <= CAPTURE_THRESHOLD_SECONDS and
        game_state['time_running']
    )

def extract_betting_lines() -> Dict[str, Dict]:
    """Extract current spread lines for all live games using working method"""
    
    try:
        results = _get_results("/v1/bet365/inplay")
        if not results:
            return {}
        
        # Find all spread markets
        spread_data = []
        
        for group in results:
            if not isinstance(group, list):
                continue
            
            for i, item in enumerate(group):
                if not isinstance(item, dict):
                    continue
                
                # Look for spread markets
                if item.get("type") == "MA" and "spread" in str(item.get("NA", "")).lower():
                    market_name = item.get("NA", "")
                    
                    # Collect participants following this market
                    participants = []
                    for j in range(i + 1, min(len(group), i + 20)):
                        next_item = group[j]
                        
                        if isinstance(next_item, dict):
                            if next_item.get("type") == "PA":
                                participants.append({
                                    'name': next_item.get("NA", ""),
                                    'handicap': next_item.get("HA", ""),
                                    'odds': next_item.get("OD", "")
                                })
                            elif next_item.get("type") in ["MA", "EV"]:
                                break
                    
                    if participants:
                        spread_data.append({
                            'market': market_name,
                            'participants': participants
                        })
        
        # Match spreads to games by participant names
        game_lines = {}
        
        for spread_market in spread_data:
            for participant in spread_market['participants']:
                p_name = participant['name']
                handicap = participant['handicap']
                
                if p_name and handicap and str(handicap) != "0":
                    try:
                        line_value = float(str(handicap).replace('+', '').replace('-', ''))
                        if 0.5 <= line_value <= 50:
                            spread_line = round(line_value * 2) / 2
                            
                            # Store line associated with participant name
                            game_lines[p_name] = {
                                'spread': spread_line,
                                'total': None  # Not available for H2H games
                            }
                    except (ValueError, TypeError):
                        continue
        
        return game_lines
        
    except Exception as e:
        print(f"Error extracting lines: {e}")
        return {}

def find_lines_for_game(game_name: str, all_lines: Dict) -> Dict[str, Optional[float]]:
    """Find lines for a specific game by matching team names"""
    
    lines = {'spread': None, 'total': None}
    
    # Try to match game name to participant names in lines
    for participant_name, participant_lines in all_lines.items():
        if participant_name.lower() in game_name.lower():
            if participant_lines['spread'] is not None:
                lines['spread'] = participant_lines['spread']
            if participant_lines['total'] is not None:
                lines['total'] = participant_lines['total']
            break
    
    return lines

def should_capture_opener(game_state: Dict) -> bool:
    """Capture opening line at game start"""
    # Capture at Q1 5:00 even if paused (game just started)
    return (
        game_state['quarter'] == 1 and 
        game_state['remaining_seconds'] >= 295 and  # 4:55-5:00
        game_state['remaining_seconds'] <= 300      # At game start
    )

def store_opener_line(event_id: int, lines: Dict[str, Optional[float]], timing: Dict[str, Any]) -> bool:
    """Store opening line from live feed"""
    try:
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
        with sqlite3.connect(DB_PATH) as con:
            if lines['spread'] is not None:
                con.execute("""
                    INSERT OR IGNORE INTO opener
                    (event_id, bookmaker_id, market, line, price_home, price_away, opened_at_utc)
                    VALUES (?, ?, 'spread', ?, NULL, NULL, ?)
                """, (
                    event_id, 
                    BOOKMAKER_ID, 
                    lines['spread'],
                    now_utc
                ))
            
            if lines['total'] is not None:
                con.execute("""
                    INSERT OR IGNORE INTO opener
                    (event_id, bookmaker_id, market, line, price_home, price_away, opened_at_utc)
                    VALUES (?, ?, 'total', ?, NULL, NULL, ?)
                """, (
                    event_id, 
                    BOOKMAKER_ID, 
                    lines['total'],
                    now_utc
                ))
            
            con.commit()
            return True
            
    except Exception as e:
        print(f"  ❌ Error storing opener line: {e}")
        return False

def is_game_ending(game_state: Dict) -> bool:
    """Check if game is ending (Q4/Q5 at 0:00)"""
    return (
        game_state['quarter'] in [4, 5] and 
        game_state['remaining_seconds'] == 0
    )

def store_quarter_lines(event_id: str, quarter: int, lines: Dict[str, Optional[float]], 
                       game_state: Dict) -> bool:
    """Store captured quarter lines to database"""
    
    try:
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
        with sqlite3.connect(DB_PATH) as con:
            for market, line in lines.items():
                if line is not None:
                    con.execute("""
                        INSERT OR REPLACE INTO quarter_line 
                        (event_id, bookmaker_id, quarter, market, line, captured_at_utc, 
                         game_time_remaining, home_score, away_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_id, BOOKMAKER_ID, quarter, market, line, now_utc,
                        game_state['remaining_seconds'], game_state['home_score'], 
                        game_state['away_score']
                    ))
            con.commit()
            return True
            
    except Exception as e:
        print(f"Error storing quarter lines: {e}")
        return False

def check_if_already_captured(event_id: str, quarter: int) -> bool:
    """Check if we've already captured this quarter for this event"""
    
    try:
        with sqlite3.connect(DB_PATH) as con:
            result = con.execute("""
                SELECT 1 FROM quarter_line 
                WHERE event_id = ? AND quarter = ?
                LIMIT 1
            """, (event_id, quarter)).fetchone()
            return result is not None
    except:
        return False

def handle_game_end(event_id: str, game_state: Dict) -> bool:
    """Handle game end - update final scores and status"""
    try:
        with sqlite3.connect(DB_PATH) as con:
            # Update event with final scores
            con.execute("""
                UPDATE event 
                SET status = 'finished', 
                    final_home = ?, 
                    final_away = ?
                WHERE event_id = ?
            """, (
                game_state['home_score'],
                game_state['away_score'],
                int(event_id)
            ))
            
            # Insert result analysis
            insert_result_analysis(con, int(event_id), 
                                 game_state['home_score'], 
                                 game_state['away_score'])
            
            con.commit()
            print(f"  🏁 GAME ENDED - Final: {game_state['home_score']}-{game_state['away_score']}")
            return True
            
    except Exception as e:
        print(f"  ❌ Error handling game end: {e}")
        return False

def track_games_once():
    """Single tracking cycle"""
    
    print(f"\n{datetime.now().strftime('%H:%M:%S')} - Checking live eBasketball games...")
    
    live_games = get_live_h2h_games()
    
    if not live_games:
        print("No live H2H GG League games found")
        return
    
    print(f"Tracking {len(live_games)} live games:")
    
    # Extract all current betting lines once
    all_lines = extract_betting_lines()
    print(f"Found lines for {len(all_lines)} participants")
    
    for game in live_games:
        fi = game['fi']
        home = game['home']
        away = game['away']
        
        print(f"\nFI {fi}: {home} vs {away}")
        
        ensure_event_exists(fi, home, away)

        # Parse game state
        game_state = parse_game_state(game['raw_data'])
        if not game_state:
            print("  Could not parse game state")
            continue
        
        # Display current state
        quarter = game_state['quarter']
        minutes = game_state['minutes']
        seconds = game_state['seconds']
        running = "⏰" if game_state['time_running'] else "⏸️"
        
        print(f"  Q{quarter}: {minutes}:{seconds:02d} {running}")
        print(f"  Score: {game_state['home_score']}-{game_state['away_score']}")
        print(f"  Remaining in quarter: {game_state['remaining_seconds']}s")
        
        # Find lines for this specific game
        game_name = f"{home} vs {away}"
        lines = find_lines_for_game(game_name, all_lines)
        print(f"  Lines: spread={lines['spread']}, total={lines['total']}")

        # Check if game is ending
        if is_game_ending(game_state):
            print(f"  🏁 GAME ENDING - CAPTURING FINAL SCORE...")
            handle_game_end(fi, game_state)
            continue
        
        # Check if at quarter end(Q1-Q3 only)
        if is_at_quarter_end(game_state):
            print(f"  🚨 AT QUARTER {quarter} END - CAPTURING LINES...")
            
            # Check if already captured
            if check_if_already_captured(fi, quarter):
                print(f"  ⚠️  Q{quarter} already captured for this game")
                continue
            
            # Store if we got valid lines
            if lines['spread'] is not None:
                if store_quarter_lines(fi, quarter, lines, game_state):
                    print(f"  ✅ Successfully captured Q{quarter} lines!")
                else:
                    print(f"  ❌ Failed to store lines")
            else:
                print(f"  ⚠️  No valid betting lines found")

        elif should_capture_opener(game_state):
            print(f"  📍 GAME START - CAPTURING OPENING LINES...")
            # Check if we already have an opener
            with sqlite3.connect(DB_PATH) as con:
                existing = con.execute("""
                    SELECT 1 FROM opener 
                    WHERE event_id = ? AND market = 'spread'
                    LIMIT 1
                """, (fi,)).fetchone()
            
            if existing:
                print(f"  ⚠️  Opening lines already captured for this game")
            else:
                if lines['spread'] is not None:
                    if store_opener_line(int(fi), lines, game_state):
                        print(f"  ✅ Successfully captured opening lines!")
                    else:
                        print(f"  ❌ Failed to store opening lines")
                else:
                    print(f"  ⚠️  No valid betting lines found")

        elif game_state['remaining_seconds'] <= 30:
            print(f"  ⚡ Approaching quarter end ({game_state['remaining_seconds']}s remaining)")
        
    check_and_update_finished_games()

def get_adaptive_poll_interval(live_games: List[Dict]) -> int:
    """Get polling interval based on game states - faster near quarter ends"""
    
    if not live_games:
        return 20  # Default when no games
    
    min_remaining = 999
    closest_game = None
    
    # Find the closest quarter end
    for game in live_games:
        game_state = parse_game_state(game.get('raw_data', {}))
        if game_state and game_state['quarter'] in [1, 2, 3, 4, 5]:
            remaining = game_state['remaining_seconds']
            if game_state['time_running'] and remaining < min_remaining:
                min_remaining = remaining
                closest_game = f"{game['home']} vs {game['away']} Q{game_state['quarter']}"
    
    # Adaptive intervals
    if min_remaining <= 5:
        interval = 1    # 1 second - CRITICAL ZONE!
    elif min_remaining <= 10:
        interval = 2    # 2 seconds - very close
    elif min_remaining <= 20:
        interval = 3    # 3 seconds - approaching
    elif min_remaining <= 30:
        interval = 5    # 5 seconds - getting close
    else:
        interval = 15   # 15 seconds - normal polling
    
    # Debug output
    if min_remaining < 999:
        print(f"  📊 Closest quarter end: {min_remaining}s remaining ({closest_game})")
    else:
        print(f"  📊 No games approaching quarter end")
    
    return interval


def check_and_update_finished_games():
    """Check if any tracked games have finished and update their results"""
    try:
        with sqlite3.connect(DB_PATH) as con:
            con.row_factory = sqlite3.Row
            
            # Get games that might be finished (started >20 mins ago, still marked as live)
            games = con.execute("""
                SELECT event_id, home_name, away_name 
                FROM event 
                WHERE status = 'live' 
                AND start_time_utc < datetime('now', '-20 minutes')
                AND final_home IS NULL
            """).fetchall()
            
            if not games:
                return
            
            print(f"\n🔍 Checking {len(games)} games for results...")
            
            for game in games:
                event_id = game['event_id']
                
                # Import here to avoid circular import
                from src.betsapi import get_event_result
                
                result = get_event_result(event_id) or {}
                fh = result.get("final_home")
                fa = result.get("final_away")
                
                if fh is not None and fa is not None:
                    # Update the event with finals
                    con.execute("""
                        UPDATE event 
                        SET status = 'finished', final_home = ?, final_away = ?
                        WHERE event_id = ?
                    """, (int(fh), int(fa), event_id))
                    
                    print(f"  ✅ {game['home_name']} vs {game['away_name']}: {fh}-{fa}")
                    
                    # Calculate and insert result
                    insert_result_analysis(con, event_id, int(fh), int(fa))
            
            con.commit()
            
    except Exception as e:
        print(f"Error checking results: {e}")

def insert_result_analysis(con, event_id: int, final_home: int, final_away: int):
    """Insert result analysis for a finished game"""
    try:
        # Get opener lines
        opener = con.execute("""
            SELECT 
                MAX(CASE WHEN market='spread' THEN line END) as spread_line,
                MAX(CASE WHEN market='total' THEN line END) as total_line
            FROM opener 
            WHERE event_id = ?
        """, (event_id,)).fetchone()
        
        if not opener:
            return
        
        spread_line = opener['spread_line']
        total_line = opener['total_line']
        
        # Calculate deltas
        margin = abs(final_home - final_away)
        total = final_home + final_away
        
        spread_delta = abs(margin - abs(spread_line)) if spread_line else None
        total_delta = abs(total - total_line) if total_line else None
        
        # Calculate within flags
        def within(d, threshold):
            return 1 if d is not None and d <= threshold else 0
        
        # Insert result
        con.execute("""
            INSERT OR REPLACE INTO result(
                event_id, spread_delta, total_delta,
                within2_spread, within3_spread, within4_spread, within5_spread,
                within2_total, within3_total, within4_total, within5_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, spread_delta, total_delta,
            within(spread_delta, 2), within(spread_delta, 3), 
            within(spread_delta, 4), within(spread_delta, 5),
            within(total_delta, 2), within(total_delta, 3),
            within(total_delta, 4), within(total_delta, 5)
        ))
        
    except Exception as e:
        print(f"Error inserting result analysis: {e}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated Quarter Tracker")
    parser.add_argument("--once", action="store_true", help="Run once")
    parser.add_argument("--monitor", action="store_true", help="Continuous monitoring")
    parser.add_argument("--adaptive", action="store_true", help="Use adaptive polling")
    
    args = parser.parse_args()
    
    print("eBasketball Quarter Line Tracker (Integrated)")
    print("=" * 50)
    
    if args.monitor:
        if args.adaptive:
            print("Starting ADAPTIVE monitoring (speeds up near quarter ends)")
            print("Polling: 1s at <5s | 2s at <10s | 3s at <20s | 5s at <30s | 15s normal")
        else:
            print(f"Starting continuous monitoring (fixed 20s polling)")
        
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                live_games = get_live_h2h_games()
                track_games_once()
                
                if args.adaptive and live_games:
                    interval = get_adaptive_poll_interval(live_games)
                    print(f"\n⏱️  Next check in {interval}s...")
                    time.sleep(interval)
                else:
                    time.sleep(20)
                    
        except KeyboardInterrupt:
            print("\nStopping tracker...")
    else:
        track_games_once()

if __name__ == "__main__":
    main()