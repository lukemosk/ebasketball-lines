"""
Test if totals are consistently at index 32 in eBasketball games
"""

import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
import re
load_dotenv(find_dotenv())

from src.betsapi import _get_results, _get_json

# NBA teams for filtering
NBA_TEAMS = {
    'hawks', 'celtics', 'nets', 'hornets', 'bulls', 'cavaliers', 'mavericks',
    'nuggets', 'pistons', 'warriors', 'rockets', 'pacers', 'clippers', 'lakers',
    'grizzlies', 'heat', 'bucks', 'timberwolves', 'pelicans', 'knicks',
    'thunder', 'magic', 'sixers', '76ers', 'suns', 'blazers', 'kings',
    'spurs', 'raptors', 'jazz', 'wizards'
}

def get_ebasketball_games():
    """Get only eBasketball games from inplay"""
    try:
        results = _get_results("/v1/bet365/inplay")
        if not results:
            return []
        
        games = []
        
        for result_group in results:
            if not isinstance(result_group, list):
                continue
            
            for item in result_group:
                if not isinstance(item, dict):
                    continue
                
                if item.get("type") == "EV":
                    game_name = item.get("NA", "")
                    game_lower = game_name.lower()
                    
                    # Check for eBasketball pattern

                    has_nba_team = any(re.search(r'\b' + team + r'\b', game_lower) for team in NBA_TEAMS)
                    has_nickname = "(" in game_name and ")" in game_name
                    
                    if has_nba_team and has_nickname:
                        fi = item.get("FI") or item.get("ID")
                        if fi:
                            games.append({
                                'fi': fi,
                                'name': game_name,
                                'raw': item
                            })
        
        # Remove duplicates
        unique_games = {}
        for game in games:
            unique_games[game['fi']] = game
        
        return list(unique_games.values())
        
    except Exception as e:
        print(f"Error getting games: {e}")
        return []

def find_totals_in_game_lines(fi):
    """Find totals within the Game Lines section"""
    try:
        data = _get_json("/v1/bet365/event", FI=fi)
        
        if not data.get("results"):
            return {'error': 'No results in response'}
        
        results = data["results"][0] if isinstance(data["results"][0], list) else []
        
        # Find Game Lines section
        game_lines_index = None
        for i, item in enumerate(results):
            if (isinstance(item, dict) and 
                item.get("type") == "MG" and 
                item.get("NA") == "Game Lines"):
                game_lines_index = i
                break
        
        if game_lines_index is None:
            return {'error': 'No Game Lines section found'}
        
        # Look for Total within next ~10 items after Game Lines
        total_index = None
        for i in range(game_lines_index + 1, min(game_lines_index + 10, len(results))):
            item = results[i]
            if (isinstance(item, dict) and 
                item.get("type") == "PA" and 
                item.get("NA") == "Total"):
                total_index = i
                break
        
        if total_index is None:
            return {
                'has_total': False,
                'game_lines_index': game_lines_index,
                'total_index': None,
                'total_lines': []
            }
        
        # Extract total lines
        total_lines = []
        for i in range(total_index + 1, min(total_index + 10, len(results))):
            item = results[i]
            if isinstance(item, dict) and item.get("type") == "PA":
                ha = item.get("HA")
                hd = item.get("HD")
                if ha and ("O" in str(hd) or "U" in str(hd)):
                    try:
                        line = float(str(ha).strip())
                        total_lines.append({
                            'line': line,
                            'display': hd,
                            'odds': item.get("OD")
                        })
                    except:
                        pass
            elif item.get("type") in ["MA", "MG"]:
                break  # Next section
        
        return {
            'has_total': True,
            'game_lines_index': game_lines_index,
            'total_index': total_index,
            'total_lines': total_lines
        }
        
    except Exception as e:
        return {'error': str(e)}

def main():
    print("=" * 80)
    print("FINDING TOTALS IN EBASKETBALL GAMES")
    print("=" * 80)
    
    games = get_ebasketball_games()
    
    if not games:
        print("No eBasketball games found")
        return
    
    print(f"\nFound {len(games)} eBasketball games")
    
    results = []
    
    for i, game in enumerate(games[:5]):  # Check first 5 games
        print(f"\n{'=' * 60}")
        print(f"Game {i+1}: {game['name']}")
        print(f"FI: {game['fi']}")
        
        if i > 0:
            print("Waiting 2 seconds...")
            time.sleep(2)
        
        result = find_totals_in_game_lines(game['fi'])
        
        if 'error' in result:
            print(f"Error: {result['error']}")
            continue
            
        print(f"\nGame Lines at index: {result['game_lines_index']}")
        
        if result['has_total']:
            print(f"Total market found at index: {result['total_index']}")
            print(f"Position after Game Lines: +{result['total_index'] - result['game_lines_index']}")
            
            if result['total_lines']:
                print(f"\nTotal lines found ({len(result['total_lines'])} values):")
                for line in result['total_lines']:
                    print(f"  Index {line['index']}: {line['line']} ({line['display']}) at {line['odds']}")
            else:
                print("\nNo line values found - check structure:")
                # Show next 10 items after Total to debug
                print("Items after 'Total' marker:")
                for j in range(result['total_index'] + 1, min(result['total_index'] + 11, len(results))):
                    try:
                        item = results[j]
                        if isinstance(item, dict):
                            print(f"  Index {j}: type={item.get('type')}, NA={item.get('NA','')}, HA={item.get('HA','')}")
                    except:
                        pass
        else:
            print("No totals in this game")
            
        results.append({
            'game': game['name'],
            'has_total': result['has_total'],
            'position_offset': result['total_index'] - result['game_lines_index'] if result['has_total'] else None
        })
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    games_with_totals = sum(1 for r in results if r['has_total'])
    print(f"Games checked: {len(results)}")
    print(f"Games with totals: {games_with_totals}")
    
    if games_with_totals > 0:
        positions = [r['position_offset'] for r in results if r['position_offset'] is not None]
        print(f"\nTotal position offsets from Game Lines: {positions}")
        print(f"Most common offset: +{max(set(positions), key=positions.count)}" if positions else "N/A")

if __name__ == "__main__":
    main()