# test_live_betting_lines.py
"""
Test extraction of live betting lines from eBasketball games
"""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from src.betsapi import _get_results

def get_current_live_games():
    """Get current live H2H games with FIs"""
    
    try:
        results = _get_results("/v1/bet365/inplay")
        if not results:
            return []
        
        games = []
        
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
                    if "ebasketball h2h gg league" in current_league:
                        game_name = item.get("NA", "")
                        fi = item.get("C2", "") or item.get("C3", "")
                        
                        if fi and fi != "0":
                            games.append({
                                'fi': fi,
                                'name': game_name,
                                'quarter': item.get("CP", ""),
                                'score': item.get("SS", "")
                            })
        
        return games[:2]  # Just test 2 games to keep output manageable
        
    except Exception as e:
        print(f"Error getting live games: {e}")
        return []

def test_detailed_game_data(fi):
    """Get detailed betting data for a specific game"""
    
    print(f"\nTesting detailed data for FI {fi}...")
    
    try:
        # Get detailed game data (where betting markets should be)
        detailed_data = _get_results("/v1/bet365/event", FI=fi, stats=1)
        
        if not detailed_data:
            print("  No detailed data returned")
            return
        
        game_data = detailed_data[0] if isinstance(detailed_data, list) else detailed_data
        
        print(f"  Detailed data type: {type(game_data)}")
        
        # Look for market-related nodes
        markets_found = []
        participants_found = []
        
        def search_for_markets(data, path=""):
            if isinstance(data, dict):
                node_type = data.get("type")
                
                if node_type == "MA":  # Market Area
                    market_name = data.get("NA", "")
                    markets_found.append({
                        'name': market_name,
                        'path': path,
                        'data': data
                    })
                
                elif node_type == "PA":  # Participant
                    participant_name = data.get("NA", "")
                    handicap = data.get("HA", "")
                    odds = data.get("OD", "")
                    
                    participants_found.append({
                        'name': participant_name,
                        'handicap': handicap,
                        'odds': odds,
                        'path': path
                    })
                
                for key, value in data.items():
                    search_for_markets(value, f"{path}.{key}" if path else key)
                    
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    search_for_markets(item, f"{path}[{i}]" if path else f"[{i}]")
        
        search_for_markets(game_data)
        
        print(f"  Found {len(markets_found)} markets:")
        for market in markets_found[:10]:  # Show first 10
            print(f"    - {market['name']}")
        
        print(f"  Found {len(participants_found)} participants:")
        
        # Look for spread and total related participants
        spread_participants = []
        total_participants = []
        
        for p in participants_found:
            name = p['name'].lower()
            handicap = str(p['handicap'])
            
            # Look for spread indicators
            if any(keyword in name for keyword in ['spread', 'handicap']) or \
               (handicap and any(char in handicap for char in ['+', '-'])):
                spread_participants.append(p)
            
            # Look for total indicators
            elif any(keyword in name for keyword in ['total', 'over', 'under']) or \
                 (handicap and handicap.replace('.', '').isdigit() and 
                  50 <= float(handicap) <= 300):
                total_participants.append(p)
        
        print(f"  Potential spread participants: {len(spread_participants)}")
        for p in spread_participants[:5]:
            print(f"    - {p['name']} | HA: {p['handicap']} | OD: {p['odds']}")
        
        print(f"  Potential total participants: {len(total_participants)}")
        for p in total_participants[:5]:
            print(f"    - {p['name']} | HA: {p['handicap']} | OD: {p['odds']}")
        
        # Try to extract actual lines
        lines = extract_lines_from_participants(participants_found)
        print(f"  Extracted lines: {lines}")
        
    except Exception as e:
        print(f"  Error getting detailed data: {e}")
        import traceback
        traceback.print_exc()

def extract_lines_from_participants(participants):
    """Extract spread and total lines from participant data"""
    
    lines = {'spread': None, 'total': None}
    
    for p in participants:
        handicap = str(p['handicap']).strip()
        name = p['name'].lower()
        
        if not handicap or handicap == "0":
            continue
        
        try:
            # Try to parse as float
            line_value = float(handicap.replace('+', '').replace('-', ''))
            
            # Classify as spread or total based on value range
            if 0.5 <= line_value <= 50:  # Spread range
                if lines['spread'] is None:
                    lines['spread'] = line_value
                    
            elif 50 <= line_value <= 300:  # Total range  
                if lines['total'] is None:
                    lines['total'] = line_value
                    
        except (ValueError, TypeError):
            continue
    
    return lines

def main():
    print("TESTING LIVE BETTING LINES EXTRACTION")
    print("=" * 50)
    
    # Get current live games
    live_games = get_current_live_games()
    
    if not live_games:
        print("No live games found")
        return
    
    print(f"Found {len(live_games)} live games to test:")
    for game in live_games:
        print(f"  FI {game['fi']}: {game['name']} ({game['quarter']}, {game['score']})")
    
    # Test detailed data for each game
    for game in live_games:
        test_detailed_game_data(game['fi'])

if __name__ == "__main__":
    main()