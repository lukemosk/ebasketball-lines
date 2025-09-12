# working_line_extractor.py
"""
Fresh approach - build on what we know works
"""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from src.betsapi import _get_results

def get_all_games():
    """Get all unique eBasketball games"""
    results = _get_results("/v1/bet365/inplay", sport_id=18)
    
    games = {}
    for group in results or []:
        if not isinstance(group, list):
            continue
            
        league = None
        for item in group:
            if not isinstance(item, dict):
                continue
                
            if item.get("type") == "CT":
                league = item.get("NA", "").lower()
            elif item.get("type") == "EV" and league and "ebasketball h2h gg league" in league:
                fi = item.get("C2") or item.get("C3")
                if fi and fi != "0":
                    games[fi] = {
                        'fi': fi,
                        'name': item.get("NA", ""),
                        'score': item.get("SS", ""),
                        'quarter': item.get("CP", "")
                    }
    
    return list(games.values())

def find_all_spread_markets():
    """Find all spread markets in the inplay data"""
    results = _get_results("/v1/bet365/inplay", sport_id=18)
    
    spread_data = []
    
    for group in results or []:
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
                for j in range(i + 1, min(len(group), i + 20)):  # Look ahead more
                    next_item = group[j]
                    
                    if isinstance(next_item, dict):
                        if next_item.get("type") == "PA":
                            participants.append({
                                'name': next_item.get("NA", ""),
                                'handicap': next_item.get("HA", ""),
                                'odds': next_item.get("OD", "")
                            })
                        elif next_item.get("type") in ["MA", "EV"]:
                            # Stop at next market or event
                            break
                
                if participants:
                    spread_data.append({
                        'market': market_name,
                        'participants': participants
                    })
    
    return spread_data

def try_match_spreads_to_games(games, spread_data):
    """Try to match spread data to games"""
    
    for game in games:
        game['spread'] = None
        game['total'] = None
    
    print(f"Trying to match {len(spread_data)} spread markets to {len(games)} games...")
    
    for spread_market in spread_data:
        print(f"\nSpread market: {spread_market['market']}")
        
        for participant in spread_market['participants']:
            p_name = participant['name']
            handicap = participant['handicap']
            
            print(f"  Participant: '{p_name}' | HA: '{handicap}'")
            
            # Try to match participant name to game
            if p_name and handicap and str(handicap) != "0":
                for game in games:
                    # Simple name matching - check if participant name appears in game name
                    if p_name.lower() in game['name'].lower():
                        try:
                            line_value = float(str(handicap).replace('+', '').replace('-', ''))
                            if 0.5 <= line_value <= 50:
                                game['spread'] = round(line_value * 2) / 2
                                print(f"    -> MATCHED to {game['name']}: spread={game['spread']}")
                                break
                        except (ValueError, TypeError):
                            pass
    
    return games

def main():
    print("Working Line Extractor")
    print("=" * 30)
    
    # Step 1: Get all games
    games = get_all_games()
    print(f"Found {len(games)} unique games:")
    for game in games:
        print(f"  - {game['name']} ({game['score']}, {game['quarter']})")
    
    # Step 2: Find all spread markets
    spread_markets = find_all_spread_markets()
    print(f"\nFound {len(spread_markets)} spread markets")
    
    # Step 3: Try to match them
    games_with_lines = try_match_spreads_to_games(games, spread_markets)
    
    # Step 4: Show results
    print("\nFinal Results:")
    print("=" * 30)
    
    for game in games_with_lines:
        print(f"FI {game['fi']}: {game['name']}")
        print(f"  Score: {game['score']} | Quarter: {game['quarter']}")
        print(f"  Spread: {game['spread']}")
        print()

if __name__ == "__main__":
    main()