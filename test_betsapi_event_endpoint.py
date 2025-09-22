"""
Test BetsAPI's suggested strategy:
1. Get FI from /v1/bet365/inplay
2. Use that FI with /v1/bet365/event
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from src.betsapi import _get_results, _get_json

def test_betsapi_strategy():
    """Follow BetsAPI support's exact instructions"""
    
    print("=" * 80)
    print("TESTING BETSAPI STRATEGY: inplay -> event")
    print("=" * 80)
    
    # Step 1: Get live games from inplay
    print("\n1. Getting live games from /v1/bet365/inplay...")
    inplay_results = _get_results("/v1/bet365/inplay")
    
    if not inplay_results:
        print("No live games found")
        return
    
    # Find eBasketball H2H GG League games
    print("\n2. Looking for eBasketball H2H GG League games...")
    
    ebasketball_games = []
    current_league = None
    
    for result_group in inplay_results:
        if not isinstance(result_group, list):
            continue
        
        for item in result_group:
            if not isinstance(item, dict):
                continue
            
            item_type = item.get("type")
            
            # Track current league
            if item_type == "CT":
                current_league = item.get("NA", "").lower()
            
            # Check if it's an eBasketball game
            elif item_type == "EV" and current_league:
                if "ebasketball h2h gg league" in current_league:
                    fi = item.get("FI") or item.get("ID")
                    if fi:
                        game_info = {
                            'fi': fi,
                            'name': item.get("NA", ""),
                            'league': current_league,
                            'raw_item': item
                        }
                        ebasketball_games.append(game_info)
    
    if not ebasketball_games:
        print("No eBasketball H2H GG League games found")
        return
    
    print(f"\nFound {len(ebasketball_games)} eBasketball games")
    
    # Step 3: For each game, call the event endpoint
    for game in ebasketball_games[:3]:  # Test first 3 games
        fi = game['fi']
        print(f"\n{'=' * 60}")
        print(f"Game: {game['name']}")
        print(f"FI: {fi}")
        print(f"{'=' * 60}")
        
        # Call event endpoint with this FI
        print(f"\n3. Calling /v1/bet365/event with FI={fi}...")
        
        try:
            event_data = _get_json("/v1/bet365/event", FI=fi)
            
            # Save full response for analysis
            filename = f"event_response_fi_{fi}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(event_data, f, indent=2)
            print(f"Saved full response to: {filename}")
            
            # Search for any mention of totals or game lines
            print("\n4. Searching for totals/game lines in response...")
            
            def search_for_patterns(obj, path="root"):
                """Recursively search for betting market patterns"""
                findings = []
                
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        key_lower = str(key).lower()
                        
                        # Check for market indicators
                        if any(term in key_lower for term in ['market', 'line', 'total', 'spread', 'handicap']):
                            findings.append(f"Found key '{key}' at {path}")
                        
                        # Check NA fields
                        if key == "NA" and isinstance(value, str):
                            value_lower = value.lower()
                            if any(term in value_lower for term in ['total', 'over', 'under', 'spread', 'game line']):
                                findings.append(f"Found market: '{value}' at {path}.NA")
                        
                        # Check for the specific structure BetsAPI mentioned
                        if key_lower == "game_lines" or key_lower == "game lines":
                            findings.append(f"FOUND GAME LINES at {path}.{key}!")
                            print(f"\nGAME LINES STRUCTURE:")
                            print(json.dumps(value, indent=2)[:500])  # Print first 500 chars
                        
                        # Recurse
                        findings.extend(search_for_patterns(value, f"{path}.{key}"))
                
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        findings.extend(search_for_patterns(item, f"{path}[{i}]"))
                
                return findings
            
            findings = search_for_patterns(event_data)
            
            if findings:
                print("\nFindings:")
                for finding in findings[:20]:  # Show first 20
                    print(f"  - {finding}")
                if len(findings) > 20:
                    print(f"  ... and {len(findings) - 20} more")
            else:
                print("No obvious total/game line structures found")
            
            # Also check the results array specifically
            if "results" in event_data:
                results = event_data["results"]
                print(f"\nResults array has {len(results) if isinstance(results, list) else 'non-list'} items")
                
                # Print a sample of the structure
                if isinstance(results, list) and results:
                    print("\nSample of first result item:")
                    print(json.dumps(results[0], indent=2)[:1000])  # First 1000 chars
            
        except Exception as e:
            print(f"Error calling event endpoint: {e}")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("Check the saved JSON files for full response structure")
    print("=" * 80)

if __name__ == "__main__":
    test_betsapi_strategy()